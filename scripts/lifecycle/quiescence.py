"""E15-E/F protected composition; no installed whole-DOWN authority.

A shared exact WP5 request/owner binds separate ECS and NAT evidence. This
adapter cannot bridge per-layer owners, settle AWS effects or authorize apply.
"""
import copy
from . import contract as c, dev_down as down, ecs_quiescence as ecs, handoff
from scripts.nat import quiescence as nat


class InstalledNAT:
    """Missing authenticated configuration/observation installation, not flags."""
    def protocol(self, authority, value, protected, records, clock):
        raise ecs.Blocked('E15EF_NAT_CONFIGURATION_AND_OBSERVATION_UNINSTALLED')


class Guard:
    def __init__(self, value, protected, authority, ecs_protocol, records, nat_source, clock):
        self.value, self.protected = copy.deepcopy(value), copy.deepcopy(protected)
        self.scope = down.scope(value, protected)
        self.owner = ecs.owner_identity(authority, self.scope)
        c.require(type(ecs_protocol) is ecs.Quiescence and ecs_protocol.authority is authority
                  and ecs_protocol.owner == self.owner
                  and all(ecs_protocol.selected[k] == v for k, v in self.scope.items()),
                  'same exact ECS request, stage and E2 owner')
        c.require(records.bucket == self.scope['backend']['bucket'] and records.prefix ==
                  'operations/' + self.scope['binding'] + '/', 'protected combined WP5 journal')
        c.require(type(nat_source) is nat.Quiescence or type(nat_source) is InstalledNAT,
                  'internal NAT protocol or uninstalled protected source only')
        if type(nat_source) is nat.Quiescence:
            c.require(self.scope['layer'] == 'global' and nat_source.authority is authority
                      and nat_source.owner == self.owner and nat_source.scope == self.scope
                      and nat_source.records is records, 'same exact NAT request, stage and E2 owner')
        self.authority, self.ecs, self.records = authority, ecs_protocol, records
        self.nat, self.clock, self.receipt = nat_source, clock, None
        self.key = value['operation_id'] + '/combined-quiescence/' + value['layer']

    def current(self):
        c.require(ecs.owner_identity(self.authority, self.scope) == self.owner,
                  'original combined E2 owner/generation only')
        c.require(down.scope(self.value, self.protected) == self.scope, 'immutable combined scope')
        c.require(self.ecs.authority is self.authority and self.ecs.owner == self.owner
                  and all(self.ecs.selected[k] == v for k, v in self.scope.items()), 'current ECS correlation')
        if type(self.nat) is nat.Quiescence:
            c.require(self.nat.authority is self.authority and self.nat.owner == self.owner
                      and self.nat.scope == self.scope, 'current NAT correlation')
            self.nat.check()

    def retain(self, key, value):
        previous = self.records.read(key)
        if previous is None:
            try:
                self.records.create(key, value)
            except Exception:
                pass  # exact readback, never a blind write retry
            previous = self.records.read(key)
        c.require(previous == value, 'durable exact combined UNKNOWN evidence')

    def require(self, stage, phase):
        c.require(stage == self.scope['layer'] and stage in down.DOWN and
                  phase in ('pre-dispatch', 'post-readback'), 'exact dependent stage/phase')
        self.current()
        intent = dict(schema='E15EF_COMBINED_V1', scope=self.scope, owner=self.owner,
                      order=list(down.DOWN), stage_index=down.DOWN.index(stage),
                      state='UNKNOWN', execution_authorized=False)
        self.retain(self.key, intent)
        blockers = ['WHOLE_DOWN_OWNER_AND_ORDERED_STAGE_HANDOFF_UNINSTALLED']
        evidence = dict(ecs=None, nat=None)
        try:
            if self.receipt is None:
                self.receipt = self.ecs.begin()
            evidence['ecs'] = self.ecs.require_quiet(self.receipt, stage)
            self.receipt = evidence['ecs']
        except Exception:
            blockers.append('ECS_CURRENT_CLOSURE_OR_QUIETNESS_UNPROVED')
        # Cluster disappearance cannot erase the remembered STOPPED cohort.
        if stage in ('data', 'global') or (stage == 'platform' and phase == 'post-readback'):
            blockers.append('ECS_CLUSTER_DELETION_EVIDENCE_HANDOFF_UNINSTALLED')
        if stage == 'global':
            try:
                if type(self.nat) is InstalledNAT:
                    self.nat = self.nat.protocol(self.authority, self.value, self.protected,
                                                 self.records, self.clock)
                    c.require(type(self.nat) is nat.Quiescence, 'concrete NAT protocol')
                    self.current()
                # This method publishes its separate protected UNKNOWN diagnostics
                # and always denies, even with perfectly shaped local readbacks.
                self.nat.require_network_teardown()
            except Exception:
                blockers.append('NAT_EXECUTOR_AND_ISSUED_EFFECT_SETTLEMENT_UNPROVED')
            if type(self.nat) is nat.Quiescence:
                evidence['nat'] = dict(key=self.nat.key, state='UNKNOWN', execution_authorized=False)
        report = dict(intent, phase=phase, evidence=evidence, blockers=sorted(blockers),
                      classification='PARTIALLY_READY', aws_verified=False)
        key = self.key + '/observations/' + c.digest(c.canonical(report))
        self.retain(key, report)
        self.current()
        # No synthetic port/receipt, administrative approval or JSON flag can
        # install whole-operation ownership, stage ordering or effect settlement.
        raise ecs.Blocked('E15EF_DOWN_BLOCKED: ' + ','.join(sorted(blockers)))


def installed(engine, channel, authority, records, clock):
    """Fixed protected runtime factory; no event-selected adapters or authority."""
    c.require(type(channel) is handoff.Handoff and channel.engine is engine
              and engine.authority is authority, 'exact E15-D engine and owner')
    channel.scope(engine.request, engine.protected)
    selected = ecs.scope(engine.request, engine.protected)
    protocol = ecs.Quiescence(engine.request, engine.protected, authority,
        ecs.ECS(engine.ecs, selected), ecs.Journal(channel.storage, selected),
        ecs.HandoffBoundary(channel), clock)
    return Guard(engine.request, engine.protected, authority, protocol, records, InstalledNAT(), clock)
