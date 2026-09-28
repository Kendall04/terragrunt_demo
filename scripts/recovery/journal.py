"""Bounded recovery evidence, using WP4B's immutable storage/effect contract.

No SDKs or public dispatcher. Installed controllers supply closed domain actions.
WP4D must authenticate storage, observations and single-runner ownership.
"""
import copy
from scripts.normal_delivery import authorization as a
from scripts.normal_delivery import delivery as d


class Journal:
    read = d.Delivery.read
    put = d.Delivery.put

    def __init__(self, environment, kind, records, runtime, stages):
        a.require(environment in ('dev', 'prod'))
        a.require(kind in ('emergency', 'cleanup', 'assign_eip', 'change_rt', 'disable_sdc'))
        a.require(isinstance(records, d.Records))
        self.env = environment + '/recovery/' + kind
        self.records, self.runtime = records, runtime
        self.stages = tuple(stages)

    def attempted(self, operation):
        # Never consult a damaged retained operation to discover side effects.
        try: d.identity(operation)
        except Exception: return False
        for stage in self.stages:
            try:
                if self.read(operation + '/' + stage + '/attempt', True) is not None:
                    return True
            except Exception:
                return True
        return False

    def accept(self, operation, request, prepare):
        key = operation + '/intent'
        retained = self.read(key, True)
        if retained is None:
            if self.attempted(operation): raise d.Uncertain()
            now = self.runtime.now()
            a.require(type(now) is int)
            body = dict(operation=operation, namespace=self.env, request=request,
                        started=now, deadline=now + 600, domain=prepare())
            retained = self.put(key, dict(body=body, sha256=a.sha(a.canonical(body))))
        try:
            a.keys(retained, ('body', 'sha256'))
            body = retained['body']
            a.keys(body, ('operation', 'namespace', 'request', 'started', 'deadline', 'domain'))
            a.exact(retained['sha256'], a.sha(a.canonical(body)), 'intent digest')
            a.exact(body['namespace'], self.env, 'namespace')
            a.exact(body['operation'], operation, 'operation')
            a.require(type(body['domain']) is dict and type(body['request']) is dict)
            a.require(type(body['started']) is int and type(body['deadline']) is int
                      and body['deadline'] == body['started'] + 600)
        except Exception:
            raise d.JournalError(key) from None
        # A valid protected operation is matched, never rebuilt from retry data.
        a.exact(body['request'], request, 'retry request')
        return copy.deepcopy(body)

    def bounded(self, op):
        now = self.runtime.now()
        a.require(type(now) is int and op['started'] <= now < op['deadline'])

    def plan(self, op, stage, request):
        return dict(token=self.env + '/' + op['operation'] + '/' + stage,
                    operation_sha256=a.sha(a.canonical(op)), request=request)

    def validate_effect(self, value, plan):
        d.Delivery.check_effect(self, value, plan['token'], plan['request'])
        if value['state'] == 'APPLIED':
            a.exact(value['result'], plan['request'], 'effect result')
        return value

    def effect(self, op, stage, request, mutate=False, guard=None):
        key = op['operation'] + '/' + stage
        plan = self.plan(op, stage, request)
        saved = self.read(key + '/plan', True)
        attempt = self.read(key + '/attempt', True)
        try:
            if saved is not None: a.exact(saved, plan, 'stage plan')
            if attempt is not None:
                a.exact(attempt, dict(token=plan['token'], plan_sha256=a.sha(a.canonical(plan))), 'attempt')
                a.require(saved is not None)
        except Exception:
            raise d.JournalError(key) from None
        if attempt is not None:
            pass
        elif not mutate:
            return None
        else:
            for suffix in ('observed', 'reconciled'):
                if self.read(key + '/' + suffix, True) is not None:
                    raise d.JournalError(key)
            self.put(key + '/plan', plan)
            self.bounded(op)
            guard()
            self.put(key + '/attempt', dict(token=plan['token'], plan_sha256=a.sha(a.canonical(plan))))
            # Fresh guard after persistence. A known pre-call rejection is FAILURE.
            self.preparing = stage
            self.bounded(op)
            guard()
            self.bounded(op)
            self.preparing = None
            try: self.runtime.mutate(stage, plan['token'], copy.deepcopy(request), op['deadline'])
            except Exception: pass
        for suffix in ('reconciled', 'observed'):
            try:
                value = self.read(key + '/' + suffix, True)
                if value is not None:
                    self.validate_effect(value, plan)
                    if value['state'] == 'APPLIED': return value
                    if value['state'] == 'ABSENT': raise d.Absent()
            except d.Absent: raise
            except Exception: pass
        try:
            value = self.runtime.effect(plan['token'], self.runtime.now() + 30)
            self.validate_effect(value, plan)
            if value['state'] == 'UNKNOWN': raise d.Uncertain()
            suffix = 'observed' if self.records.read(self.env + '/' + key + '/observed') is None else 'reconciled'
            self.put(key + '/' + suffix, value)
            if value['state'] == 'ABSENT': raise d.Absent()
            return value
        except d.Absent: raise
        except Exception: raise d.Uncertain() from None

    def run(self, operation, raw, domain):
        result = self.execute(operation, raw, domain)
        try:
            d.identity(operation)
            outcome = dict(result, operation=operation, namespace=self.env)
            self.put(operation + '/outcomes/' + a.sha(a.canonical(outcome)), outcome)
        except Exception:
            # Failure to record an outcome cannot prove a runtime effect.
            pass
        return result

    def execute(self, operation, raw, domain):
        """Domain supplies selection, exact stages, fresh guards and final proof.

        Acknowledgements never prove effects. Retry reconciles before authorization.
        ABSENT is terminal under the accepted no-resend contract.
        """
        op = None
        self.preparing = None
        reconciled = False
        try:
            d.identity(operation)
            request = a.decode(raw)
            a.keys(request, ())
            op = self.accept(operation, request, domain.prepare)
            try:
                domain.validate(op['domain'])
                actions = domain.actions(op['domain'])
                a.require(type(actions) is dict and set(actions) <= set(self.stages))
                for stage in set(self.stages) - set(actions):
                    a.require(self.read(operation + '/' + stage + '/attempt', True) is None)
            except Exception:
                raise d.JournalError(operation + '/intent') from None
            effects = {}
            for stage, request in actions.items():
                value = self.effect(op, stage, request)
                if value is not None: effects[stage] = value
            reconciled = True
            for stage, request in actions.items():
                if stage not in effects:
                    effects[stage] = self.effect(op, stage, request, True,
                        lambda: domain.guard(op, stage, effects))
            self.bounded(op)
            final = domain.final(op, effects)
            # Revalidate every effect at receipt closure; never copy raw journal data.
            for stage, request in actions.items():
                effects[stage] = self.effect(op, stage, request)
                a.require(effects[stage] is not None and effects[stage]['state'] == 'APPLIED')
            receipt = dict(status='SUCCESS', namespace=self.env, operation=operation,
                           intent_sha256=a.sha(a.canonical(op)), effects=effects, final=final)
            self.put(operation + '/receipts/' + a.sha(a.canonical(receipt)), receipt)
            return receipt
        except d.Absent:
            return dict(status='FAILURE', reason='authoritative absence; no resend')
        except d.Uncertain:
            return dict(status='UNCERTAIN')
        except d.JournalError:
            return dict(status='UNCERTAIN' if self.attempted(operation) else 'FAILURE')
        except Exception:
            # Domain errors are definitive only before any unresolved side effect.
            # Once all attempts reconcile, authorization rejection can be definitive.
            uncertain = not reconciled and self.attempted(operation)
            if op is not None and self.preparing != 'switch':
                try: uncertain |= self.read(operation + '/switch/attempt', True) is not None
                except Exception: uncertain = True
            return dict(status='UNCERTAIN' if uncertain else 'FAILURE')
