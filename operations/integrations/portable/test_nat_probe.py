"""Real POSIX deadline tests; no public network or AWS calls."""
import datetime as dt
import os
import signal
import socket
import time
import unittest
from unittest.mock import patch
import nat_probe as n


class Context:
    aws_request_id = 'local-deadline-test'

    def get_remaining_time_in_millis(self):
        return 10000


class ProbeTests(unittest.TestCase):
    def setUp(self):
        expiry = (dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=1)).isoformat()
        self.env = patch.dict(os.environ, {'EXPIRES_AT': expiry})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.event = {'operation': 'https-egress-a', 'observationId': 'test-one'}

    def test_actual_deadline_interrupts_blocked_socket_before_lambda_timeout(self):
        # A real blocked local read models a peer that never completes TLS/body.
        # The fault is local; this is not evidence of an AWS NAT incident.
        a, b = socket.socketpair()
        self.addCleanup(a.close)
        self.addCleanup(b.close)
        previous = signal.getsignal(signal.SIGALRM)
        start = time.monotonic()
        with patch.object(n, 'TOTAL_DEADLINE_SECONDS', 0.2), patch.object(n.urllib.request, 'build_opener') as factory:
            factory.return_value.open.side_effect = lambda *args, **kwargs: a.recv(1)
            result = n.handler(self.event, Context())
            self.assertEqual(factory.return_value.open.call_count, 1)
        self.assertEqual(result['status'], 'HTTPS_FAILED')
        self.assertEqual(result['errorType'], 'ProbeDeadline')
        self.assertLess(time.monotonic() - start, 2)
        self.assertGreaterEqual(result['durationMs'], 150)
        self.assertEqual(signal.getitimer(signal.ITIMER_REAL), (0.0, 0.0))
        self.assertIs(signal.getsignal(signal.SIGALRM), previous)
        self.assertFalse(issubclass(n.ProbeDeadline, OSError))

    def test_success_is_correlated_and_next_invocation_has_no_timer(self):
        with patch.object(n.urllib.request, 'build_opener') as factory:
            response = factory.return_value.open.return_value.__enter__.return_value
            response.status = 200
            response.read.return_value = b'192.0.2.1\n'
            for _ in range(2):
                result = n.handler(self.event, Context())
                self.assertEqual(result['status'], 'HTTPS_SUCCESS')
                self.assertEqual(result['egressIp'], '192.0.2.1')
                self.assertEqual(result['observationId'], 'test-one')
                self.assertEqual(result['httpsRequests'], 1)
                self.assertEqual(signal.getitimer(signal.ITIMER_REAL), (0.0, 0.0))
            factory.return_value.open.assert_called_with('https://checkip.amazonaws.com/', timeout=4)
            response.read.assert_called_with(65)

    def test_executor_short_budget_is_not_a_false_network_failure(self):
        with patch.object(Context, 'get_remaining_time_in_millis', return_value=7000), patch.object(n.urllib.request, 'build_opener') as factory:
            with self.assertRaisesRegex(RuntimeError, 'DEADLINE_UNAVAILABLE'):
                n.handler(self.event, Context())
            factory.assert_not_called()

    def test_arbitrary_destination_and_redirect_are_rejected(self):
        with self.assertRaisesRegex(ValueError, 'CLOSED_PROBE_REQUEST'):
            n.handler({**self.event, 'url': 'https://example.invalid/'}, Context())
        with self.assertRaisesRegex(ValueError, 'REDIRECT_REFUSED'):
            n.NoRedirect().redirect_request(None, None, 302, '', {}, 'https://example.invalid/')


if __name__ == '__main__':
    unittest.main()
