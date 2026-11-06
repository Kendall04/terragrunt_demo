"""One bounded HTTPS request from private subnet A; no AWS API calls."""
import datetime as dt
import ipaddress
import json
import os
import signal
import time
import urllib.request

TOTAL_DEADLINE_SECONDS = 6


class ProbeDeadline(Exception):
    """Not OSError: socket/urllib must not retry another address after expiry."""


def deadline_expired(signum, frame):
    raise ProbeDeadline('HTTPS_TOTAL_DEADLINE')


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError('REDIRECT_REFUSED')


def handler(event, context):
    now = dt.datetime.now(dt.timezone.utc)
    if now >= dt.datetime.fromisoformat(os.environ['EXPIRES_AT'].replace('Z', '+00:00')):
        raise ValueError('PROBE_WINDOW_EXPIRED')
    if set(event) != {'operation', 'observationId'} or event['operation'] != 'https-egress-a' or not isinstance(event['observationId'], str) or len(event['observationId']) > 128:
        raise ValueError('CLOSED_PROBE_REQUEST')
    start = time.monotonic()
    # Lambda runs this handler on the Linux main thread. A socket timeout is per
    # address/read, not a bound on DNS + all connections + TLS + response body.
    # Fail as an executor error if this process cannot safely arm its own timer.
    if context.get_remaining_time_in_millis() < 8000 or signal.getitimer(signal.ITIMER_REAL) != (0.0, 0.0):
        raise RuntimeError('PROBE_EXECUTOR_DEADLINE_UNAVAILABLE')
    previous = signal.signal(signal.SIGALRM, deadline_expired)
    try:
        signal.setitimer(signal.ITIMER_REAL, TOTAL_DEADLINE_SECONDS)
        with urllib.request.build_opener(NoRedirect()).open('https://checkip.amazonaws.com/', timeout=4) as response:
            if response.status != 200:
                raise ValueError('HTTP_STATUS')
            public = str(ipaddress.IPv4Address(response.read(65).decode('ascii').strip()))
        result = {'status': 'HTTPS_SUCCESS', 'egressIp': public}
    except Exception as error:
        result = {'status': 'HTTPS_FAILED', 'errorType': type(error).__name__}
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous)
    return {**result, 'at': now.isoformat(), 'durationMs': round((time.monotonic() - start) * 1000),
            'observationId': event['observationId'], 'requestId': context.aws_request_id, 'httpsRequests': 1}
