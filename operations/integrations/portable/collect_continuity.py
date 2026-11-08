"""Read-only, bounded DEV evidence export. Never invokes workers or consumes SQS.

CloudWatch/DynamoDB/S3 already persist the trial's evidence without this process.
Run after a real observation interval; a report never extrapolates future health.
"""
import argparse
import collections
import datetime as dt
import json
from pathlib import Path

PREFIX = 'ecs-portable-r20261026p1'
UTC = dt.timezone.utc


def timestamp(value):
    parsed = dt.datetime.fromisoformat(value.replace('Z', '+00:00'))
    if parsed.utcoffset() != dt.timedelta(0):
        raise ValueError('UTC required')
    return parsed


def summarize(rows, max_gap_seconds=90):
    """Separate unhealthy samples and missing visibility; no filling of gaps."""
    rows = sorted(rows, key=lambda x: x['timestamp'])
    if len({x['eventId'] for x in rows}) != len(rows):
        raise ValueError('Duplicate log events')
    segments, gaps, unhealthy = [], [], []
    current = None
    previous = None
    for row in rows:
        at = row['timestamp'] / 1000
        data = row['data']
        gap = previous is not None and at-previous > max_gap_seconds
        if gap:
            gaps.append({'after': previous, 'before': at, 'seconds': at-previous})
        healthy = (data.get('healthy') == 1 and data['result']['state'] in ('HEALTHY_ACTIVE', 'HEALTHY_IDLE')
                   and data.get('activePermanentFailures') == 0)
        if gap or not healthy:
            if current:
                segments.append(current)
                current = None
        if healthy:
            if current is None:
                current = {'first': at, 'last': at, 'samples': 0}
            current['last'] = at
            current['samples'] += 1
        else:
            unhealthy.append({'at': at, 'state': data['result']['state'], 'reasons': data['result'].get('reasons')})
        previous = at
    if current:
        segments.append(current)
    for segment in segments:
        segment['observedSeconds'] = segment['last']-segment['first']
    return {'healthySegments': segments, 'visibilityGaps': gaps, 'unhealthySamples': unhealthy,
            'samples': len(rows), 'maxGapSeconds': max_gap_seconds,
            'claim': 'SAMPLED_HEALTH_ONLY; reconcile deployments/manual invocations separately'}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--since', type=timestamp, required=True)
    p.add_argument('--until', type=timestamp)
    p.add_argument('--profile', default='cnp-cert-dev')
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    now = dt.datetime.now(UTC)
    end = a.until or now
    if not a.since < end <= now or end-a.since > dt.timedelta(hours=26) or a.output.exists():
        p.error('A past interval <=26 hours and a new private output file are required')
    import boto3
    from botocore.config import Config
    s = boto3.Session(profile_name=a.profile, region_name='us-east-1')
    client = lambda name: s.client(name, config=Config(retries={'total_max_attempts': 1}))
    identity = client('sts').get_caller_identity()
    if identity['Arn'] != 'arn:aws:iam::341936017254:user/cnp-cert-admin':
        raise ValueError('Administrative DEV read identity mismatch')
    out = {'at': now.isoformat(), 'since': a.since.isoformat(), 'until': end.isoformat(),
           'identity': identity['Arn'], 'mutations': 0}
    logs = client('logs')
    for role, term in [('worker', 'SentinelTick'), ('watchdog', 'SentinelHealth'), ('backup-observer', 'observationId')]:
        args = dict(logGroupName='/aws/lambda/'+PREFIX+'-'+role, startTime=int(a.since.timestamp()*1000),
                    endTime=int(end.timestamp()*1000), filterPattern='"'+term+'"', limit=1000)
        rows, metric_lines = [], []
        for _ in range(40):
            result = logs.filter_log_events(**args)
            for event in result['events']:
                if role == 'watchdog' and event['message'].rstrip().endswith(('SentinelHealthMetric 0', 'SentinelHealthMetric 1')):
                    metric_lines.append(event)
                    continue
                # An unexpected matching record is a visible collection failure.
                body = event['message'][event['message'].index('{'):]
                rows.append({'timestamp': event['timestamp'], 'eventId': event['eventId'],
                             'stream': event['logStreamName'], 'data': json.loads(body)})
            if not result.get('nextToken'):
                break
            args['nextToken'] = result['nextToken']
        else:
            raise RuntimeError('Incomplete bounded log collection')
        out[role] = sorted(rows, key=lambda x: x['timestamp'])
        if metric_lines:
            out[role+'MetricLines'] = metric_lines
    out['health'] = summarize(out['watchdog'])
    work = [x['data'] for x in out['worker']]
    out['workerSummary'] = {'ticks': len(work), 'outcomes': dict(collections.Counter(x['result']['outcome'] for x in work)),
                            'maxRequests': max((x['requests'] for x in work), default=None),
                            'failures': sum(x['result']['failures'] for x in work)}
    sqs = client('sqs')
    url = sqs.get_queue_url(QueueName=PREFIX+'-operations-dlq')['QueueUrl']
    out['dlqAttributes'] = sqs.get_queue_attributes(QueueUrl=url, AttributeNames=['All'])['Attributes']
    out['alarms'] = client('cloudwatch').describe_alarms(AlarmNamePrefix=PREFIX+'-')['MetricAlarms']
    with a.output.open('x', encoding='utf-8') as f:
        json.dump(out, f, default=str, indent=2)
    print(json.dumps({'file': str(a.output), 'health': out['health'], 'worker': out['workerSummary']}, indent=2))


if __name__ == '__main__':
    main()
