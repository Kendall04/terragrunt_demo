"""Offline pagination/correlation regressions; no SDK, network or process calls."""
import copy
import hashlib
import json
import sys
import unittest

import collector
import evidence_export as export


def audit(event, args):
    if event.startswith('socket.') or event in ('subprocess.Popen', 'os.system', 'os.posix_spawn'):
        raise AssertionError('EXTERNAL_EFFECT_FORBIDDEN')


sys.addaudithook(audit)
CID = '12345678-1234-1234-1234-123456789abc'
RID = '87654321-4321-4321-4321-cba987654321'
INSTANCE = 'i-' + 'a' * 17


def config():
    run = 'ecs-sentinel-ssmdiag-r20261024d1'
    return {'run': run, 'account': '341936017254', 'region': 'us-east-1',
            'expires_at': '2026-10-25T20:37:02Z', 'log_group': '/ecs/ssm-diagnostic/' + run,
            'role': run + '-node', 'source_sha256': 'a' * 64}


def event(sequence=0, large=False):
    c = config()
    line = {'lineSha256': 'b' * 64, 'codes': ['AccessDeniedException'],
            'actions': ['GetDocument'], 'commandIds': [CID], 'requestIds': [RID]}
    if large:
        line['commandIds'] = [CID] * 3
        line['requestIds'] = [RID] * 3
    row = {'schemaVersion': 1, 'diagnosticOnly': True, 'run': c['run'],
           'account': c['account'], 'region': c['region'], 'nodeRole': c['role'],
           'instanceId': INSTANCE, 'atUtc': '2026-10-24T21:20:00+00:00',
           'sequence': sequence, 'agentService': {'ActiveState': 'active'},
           'agentVersion': '3.3.5390.0',
           'logs': [{'source': i, 'status': 'READ',
                     'rows': [copy.deepcopy(line) for _ in range(32 if large else 1)]}
                    for i in range(2)],
           'rawLogsExported': False, 'sourceSha256': c['source_sha256']}
    return {'eventId': str(sequence), 'timestamp': sequence,
            'ingestionTime': sequence + 1, 'message': json.dumps(row)}


class Pages:
    def __init__(self, *pages):
        self.pages, self.calls = list(pages), []

    def __call__(self, **args):
        self.calls.append(args)
        item = self.pages.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def capture(pages, **limits):
    return export.export_boot_events(pages, config(), INSTANCE, **limits)


class ExportTests(unittest.TestCase):
    def test_follows_multiple_and_empty_pages_without_exporting_tokens_or_raw_fields(self):
        first = event()
        first['untrustedExtra'] = 'PRIVATE'
        p = Pages({'events': [first], 'nextToken': 'PRIVATE-TOKEN-1'},
                  {'events': [], 'nextToken': 'PRIVATE-TOKEN-2'}, {'events': [event(1)]})
        r = capture(p)
        self.assertTrue(r['Capture']['PaginationExhausted'])
        self.assertFalse(r['TruncatedByApi'])
        self.assertEqual(r['Capture']['PagesRead'], 3)
        self.assertEqual(len(r['Events']), 2)
        self.assertNotIn('nextToken', p.calls[0])
        self.assertEqual(p.calls[1]['nextToken'], 'PRIVATE-TOKEN-1')
        self.assertEqual(p.calls[2]['nextToken'], 'PRIVATE-TOKEN-2')
        self.assertEqual(p.calls[2]['limit'], 119)
        self.assertNotIn('PRIVATE', json.dumps(r))
        self.assertNotIn('message', r['Events'][0])

    def test_repeated_token_stops_and_does_not_claim_exhaustion(self):
        p = Pages({'events': [event()], 'nextToken': 'same'},
                  {'events': [event(1)], 'nextToken': 'same'})
        r = capture(p)
        self.assertEqual(len(p.calls), 2)
        self.assertEqual(r['Capture']['StopReason'], 'REPEATED_TOKEN')
        self.assertTrue(r['TruncatedByApi'])

    def test_empty_unique_token_pages_are_also_bounded(self):
        p = Pages(*[{'events': [], 'nextToken': str(i)} for i in range(3)])
        r = capture(p, max_pages=3)
        self.assertEqual(len(p.calls), 3)
        self.assertEqual(r['Capture']['StopReason'], 'PAGE_LIMIT')
        self.assertFalse(r['Capture']['PaginationExhausted'])

    def test_120_limit_does_not_fetch_again_but_exact_end_is_complete(self):
        p = Pages({'events': [event(i) for i in range(119)], 'nextToken': 'one'},
                  {'events': [event(119)], 'nextToken': 'two'})
        r = capture(p)
        self.assertEqual(len(r['Events']), 120)
        self.assertEqual(len(p.calls), 2)
        self.assertEqual(p.calls[-1]['limit'], 1)
        self.assertEqual(r['Capture']['StopReason'], 'EVENT_LIMIT')
        complete = capture(Pages({'events': [event(i) for i in range(120)]}))
        self.assertTrue(complete['Capture']['PaginationExhausted'])

    def test_two_mib_includes_entire_serialized_envelope(self):
        p = Pages({'events': [event(i, large=True) for i in range(120)]})
        r = capture(p)
        self.assertEqual(r['Capture']['StopReason'], 'BYTE_LIMIT')
        self.assertLess(len(r['Events']), 120)
        size = len(export.canonical(r))
        self.assertLessEqual(size, 2 * 1024 * 1024)
        self.assertEqual(size, r['Capture']['SerializedBytes'])
        self.assertFalse(r['Capture']['PaginationExhausted'])

    def test_duplicate_event_is_not_double_counted_and_conflict_fails_closed(self):
        p = Pages({'events': [event()], 'nextToken': 'one'},
                  {'events': [event(), event(1)]})
        r = capture(p)
        self.assertEqual(len(r['Events']), 2)
        self.assertEqual(r['Capture']['DuplicateEventsSkipped'], 1)
        changed = event()
        changed['timestamp'] += 1
        with self.assertRaisesRegex(ValueError, 'EXPORT_EVENT_ID_CONFLICT'):
            capture(Pages({'events': [event(), changed]}))

    def test_fetch_failure_is_partial_no_retry_and_never_exports_exception_text(self):
        p = Pages({'events': [event()], 'nextToken': 'one'}, RuntimeError('PRIVATE'))
        r = capture(p)
        self.assertEqual(len(p.calls), 2)
        self.assertEqual(len(r['Events']), 1)
        self.assertEqual(r['Capture']['StopReason'], 'FETCH_FAILED_NO_RETRY')
        self.assertTrue(r['TruncatedByApi'])
        self.assertNotIn('PRIVATE', json.dumps(r))

    def test_missing_fields_foreign_records_oversized_input_and_limits_fail_closed(self):
        untouched = Pages()
        with self.assertRaisesRegex(ValueError, 'SCOPE'):
            export.export_boot_events(untouched, config() | {'log_group': '/other'}, INSTANCE)
        self.assertEqual(untouched.calls, [])
        for field in ('logs', 'sourceSha256'):
            e = event()
            row = json.loads(e['message'])
            del row[field]
            e['message'] = json.dumps(row)
            with self.assertRaises((ValueError, KeyError)):
                capture(Pages({'events': [e]}))
        e = event()
        row = json.loads(e['message'])
        row['instanceId'] = 'i-' + 'b' * 17
        e['message'] = json.dumps(row)
        with self.assertRaisesRegex(ValueError, 'EXPORT_INSTANCE'):
            capture(Pages({'events': [e]}))
        e['message'] = 'x' * 32769
        with self.assertRaisesRegex(ValueError, 'EXPORT_MESSAGE_BOUND'):
            capture(Pages({'events': [e]}))
        for limits in ({'max_events': 121}, {'max_bytes': 2097153}, {'max_pages': 129}):
            with self.assertRaisesRegex(ValueError, 'EXPORT_LIMITS'):
                capture(Pages(), **limits)


class CorrelationTests(unittest.TestCase):
    def test_codes_actions_and_spaced_id_only_continuations_survive_without_raw_text(self):
        lines = ['GetDocument AccessDeniedException PRIVATE',
                 'status code: 403, request id: ' + RID + ' PRIVATE',
                 'command ID: ' + CID + ' PRIVATE']
        rows = collector.sanitize('\n'.join(lines).encode())
        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[0]['actions'], ['GetDocument'])
        self.assertEqual(rows[0]['codes'], ['AccessDeniedException'])
        self.assertEqual(rows[1]['requestIds'], [RID])
        self.assertEqual(rows[1]['codes'], [])
        self.assertEqual(rows[1]['actions'], [])
        self.assertEqual(rows[2]['commandIds'], [CID])
        self.assertEqual(rows[2]['requestIds'], [])
        self.assertEqual(rows[1]['lineSha256'], hashlib.sha256(lines[1].encode()).hexdigest())
        self.assertNotIn('PRIVATE', json.dumps(rows))
        # Adjacent summaries remain separate: association with an error is not inferred.
        self.assertEqual(rows[0]['requestIds'], [])

    def test_absent_ids_remain_absent_and_unlabelled_or_malformed_values_do_not_escape(self):
        rows = collector.sanitize(('AccessDenied GetDocument password=PRIVATE uuid=' + CID).encode())
        self.assertEqual(rows[0]['requestIds'], [])
        self.assertEqual(rows[0]['commandIds'], [])
        self.assertEqual(collector.sanitize(b'request id: PRIVATE commandId: not-a-uuid'), [])
        self.assertEqual(collector.sanitize(b'unknown private error'), [])
        for label, key, value in [('requestId', 'requestIds', RID), ('REQUEST ID', 'requestIds', RID),
                                  ('commandId', 'commandIds', CID)]:
            self.assertEqual(collector.sanitize((label + ': ' + value).encode())[0][key], [value])


if __name__ == '__main__':
    unittest.main()
