"""DEV NAT guards tolerate only progress by the other two fixed duties.

Selected only by the three DEV bundles. No dispatch, storage, retry or IAM port.
"""
from scripts.normal_delivery import authorization as a


def controller(base):
    class DevNat(base):
        def guard(self, op, stage, effects):
            a.require(self.environment == 'dev' and stage == self.action)
            current = self.context()  # Full authenticated membership validation.
            a.exact(current['membership'], op['domain']['membership'],
                    'fresh DEV NAT membership')
            field = {'assign_eip': 'association_eni',
                     'change_rt': 'default_route_eni',
                     'disable_sdc': 'source_dest_check'}[self.action]
            a.exact(current['state'][field], op['domain']['state'][field],
                    'fresh DEV NAT action state')
            if self.action == 'change_rt':
                a.exact(current['route_exists'], op['domain']['route_exists'],
                        'fresh DEV default route existence')
    return DevNat
