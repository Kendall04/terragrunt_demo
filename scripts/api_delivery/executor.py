"""One blue/green algorithm for DEV, PROD and historical rollback.

Ports return observed facts. Acknowledgements never authorize draining. An
uncertain operation retains E2 ownership; this module has no takeover/retry API.
"""
from .model import require


class DeliveryFailure(RuntimeError):
    def __init__(self, state, safe=False):
        super().__init__(state)
        self.safe = safe


def deploy(port, image):
    initial = port.snapshot()
    old, new = initial['active'], initial['inactive']
    require(initial['routes'] == (old, new), 'initial routing is not exclusive')
    require(initial['inactive_count'] == 0 and initial['pending'] == 0, 'inactive service must be quiescent')
    previous_healthy = initial['active_count'] > 0
    if previous_healthy:
        port.client_ready()
    switched = False
    draining = False
    try:
        revision = port.register(new, image)
        port.start(new, revision)
        port.ready(new, revision, image, old)
        require(port.snapshot()['routes'] == (old, new), 'routing changed during readiness')
        # Mark BEFORE sending: a timeout can still have changed the listener.
        switched = True
        port.listener(new)
        require(port.snapshot()['routes'] == (new, new), 'listener effect unproved')
        port.candidate(old)
        require(port.snapshot()['routes'] == (new, old), 'candidate rule effect unproved')
        port.client_ready()
        port.drain_wait()
        # Both routes and the exact task cohort are re-read after the delay.
        require(port.snapshot()['routes'] == (new, old), 'routing changed before drain')
        port.still_ready(new, revision, image)
        port.journal('healthy-before-drain', dict(image=image, revision=revision, routes=[new, old]))
        draining = True
        port.stop(old)
        final = port.snapshot()
        require(final['routes'] == (new, old) and final['inactive_count'] == 0 and
                final['active_count'] == port.replicas and final['pending'] == 0, 'final state unproved')
        port.client_ready()
        return dict(color=new, revision=revision, per_task_ready=True, client_ready=True)
    except Exception as error:
        # Never restore an old color once draining may have started. Retain the
        # healthy new color, capacity and durable hold for explicit reconciliation.
        if draining:
            raise DeliveryFailure('POST_DRAIN_RECONCILIATION_REQUIRED') from error
        if switched and previous_healthy:
            try:
                routes = port.snapshot()['routes']
                require(routes in ((new, new), (new, old), (old, new), (old, old)), 'foreign route')
                port.old_ready(old, initial['active_revision'], initial['active_count'])
                if routes[0] != old:
                    try:
                        port.listener(old)
                    except Exception:
                        pass  # An absent ACK is settled only by the read below.
                routes = port.snapshot()['routes']
                require(routes[0] == old and routes[1] in (old, new), 'rollback listener unproved')
                if routes[1] != new:
                    try:
                        port.candidate(new)
                    except Exception:
                        pass
                require(port.snapshot()['routes'] == (old, new), 'rollback routes unproved')
                port.client_ready()
                # No stopping of the candidate here: an uncertain service call
                # or failed evidence write must remain diagnosable, not hidden.
                port.journal('traffic-restored', dict(routes=[old, new], revision=initial['active_revision']))
            except Exception as rollback_error:
                raise DeliveryFailure('TRAFFIC_RECONCILIATION_REQUIRED') from rollback_error
            raise DeliveryFailure('FAILED_TRAFFIC_RESTORED_HOLD_RETAINED') from error
        raise DeliveryFailure('PRE_SWITCH_HOLD_RETAINED') from error
