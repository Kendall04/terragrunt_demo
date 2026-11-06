"""Real child-process deadline tests; no public network or AWS calls."""
import datetime as dt
import json
import os
import subprocess
import sys
import time
import unittest
from unittest.mock import patch
import nat_probe as n

class Context:
    aws_request_id = 'local-deadline-test'
    def get_remaining_time_in_millis(self): return 10000

class ProbeTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {'EXPIRES_AT': (dt.datetime.now(dt.timezone.utc)+dt.timedelta(hours=1)).isoformat()})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.event = {'operation': 'https-egress-a', 'observationId': 'test-one'}

    def test_real_child_deadline_kills_and_reaps_blocked_executor(self):
        # Real local process, independent of Python signal delivery. No AWS outage.
        original = subprocess.Popen
        children = []
        def blocked(*args, **kwargs):
            child = original([sys.executable, '-I', '-S', '-c', 'import time; time.sleep(60)'], **kwargs)
            children.append(child)
            return child
        start = time.monotonic()
        with patch.object(n, 'TOTAL_DEADLINE_SECONDS', .2), patch.object(n.subprocess, 'Popen', side_effect=blocked):
            result = n.handler(self.event, Context())
        self.assertEqual(result['status'], 'HTTPS_FAILED')
        self.assertEqual(result['errorType'], 'HttpsTotalDeadline')
        self.assertLess(time.monotonic()-start, 3)
        self.assertGreaterEqual(result['durationMs'], 150)
        self.assertEqual(len(children), 1)
        self.assertIsNotNone(children[0].poll())

    def test_child_uses_closed_command_and_no_aws_credentials(self):
        with patch.object(n.subprocess, 'Popen') as factory:
            child = factory.return_value.__enter__.return_value
            child.communicate.return_value = (json.dumps({'status':'HTTPS_SUCCESS','egressIp':'192.0.2.1'}).encode(), None)
            child.returncode = 0
            for _ in range(2):
                result = n.handler(self.event, Context())
                self.assertEqual(result['status'], 'HTTPS_SUCCESS')
                self.assertEqual(result['observationId'], 'test-one')
                self.assertEqual(result['httpsRequests'], 1)
            self.assertEqual(factory.call_args.args[0], [sys.executable, '-I', '-S', os.path.abspath(n.__file__), '--fixed-https'])
            self.assertEqual(factory.call_args.kwargs['env'], {})
            self.assertNotIn('shell', factory.call_args.kwargs)

    def test_fixed_https_request_validates_status_ip_and_bounds_response(self):
        with patch.object(n.urllib.request, 'build_opener') as factory:
            response = factory.return_value.open.return_value.__enter__.return_value
            response.status = 200
            response.read.return_value = b'192.0.2.1\n'
            self.assertEqual(n.https_request(), {'status':'HTTPS_SUCCESS','egressIp':'192.0.2.1'})
            factory.return_value.open.assert_called_with('https://checkip.amazonaws.com/', timeout=4)
            response.read.assert_called_with(65)
            response.status = 503
            self.assertEqual(n.https_request()['status'], 'HTTPS_FAILED')
            response.status = 200
            response.read.return_value = b'not-an-ip'
            self.assertEqual(n.https_request()['status'], 'HTTPS_FAILED')

    def test_executor_short_budget_and_child_crash_are_unknown_not_network_failure(self):
        with patch.object(Context, 'get_remaining_time_in_millis', return_value=7000), patch.object(n.subprocess, 'Popen') as factory:
            with self.assertRaisesRegex(RuntimeError, 'DEADLINE_UNAVAILABLE'): n.handler(self.event, Context())
            factory.assert_not_called()
        with patch.object(n.subprocess, 'Popen') as factory:
            child = factory.return_value.__enter__.return_value
            child.communicate.return_value = (b'', None)
            child.returncode = 1
            with self.assertRaisesRegex(RuntimeError, 'CHILD_UNAVAILABLE'): n.handler(self.event, Context())

    def test_arbitrary_destination_and_redirect_are_rejected(self):
        with self.assertRaisesRegex(ValueError, 'CLOSED_PROBE_REQUEST'): n.handler({**self.event,'url':'https://example.invalid/'}, Context())
        with self.assertRaisesRegex(ValueError, 'REDIRECT_REFUSED'): n.NoRedirect().redirect_request(None,None,302,'',{},'https://example.invalid/')

if __name__ == '__main__': unittest.main()
