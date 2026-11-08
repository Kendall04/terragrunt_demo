"""E15-G narrow whole-DEV invocation; no public gateway or new authority.

The first exact edge request owns E2; immutable child requests are separately
approved under WP5/E15-C/D. A single invocation retains that original grant.
Interrupted intents cannot resume, replace owners, regenerate plans or resend.
Installed NAT closure is still absent: installed whole DOWN fails closed.
"""
import copy
from . import contract as c, dev_down as down, ecs_quiescence as ecs
from .controller import Controller
from scripts import environment_mutation as e


class WholeGuard:
    """Separate domain evidence throughout the original operation interval."""
    def __init__(self, operation, ecs_protocol, nat_protocol, residual):
        from scripts.nat.quiescence import Quiescence as NAT
        c.require(type(operation) is Operation and type(ecs_protocol) is ecs.Quiescence
            and ecs_protocol.authority is operation.authority
            and ecs_protocol.selected == ecs.scope(operation.requests[0], operation.protected),
            'original ECS operation correlation')
        c.require(type(nat_protocol) is NAT and nat_protocol.authority is operation.authority
            and nat_protocol.owner == operation.owner
            and nat_protocol.scope == down.scope(operation.requests[-1], operation.protected),
            'separate exact global NAT protocol under original owner')
        c.require(isinstance(residual, Residual), 'protected residual observation port')
        self.operation, self.ecs, self.nat, self.residual = operation, ecs_protocol, nat_protocol, residual
        self.prepared = False

    def prepare(self):
        # NAT must establish closure before any destructive layer. The current
        # concrete NAT protocol denies here, preserving its UNKNOWN evidence.
        self.nat.require_network_teardown()
        self.ecs.drain_until_quiet()
        self.prepared = True

    def require(self, stage, phase):
        c.require(self.prepared, 'both domains required before destruction')
        self.operation.check()
        self.nat.require_network_teardown()
        if stage in ('data', 'global') or (stage == 'platform' and phase == 'post-readback'):
            evidence = self.ecs.require_terminal_handoff(stage)
        elif stage == 'platform' and phase == 'pre-dispatch':
            evidence = self.ecs.require_predelete_seal()
        else:
            evidence = self.ecs.check()
        self.operation.check()
        return evidence


class Residual:
    """Internal protected exhaustive service readback, never local E15 notes.

    Installation must independently attribute ownership and enumerate implicit
    EC2/EBS/ENI/tasks/routes and unexpected DEV resources. No live adapter exists.
    """
    def observe(self, manifest, owner):
        raise ecs.Blocked('E15G_RESIDUAL_REMOTE_INVENTORY_UNINSTALLED')


def residual_result(observed, manifest, owner):
    c.keys(observed, ('operation_sha256', 'owner', 'resources', 'complete'), 'closed residual evidence')
    c.require(observed['operation_sha256'] == c.digest(c.canonical(manifest))
        and observed['owner'] == owner and observed['complete'] is True, 'complete original residual inventory')
    c.require(type(observed['resources']) is list and bool(observed['resources']), 'nonempty exhaustive inventory')
    expected = set(manifest['residual_keys'])
    seen = set()
    for item in observed['resources']:
        c.keys(item, ('key', 'disposition', 'evidence_sha256'), 'closed residual item')
        c.require(type(item['key']) is str and item['key'] not in seen, 'unique residual identity')
        seen.add(item['key'])
        c.require(item['disposition'] in ('ABSENT', 'RETAINED', 'PRESENT', 'UNKNOWN_OWNERSHIP',
            'NOT_QUERIED', 'READBACK_FAILED', 'PARTIAL'), 'explicit residual disposition')
        c.require(type(item['evidence_sha256']) is str and len(item['evidence_sha256']) == 64
            and all(x in '0123456789abcdef' for x in item['evidence_sha256']), 'readback evidence digest')
        c.require(item['disposition'] == ('RETAINED' if item['key'] in manifest['retained_keys'] else 'ABSENT'),
            'runtime residual unverified; potential continuing billing')
    c.require(expected <= seen, 'all installed and implicit resources queried')
    return copy.deepcopy(observed)


class Operation:
    """One-shot internal WP5 controller composition, never a serialized grant.

    Authority is the unmodified E2 primitive. Child authority exists only through
    this instance, an exact durable manifest, original owner, ordered current
    stage, and each existing independently protected WP5 approval. There is no
    release between layers and no re-entry after any interrupted attempt.
    """
    def __init__(self, requests, protected, authority, records, clock):
        c.require(type(requests) is list and len(requests) == len(down.DOWN), 'five exact stage requests')
        self.requests, self.protected = copy.deepcopy(requests), copy.deepcopy(protected)
        self.authority, self.records, self.clock = authority, records, clock
        c.require([x['layer'] for x in self.requests] == list(down.DOWN), 'exact reverse dependency order')
        c.require(len({x['operation_id'] for x in self.requests}) == len(down.DOWN)
            and len({x['revision'] for x in self.requests}) == 1, 'distinct stage approvals, one installed revision')
        for request in self.requests:
            down.scope(request, self.protected)
            c.authorize(ecs.BINDING, request, self.protected,
                        self.protected['installations'][request['revision']])
        c.require(type(authority) is e.Authority and authority.binding == ecs.BINDING
            and authority.operation == self.requests[0]['operation_id']
            and authority.request_sha256 == c.digest(c.canonical(self.requests[0]))
            and authority.store.environment == 'dev' and authority.store.selected == 'application'
            and authority.store.bucket == f'e1-wp4-dev-{protected["account"]}-{protected["region"]}',
            'one original exact DEV E2 context')
        c.require(records.bucket == self.protected['layers']['edge']['backend']['bucket']
            and records.prefix == 'operations/' + ecs.BINDING + '/', 'existing protected WP5 operation records')
        # SQL consent is required before any whole DOWN mutation, then again at
        # the existing data dispatch boundary. No backup policy is introduced.
        down.check_data_consent(self.requests[3], self.protected, self.clock())
        self.owner = None
        self.index = 0
        self.running = False
        self.guard = None
        self.key = authority.operation + '/whole-down'
        # Installed membership is expanded, unlike E15's local declaration
        # inventory. Implicit/orphan dimensions also require independent reads.
        retained = ['retained:backend-state-locking', 'retained:security-root',
            'retained:shared-secrets', 'retained:journals-evidence',
            'retained:ecr-provenance', 'retained:approved-persistent']
        implicit = ['related:nat-instances', 'related:sql-root-ebs', 'related:service-enis',
            'related:running-tasks', 'related:nat-default-routes', 'related:unexpected-dev']
        members = [layer + '#' + address for layer in down.DOWN
                   for address in self.protected['layers'][layer]['addresses']]
        self.manifest = dict(schema='E15G_WHOLE_DOWN_V1', environment='dev',
            account=protected['account'], region=protected['region'], binding=ecs.BINDING,
            operation_id=authority.operation, requests=self.requests,
            configuration_sha256=c.digest(c.canonical(self.protected)), order=list(down.DOWN),
            residual_keys=sorted(members + implicit + retained), retained_keys=sorted(retained))

    def retain(self, key, value):
        prior = self.records.read(key)
        if prior is None:
            try:self.records.create(key, value)
            except Exception:pass
            prior = self.records.read(key)
        c.require(prior == value, 'exact durable whole-operation evidence; never blind write retry')

    def check(self):
        self.authority._check()
        c.require(self.owner is not None and self.authority.value == self.owner and self.running,
                  'original uninterrupted invocation only')
        intent = dict(manifest=self.manifest, owner=self.owner, state='UNKNOWN')
        c.require(self.records.read(self.key) == intent, 'immutable original operation manifest')
        c.require(c.digest(c.canonical(self.protected)) == self.manifest['configuration_sha256'],
                  'protected configuration unchanged')
        for value in self.requests[:self.index]:
            verified = self.records.read(self.key + '/stages/' + value['layer'] + '/verified')
            c.require(type(verified) is dict and verified.get('owner') == self.owner
                and verified.get('request_sha256') == c.digest(c.canonical(value))
                and verified.get('state') == 'VERIFIED' and verified.get('result', {}).get('state') == 'SUCCESS',
                'prior dependent stage must have durable exact verification')

    def owns_request(self, value, protected, authority):
        self.check()
        c.require(authority is self.authority and protected == self.protected
            and self.index < len(self.requests) and value == self.requests[self.index],
            'exact currently ordered child request under original E2')
        c.authorize(ecs.BINDING, value, protected, protected['installations'][value['revision']])
        return copy.deepcopy(self.owner)

    def require(self, value, protected, authority, phase):
        self.owns_request(value, protected, authority)
        c.require(phase in ('pre-dispatch', 'post-readback') and type(self.guard) is WholeGuard,
                  'internal whole-operation domain guard')
        proof = self.guard.require(value['layer'], phase)
        self.check()
        record = dict(owner=self.owner, layer=value['layer'], phase=phase,
            request_sha256=c.digest(c.canonical(value)), evidence=proof, state='UNKNOWN')
        self.retain(self.key + '/evidence/' + c.digest(c.canonical(record)), record)
        return proof

    def run(self, packages, engine_factory, guard_factory):
        c.require(not self.running and self.owner is None, 'whole DOWN cannot re-enter or resume')
        self.authority._check()
        c.require(self.records.read(self.key) is None, 'interrupted operation cannot resume')
        c.require(all(self.records.read(value['operation_id']) is None for value in self.requests),
                  'stage UUID already used; no legacy layer-result substitution')
        self.owner = copy.deepcopy(self.authority.value)
        self.running = True
        self.retain(self.key, dict(manifest=self.manifest, owner=self.owner, state='UNKNOWN'))
        result = dict(operation_id=self.authority.operation, state='UNKNOWN', completed_layers=[],
                      residual='NOT_QUERIED', potential_continuing_billing=True)
        try:
            self.guard = guard_factory(self)
            c.require(type(self.guard) is WholeGuard, 'installed domain composition only')
            self.guard.prepare();self.check()
            for index, value in enumerate(self.requests):
                self.index = index
                self.check()
                layer = value['layer']
                # Intent makes a crash before or after dispatch non-replayable.
                self.retain(self.key + '/stages/' + layer, dict(owner=self.owner, request=value, state='UNKNOWN'))
                engine = engine_factory(value, self)
                c.require(engine.authority is self.authority and engine.down_operation is self
                    and engine.request == value and engine.protected == self.protected, 'exact installed stage engine')
                self.require(value, self.protected, self.authority, 'pre-dispatch')
                stage = Controller(ecs.BINDING, self.protected, packages, engine, self.records).run(value)
                c.require(stage['state'] == 'SUCCESS', 'stage incomplete; retain original hold')
                self.require(value, self.protected, self.authority, 'post-readback')
                self.retain(self.key + '/stages/' + layer + '/verified', dict(owner=self.owner,
                    request_sha256=c.digest(c.canonical(value)), result=stage, state='VERIFIED'))
                result['completed_layers'].append(layer)
            started = self.clock();self.check()
            observed = self.guard.residual.observe(copy.deepcopy(self.manifest), copy.deepcopy(self.owner))
            residual = residual_result(observed, self.manifest, self.owner)
            self.check()
            c.require(type(started) is int and type(self.clock()) is int and 0 <= self.clock() - started < 30,
                      'fresh bounded final residual readback')
            self.retain(self.key + '/residual', residual)
            verified = dict(result, state='SUCCESS', residual='VERIFIED')
            self.retain(self.key + '/verified', dict(owner=self.owner, result=verified))
            # A failed final publication must leave UNKNOWN, never release E2.
            result = verified
        except Exception:
            self.retain(self.key + '/blocked', dict(owner=self.owner, result=result,
                reason='QUIESCENCE_APPROVAL_EXECUTION_OR_RESIDUAL_UNPROVED'))
        # E2 execute() alone decides final release, after whole SUCCESS. No
        # stage controller owns release and no finally/exception does it here.
        return result

    def execute(self, packages, engine_factory, guard_factory):
        """Repeat UUIDs only read durable whole-operation evidence.

        E2's terminal binds the original request, so it cannot independently
        authenticate this five-request manifest. A legacy per-layer terminal
        is never projected as completed whole DOWN.
        """
        prior = self.records.read(self.key)
        if prior is not None:
            c.require(prior.get('manifest') == self.manifest and prior.get('state') == 'UNKNOWN',
                      'repeated whole-operation manifest changed')
            verified = self.records.read(self.key + '/verified')
            if verified is not None:
                c.require(verified['owner'] == prior['owner'] and verified['result']['state'] == 'SUCCESS'
                    and verified['result']['completed_layers'] == list(down.DOWN)
                    and verified['result']['residual'] == 'VERIFIED', 'whole terminal completeness')
                # Final journal ACK does not prove E2 release after a crash.
                terminal = self.authority.retained()
                head, _ = self.authority.store.read()
                c.require(terminal is not None and terminal['status'] == 'SUCCESS'
                    and terminal['generation'] == prior['owner']['generation']
                    and head['state'] == 'RELEASED', 'completed original E2 release unproved')
                return copy.deepcopy(verified['result'])
            return dict(operation_id=self.authority.operation, state='UNKNOWN',
                reason='INTERRUPTED_OR_BLOCKED_WHOLE_DOWN_NO_RESUME')
        c.require(self.authority.retained() is None, 'UUID already used by a different lifecycle operation')
        return e.execute(self.authority, lambda _:self.run(packages, engine_factory, guard_factory), state_key='state')
