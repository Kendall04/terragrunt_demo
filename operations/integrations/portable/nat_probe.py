"""One bounded HTTPS request from private subnet A; no AWS API calls."""
import datetime as dt
import ipaddress
import json
import os
import subprocess
import sys
import time
import urllib.request

TOTAL_DEADLINE_SECONDS = 6


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError('REDIRECT_REFUSED')


def https_request():
    # The child has no caller-selected URL, arguments, credentials or AWS client.
    try:
        with urllib.request.build_opener(NoRedirect()).open('https://checkip.amazonaws.com/', timeout=4) as response:
            if response.status != 200:
                raise ValueError('HTTP_STATUS')
            public = str(ipaddress.IPv4Address(response.read(65).decode('ascii').strip()))
        return {'status': 'HTTPS_SUCCESS', 'egressIp': public}
    except Exception as error:
        return {'status': 'HTTPS_FAILED', 'errorType': type(error).__name__}


def bounded_request():
    # A Python signal can be delayed inside a native resolver. Bound the entire
    # fixed child instead, including DNS, address attempts, TLS and body reads.
    # Popen startup itself is OS-dependent; a Lambda executor failure is Unknown.
    with subprocess.Popen([sys.executable, '-I', '-S', os.path.abspath(__file__), '--fixed-https'],
                          stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                          env={}, close_fds=True) as child:
        try:
            raw, _ = child.communicate(timeout=TOTAL_DEADLINE_SECONDS)
        except subprocess.TimeoutExpired:
            child.kill()
            child.communicate(timeout=1)
            return {'status': 'HTTPS_FAILED', 'errorType': 'HttpsTotalDeadline'}
        if child.returncode != 0 or len(raw) > 512:
            raise RuntimeError('PROBE_CHILD_UNAVAILABLE')
        result = json.loads(raw)
        if result.get('status') not in ('HTTPS_SUCCESS', 'HTTPS_FAILED'):
            raise RuntimeError('PROBE_CHILD_RESPONSE')
        return result


def handler(event, context):
    now = dt.datetime.now(dt.timezone.utc)
    if now >= dt.datetime.fromisoformat(os.environ['EXPIRES_AT'].replace('Z', '+00:00')):
        raise ValueError('PROBE_WINDOW_EXPIRED')
    if set(event) != {'operation', 'observationId'} or event['operation'] != 'https-egress-a' or not isinstance(event['observationId'], str) or len(event['observationId']) > 128:
        raise ValueError('CLOSED_PROBE_REQUEST')
    start = time.monotonic()
    # Leave time for child termination, response encoding and the runtime.
    if context.get_remaining_time_in_millis() < 8000:
        raise RuntimeError('PROBE_EXECUTOR_DEADLINE_UNAVAILABLE')
    result = bounded_request()
    return {**result, 'at': now.isoformat(), 'durationMs': round((time.monotonic() - start) * 1000),
            'observationId': event['observationId'], 'requestId': context.aws_request_id, 'httpsRequests': 1}


if __name__ == '__main__':
    if sys.argv[1:] != ['--fixed-https']:
        raise SystemExit('CLOSED_CHILD_REQUEST')
    print(json.dumps(https_request()))
