"""DEV-only data consent and offline destroy-artifact review; no I/O authority.

Consent is an extra restriction in existing admin-owned teardown_approvals. Local
review bytes never authenticate their origin or grant plan execution authority.
"""
import copy
import re
from . import contract as c

DOWN = ('edge', 'apps', 'platform', 'data', 'global')
POLICY = 'TERRAGRUNT_DEMO_DEV_SQL_DISPOSABLE_WITH_EXPLICIT_LOSS_ACK'


def scope(value, protected):
    binding = 'environment-lifecycle/infra-high-risk-dev'
    c.request(binding, value)
    c.require(value['operation'] == 'teardown' and value['layer'] in DOWN, 'DEV DOWN scope only')
    c.require(protected['binding'] == binding and protected['environment'] == 'dev', 'DEV installed context')
    account, region = protected['account'], protected['region']
    c.require(type(account) is str and re.fullmatch('[0-9]{12}', account), 'exact account')
    c.require(type(region) is str and re.fullmatch('[a-z]{2}(?:-[a-z]+)+-[0-9]', region), 'exact region')
    layer = protected['layers'][value['layer']]
    c.keys(layer, ('root', 'variables', 'addresses', 'membership', 'backend'), 'installed layer')
    c.require(layer['root'] == 'terraform/modules/target/dev/' + value['layer'], 'DEV root')
    c.require(layer['backend'] == dict(bucket=f'e1-lifecycle-dev-{account}-{region}',
        key=f'e1/lifecycle/dev/{value["layer"]}/terraform.tfstate', region=region), 'DEV state retained')
    c.require(layer['variables'].get('account_id') == account and layer['variables'].get('region') == region,
              'provider identity')
    reference = protected['installations'][value['revision']]
    c.require(reference['binding'] == binding and reference['sha256'] == value['revision']
              and value['revision'] in protected['active_contracts'], 'active source installation')
    result = dict(application='terragrunt_demo', environment='dev', account=account, region=region,
        binding=binding, operation_id=value['operation_id'], layer=value['layer'], revision=value['revision'],
        source_commit=reference['source_commit'], request_sha256=c.digest(c.canonical(value)),
        installed_layer_sha256=c.digest(c.canonical(layer)), root=layer['root'],
        backend=copy.deepcopy(layer['backend']), workspace='default', sql_policy=POLICY)
    result['scope_sha256'] = c.digest(c.canonical(result))
    return result


def acknowledgements(selected):
    identity = ' '.join(selected[k] for k in ('account', 'region', 'operation_id', 'scope_sha256'))
    return dict(destroy_ack='DESTROY terragrunt_demo DEV ' + identity,
                sql_loss_ack='PERMANENTLY LOSE terragrunt_demo DEV SQL DATA ' + identity)


def confirm(selected, record, now):
    c.keys(record, ('schema', 'scope_sha256', 'issued_at', 'expires_at', 'destroy_ack', 'sql_loss_ack'), 'DEV consent')
    c.require(record['schema'] == 'E15B_DEV_CONSENT_V1' and record['scope_sha256'] == selected['scope_sha256'],
              'exact DEV consent scope')
    c.require(type(now) is int and type(record['issued_at']) is int and type(record['expires_at']) is int
              and 0 <= record['issued_at'] <= now < record['expires_at'], 'current unexpired DEV consent')
    c.require({k: record[k] for k in ('destroy_ack', 'sql_loss_ack')} == acknowledgements(selected),
              'separate exact resource and permanent SQL-loss acknowledgements')
    return c.digest(c.canonical(record))


def check_data_consent(value, protected, now):
    selected = scope(value, protected)
    record = protected['teardown_approvals'].get('dev-sql-loss/' + value['operation_id'])
    return confirm(selected, record, now)


def review(value, protected, binary, plan, context, now):
    """Summarize an already supplied binary and its JSON; no Terraform call.

    Matching local hashes do not prove JSON was generated from binary or state is
    current. Protected acquisition, immutable approval and consumption remain gates.
    """
    selected = scope(value, protected)
    c.keys(context, ('schema', 'scope_sha256', 'created_at', 'expires_at', 'binary_sha256', 'json_sha256',
                     'state', 'workspace'), 'destroy review context')
    c.require(context['schema'] == 'E15B_DESTROY_REVIEW_V1' and context['scope_sha256'] == selected['scope_sha256'],
              'exact review scope')
    c.require(type(now) is int and type(context['created_at']) is int and type(context['expires_at']) is int
              and 0 <= context['created_at'] <= now < context['expires_at'], 'current review window')
    c.require(type(binary) is bytes and 0 < len(binary) <= 16777216, 'bounded binary plan required')
    c.require(context['binary_sha256'] == c.digest(binary)
              and context['json_sha256'] == c.digest(c.canonical(plan)), 'exact binary/JSON identities')
    c.require(context['workspace'] == 'default', 'fixed workspace')
    state = context['state']
    c.keys(state, ('lineage', 'serial', 'version_id', 'sha256'), 'exact claimed state snapshot')
    c.require(type(state['lineage']) is str and re.fullmatch('[A-Za-z0-9-]{1,128}', state['lineage'])
              and type(state['serial']) is int and state['serial'] >= 0, 'state lineage/serial')
    c.require(type(state['version_id']) is str and state['version_id'].strip() == state['version_id']
              and state['version_id'].lower() not in ('', 'latest', 'null'), 'exact state version')
    c.require(type(state['sha256']) is str and re.fullmatch('[0-9a-f]{64}', state['sha256']), 'state bytes digest')
    c.require(type(plan) is dict and plan.get('format_version') == '1.2' and plan.get('complete') is True
              and plan.get('errored') is False and not plan.get('deferred_changes')
              and not plan.get('resource_drift'), 'complete destroy review')
    layer = protected['layers'][value['layer']]
    changes = plan.get('resource_changes', [])
    c.require(type(changes) is list, 'change list')
    summary, seen = [], set()
    for resource in changes:
        address, kind = resource.get('address'), resource.get('type')
        c.require(address in layer['addresses'] and address not in seen and layer['addresses'][address] == kind,
                  'installed address/type only')
        seen.add(address)
        change = resource['change']; actions = change['actions']
        if resource.get('mode') == 'data':
            c.require(actions == ['no-op'], 'no deferred data reads')
            continue
        c.require(resource.get('mode') == 'managed' and not kind.startswith(c.PROTECTED_TYPES)
                  and actions in (['delete'], ['no-op']), 'no protected/cross-scope/create/update action')
        before = change.get('before')
        c.require(type(before) is dict and before.get('id') == layer['membership'].get(address)
                  and type(before.get('id')) is str and bool(before['id']), 'exact existing membership')
        if actions == ['delete']:
            c.require(change.get('after') is None, 'delete outcome')
        summary.append(dict(address=address, type=kind, id=before['id'], actions=actions))
    result = dict(scope=selected, context=copy.deepcopy(context), destructive_changes=summary,
        expected_acknowledgements=acknowledgements(selected), provenance='UNTRUSTED_LOCAL_ARTIFACTS',
        plan_authenticated=False, execution_authorized=False,
        gates=['PROTECTED_BINARY_JSON_STATE_ACQUISITION_REQUIRED', 'IMMUTABLE_PLAN_APPROVAL_HANDOFF_REQUIRED',
               'CURRENT_STATE_RECHECK_AND_SINGLE_USE_CONSUMPTION_REQUIRED', 'ECS_CONTROLLER_CLOSURE_REQUIRED',
               'NAT_EXECUTOR_AND_ISSUED_EFFECT_SETTLEMENT_REQUIRED'])
    result['review_sha256'] = c.digest(c.canonical(result))
    return result


def check_current_review(record, selected, state, binary, plan, now):
    """Local consistency only; matching bytes cannot establish authenticated state."""
    unsigned = {k:v for k,v in record.items() if k != 'review_sha256'}
    c.require(record.get('review_sha256') == c.digest(c.canonical(unsigned)), 'unchanged local review')
    c.require(record['scope'] == selected and record['context']['state'] == state, 'review state/scope still matches')
    c.require(type(now) is int and record['context']['created_at'] <= now < record['context']['expires_at'],
              'review still current')
    c.require(record['context']['binary_sha256'] == c.digest(binary)
              and record['context']['json_sha256'] == c.digest(c.canonical(plan)), 'reviewed exact artifacts')
    return dict(local_consistency=True, execution_authorized=False, state_authenticated=False)
