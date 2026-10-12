"""Protected WP5 execution orchestration over narrow installed runtime ports."""
import time
from . import contract as c
from .dev_down import check_data_consent


class Controller:
    def __init__(self, binding, protected, packages, engine, records):
        self.binding, self.protected = binding, protected
        self.packages, self.engine, self.records = packages, engine, records

    def run(self, request):
        value = c.request(self.binding, request)
        key = value['operation_id']
        retained = self.records.read(key)
        if retained is not None:
            c.require(retained['request_sha256'] == c.digest(c.canonical(value)), 'retry changed request')
            return retained
        installed = self.packages.verify(self.protected['installations'].get(value['revision']))
        value, layer = c.authorize(self.binding, value, self.protected, installed)
        needs_dev_consent = (self.protected['environment'] == 'dev'
                             and value['operation'] == 'teardown' and value['layer'] == 'data')
        if needs_dev_consent:
            check_data_consent(value, self.protected, int(time.time()))
        self.engine.prepare(installed, layer, value['parameters'])
        plan = self.engine.plan(destroy=value['operation'] == 'teardown')
        # Greenfield creation has no existing ECS installation to observe.
        # Require live quiescence only for teardown or runtime-side removal.
        needs_observation = value['operation'] == 'teardown' or any(
            x.get('type') in c.RUNTIME_FIELDS and 'delete' in x.get('change',{}).get('actions',[])
            for x in plan.get('resource_changes',[]))
        observation = self.engine.observe(self.protected['environment']) if needs_observation else None
        plan_hash = c.validate_plan(value, layer, plan, observation, self.protected['environment'])
        result = {'request_sha256': c.digest(c.canonical(value)), 'plan_sha256': plan_hash,
                  'operation_id': key, 'state': 'PLANNED' if value['operation'] == 'plan' else 'UNKNOWN'}
        exact = getattr(self.engine, 'exact_destroy', None)
        if exact is not None and exact.loaded is not None:
            result['exact_destroy_approval'] = exact.loaded['reference']
            result['binary_sha256'] = self.engine.destroy_seal['binary_sha256']
        # Retain the intent before mutation. A lost acknowledgement is UNKNOWN
        # and a repeated UUID cannot cause a second apply. E2 locking is separate.
        self.records.create(key, result)
        if value['operation'] == 'plan':return result
        try:
            if needs_dev_consent:
                check_data_consent(value, self.protected, int(time.time()))
            self.engine.apply(plan_hash)
        except Exception:return result
        # Success requires independent exact readback, not process exit alone.
        try:verified = self.engine.verify(plan_hash, layer, value['operation'])
        except Exception:return result
        if verified:
            result = {**result, 'state': 'SUCCESS'}
            self.records.complete(key, result)
        return result
