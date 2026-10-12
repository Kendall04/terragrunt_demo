"""E15 local DEV preparation and residual review. No network or execution ports.

Reports are declaration inventories and untrusted operator notes, never live
AWS evidence, authorization or a Terraform destroy plan. Use existing WP5/WP6
interfaces only after the runbook's gates. DOWN/EXECUTE deliberately fails closed.
"""
import argparse
from decimal import Decimal, InvalidOperation
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.lifecycle import contract as c
from scripts import environment_mutation as e

UP = c.LAYERS
RETAINED_LAYERS = ('shared', 'secrets')
DOWN = tuple(x for x in reversed(UP) if x not in RETAINED_LAYERS)
DEPENDENCIES = {'shared': (), 'secrets': (), 'global': ('shared',),
    'data': ('global', 'shared', 'secrets'), 'platform': (),
    'apps': ('global', 'data', 'platform', 'shared', 'secrets'), 'edge': ('global',)}
# Charging dimensions, not prices or instance expansion. Related service usage
# can be billed even when the API resource itself has no standing charge.
COST = {
    'aws_apigatewayv2_api': 'API requests/data',
    'aws_apigatewayv2_integration': 'API requests/data',
    'aws_apigatewayv2_route': 'API requests/data',
    'aws_apigatewayv2_stage': 'API requests/log ingestion',
    'aws_apigatewayv2_vpc_link': 'dependent ENIs/network usage',
    'aws_autoscaling_group': 'NAT EC2/EBS/public IPv4/transfer',
    'aws_cloudwatch_log_group': 'log ingestion/retained bytes',
    'aws_cloudwatch_metric_alarm': 'alarms/custom metrics',
    'aws_ecs_cluster': 'Container Insights/associated tasks',
    'aws_ecs_cluster_capacity_providers': 'associated tasks',
    'aws_ecs_service': 'Fargate vCPU/memory time/logs/transfer',
    'aws_ecs_task_definition': 'associated tasks',
    'aws_eip': 'allocated public IPv4 hours, including idle',
    'aws_flow_log': 'log ingestion/retained bytes',
    'aws_instance': 'SQL EC2 time/root EBS/transfer/possible credits',
    'aws_internet_gateway': 'associated transfer',
    'aws_lb': 'ALB hours/capacity units',
    'aws_lb_listener': 'associated ALB', 'aws_lb_listener_rule': 'associated ALB',
    'aws_lb_target_group': 'associated ALB/tasks',
    'aws_route': 'associated transfer', 'aws_route_table': 'associated transfer',
    'aws_route_table_association': 'associated transfer',
    'aws_security_group': 'associated resources', 'aws_security_group_rule': 'associated resources',
    'aws_subnet': 'associated ENIs/compute/transfer', 'aws_vpc': 'associated network resources',
    'aws_sns_topic': 'notifications/requests', 'aws_sns_topic_subscription': 'notifications',
    'aws_cloudwatch_event_rule': 'events/targets/associated compute',
    'aws_cloudwatch_event_target': 'events/associated compute',
    'aws_codebuild_project': 'build minutes/logs/artifacts',
    'aws_ecr_repository': 'retained image bytes, unbounded under E8',
    'aws_ecr_repository_policy': 'associated repository bytes',
    'aws_kms_key': 'key months/API requests', 'aws_kms_alias': 'associated key',
    'aws_lambda_function': 'invocations/duration/logs/image bytes',
    'aws_lambda_alias': 'associated function', 'aws_lambda_permission': 'associated function',
    'aws_lambda_function_event_invoke_config': 'async retries/destinations',
    'aws_launch_template': 'associated future EC2/EBS/IPv4',
    'aws_secretsmanager_secret': 'secret months/API requests',
    'aws_sqs_queue': 'requests/retained diagnostic messages',
    'aws_sqs_queue_policy': 'associated queue', 'terraform_data': 'no direct AWS resource',
}
for kind in ('instance_profile','openid_connect_provider','policy','role','role_policy','role_policy_attachment'):
    COST['aws_iam_' + kind] = 'no direct standing charge; associated compute retained'
for suffix in ('bucket','bucket_lifecycle_configuration','bucket_ownership_controls','bucket_policy',
               'bucket_public_access_block','bucket_server_side_encryption_configuration','bucket_versioning'):
    COST['aws_s3_' + suffix] = 'retained objects/versions/requests'


def require(ok, reason):
    if not ok: raise ValueError('E15_LOCAL_REVIEW_REJECTED: ' + reason)


def decode(raw):
    require(type(raw) is str and len(raw.encode()) <= 4 * 1024 * 1024, 'bounded local JSON')
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, 'duplicate JSON key')
            result[key] = value
        return result
    return json.loads(raw, object_pairs_hook=pairs,
        parse_constant=lambda value: (_ for _ in ()).throw(ValueError('nonfinite JSON')))


def context(environment, account, region):
    require(environment == 'dev', 'DEV only; PROD/shared cannot be selected')
    require(type(account) is str and re.fullmatch('[0-9]{12}', account), 'explicit account')
    require(type(region) is str and re.fullmatch('[a-z]{2}(?:-[a-z]+)+-[0-9]', region), 'explicit region')


def declarations(root=ROOT):
    """Trusted source declaration scan; does not expand modules/count/for_each."""
    rows = []
    for base in ('terraform/modules/target/dev', 'terraform/infra/security'):
        for path in sorted((root / base).rglob('*')):
            if any(part in ('.terraform','.terragrunt-cache','__pycache__') for part in path.parts): continue
            if path.is_symlink(): raise ValueError('linked source')
            entries = []
            if path.name.endswith('.tf.json'):
                entries = [(kind, name) for kind, nodes in decode(path.read_text(encoding='utf-8')).get('resource', {}).items()
                           for name in nodes]
            elif path.suffix == '.tf':
                entries = re.findall(r'^resource\s+"([^\"]+)"\s+"([^\"]+)"', path.read_text(encoding='utf-8'), re.M)
            for kind, name in entries:
                require(kind in COST, 'unmapped resource type: ' + kind)
                source = path.relative_to(root).as_posix()
                security = base.endswith('security')
                layer = 'security' if security else path.relative_to(root / base).parts[0]
                retained = security or layer in RETAINED_LAYERS
                risk = ('SQL root EBS deleted on termination; no approved backup' if kind == 'aws_instance'
                        else 'logs removed with owning DEV layer' if kind == 'aws_cloudwatch_log_group' and not retained
                        else 'preserve control/evidence/image bytes' if retained else 'dependent runtime/state references')
                rows.append(dict(key=source + '#' + kind + '.' + name, source=source, type=kind,
                    origin='DECLARATION_NOT_EXPANDED', owner=layer, scope='SECURITY_DEV_PROD_NEUTRAL' if security else 'DEV',
                    treatment='RETAIN' if retained else 'WP5_TEARDOWN_CANDIDATE',
                    cost_dimension=COST[kind], data_risk=risk,
                    dependencies=('admin backend/installation/publication' if security else DEPENDENCIES[layer]),
                    future_absence_check='independent exact-ID service read plus complete parent/child enumeration; see resource table',
                    protected_by='E1_ADMIN' if security else 'E1_WP5_E2',
                    reconstruction='protected installation' if security else 'installed WP5 layer plus fresh bindings'))
    # These resources are created by services or a separately authenticated
    # bootstrap, not standalone Terraform declarations. Absence of their parent
    # in state is insufficient to infer billing/ENI/volume absence.
    related = (
        ('nat-instances', 'global', 'DEV', 'EC2/EBS/public IPv4 hours', 'ASG launched instances and root volumes'),
        ('sql-root-ebs', 'data', 'DEV', 'EBS provisioned bytes/time', 'SQL root data deleted with instance'),
        ('service-enis', 'global', 'DEV', 'dependent compute/network usage', 'NAT/SQL/ECS/VPC Link ENIs can outlive a partial teardown'),
        ('running-tasks', 'apps', 'DEV', 'Fargate vCPU/memory time', 'must independently observe both colors and full task lists'),
        ('runtime-task-revisions', 'security', 'DEV', 'no standing revision charge', 'WP4-owned revisions/evidence; no arbitrary deregistration'),
        ('nat-default-routes', 'global', 'DEV', 'dependent transfer', 'WP4 recovery owns default routes; settle in-flight calls'),
        ('security-backend', 'security', 'ACCOUNT_ADMIN', 'state versions/requests', 'external admin backend and locking must survive'),
        ('approved-snapshots-backups', 'security', 'OWNER_SELECTED', 'snapshot/backup retained bytes', 'not implemented/created by E15; never delete existing backups'),
    )
    for name, owner, scope, cost, risk in related:
        rows.append(dict(key='related:' + name, source='service-created or external; see E15 runbook',
            type=name, origin='IMPLICIT_OR_EXTERNAL_DEPENDENCY', owner=owner, scope=scope,
            treatment='RETAIN' if owner == 'security' else 'WP5_TEARDOWN_CANDIDATE',
            cost_dimension=cost, data_risk=risk, dependencies='parent service plus protected admin boundaries',
            future_absence_check='independent exact-ID enumeration including orphan resources; parent state absence insufficient', protected_by='E1_ADMIN' if owner == 'security' else 'E1_WP5_E2',
            reconstruction='fresh protected installation/membership; parent absence is not evidence'))
    require(rows and len({r['key'] for r in rows}) == len(rows), 'complete unique declaration inventory')
    return rows


def budget(value):
    c.keys(value, ('monthly_limit', 'currency', 'actual_percent', 'forecast_percent', 'recipients', 'scope'), 'budget draft')
    missing = []
    for key in ('monthly_limit', 'actual_percent', 'forecast_percent'):
        raw = value[key]
        if raw is None: missing.append(key); continue
        require(type(raw) is str, 'budget numbers must be decimal strings')
        try: amount = Decimal(raw)
        except InvalidOperation: raise ValueError('invalid budget decimal') from None
        require(amount.is_finite() and amount > 0, 'positive budget value')
    require(value['currency'] is None or value['currency'] == 'USD', 'supported cost-budget currency')
    require(value['scope'] is None or value['scope'] in ('ACCOUNT_TOTAL', 'DEV_TAG_PLUS_RESIDUAL_REVIEW'), 'explicit budget scope')
    require(type(value['recipients']) is list and len(value['recipients']) <= 10
            and len(set(value['recipients'])) == len(value['recipients']), 'bounded unique recipients')
    require(all(type(x) is str and re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', x) for x in value['recipients']), 'alert recipients')
    for key in ('currency', 'scope', 'recipients'):
        if not value[key]: missing.append(key)
    return dict(configuration=value, missing_owner_decisions=missing,
        classification='REQUIRES_OWNER_DECISION' if missing else 'PARTIALLY_READY',
        installation='NOT_INSTALLED', hard_billing_cap=False, automatic_shutdown=False)


def assess_notes(notes, account, region, rows):
    """Untrusted local audit notes can add blockers; cannot authorize execution."""
    c.keys(notes, ('schema', 'environment', 'account', 'region', 'e2', 'operations', 'resources'), 'local audit notes')
    require(notes['schema'] == 'E15_LOCAL_NOTES_V1', 'local notes schema')
    context(notes['environment'], notes['account'], notes['region'])
    require(notes['account'] == account and notes['region'] == region, 'notes identity mismatch')
    c.keys(notes['e2'], ('application', 'shared', 'secrets'), 'all E2 domains required')
    blockers = []
    for domain, envelope in notes['e2'].items():
        c.keys(envelope, ('version_id', 'head'), 'E2 notes envelope')
        version = envelope['version_id']
        require(type(version) is str and version.strip() == version and version.lower() not in ('', 'null', 'latest'), 'exact E2 version')
        e.validate(envelope['head'], 'dev', domain)
        if envelope['head']['state'] == 'ACTIVE': blockers.append('E2_ACTIVE_' + domain)
    require(type(notes['operations']) is list, 'operation notes')
    identities = set()
    for operation in notes['operations']:
        c.keys(operation, ('binding', 'operation_id', 'state', 'layer'), 'operation note')
        require(operation['binding'].endswith('-dev'), 'DEV operation')
        e.domain(operation['binding'], operation['layer'])
        e.identity(operation['operation_id'])
        require(operation['operation_id'] not in identities, 'duplicate operation')
        identities.add(operation['operation_id'])
        require(operation['state'] in ('SUCCESS', 'FAILURE', 'PLANNED', 'ACTIVE', 'UNKNOWN', 'UNCERTAIN'), 'known operation state')
        if operation['state'] in ('ACTIVE', 'UNKNOWN', 'UNCERTAIN'):
            blockers.append('UNRESOLVED_' + operation['state'])
    require(type(notes['resources']) is dict and set(notes['resources']) <= {r['key'] for r in rows}, 'known declaration notes only')
    require(all(value in ('PRESENT', 'ABSENT', 'UNKNOWN', 'PARTIAL') for value in notes['resources'].values()), 'known resource observation')
    residual = [dict(key=r['key'], reported=notes['resources'].get(r['key'], 'UNKNOWN'),
        treatment=r['treatment'], cost_dimension=r['cost_dimension']) for r in rows
        if r['treatment'] == 'RETAIN' or notes['resources'].get(r['key']) != 'ABSENT']
    if any(r['reported'] in ('UNKNOWN', 'PARTIAL') for r in residual): blockers.append('INCOMPLETE_RESIDUAL_EVIDENCE')
    if any(r['reported'] == 'PRESENT' and r['treatment'] != 'RETAIN' for r in residual): blockers.append('DEV_RESOURCES_REMAIN')
    return dict(provenance='UNTRUSTED_LOCAL_NOTES', blockers=sorted(set(blockers)), residual=residual,
                aws_verified=False, execution_authorized=False)


def report(action, account, region, environment='dev', notes=None, budget_config=None,
           confirm_dev=False, confirm_sql_loss=False, sql_policy='UNDECIDED', root=ROOT):
    context(environment, account, region)
    require(action in ('status', 'up-prepare', 'down-preview', 'verify', 'residual', 'down-execute'), 'known action')
    require(action != 'down-execute', 'DOWN/EXECUTE unavailable: no active-color quiescence/NAT retirement authority')
    require(type(confirm_dev) is bool and type(confirm_sql_loss) is bool, 'separate confirmations')
    require(sql_policy in ('UNDECIDED', 'DISPOSABLE', 'PRESERVE'), 'explicit SQL policy')
    require(not confirm_sql_loss or (confirm_dev and sql_policy == 'DISPOSABLE'), 'SQL loss confirmation requires DEV destruction and disposable choice')
    rows = declarations(root)
    doc = decode((root / 'terraform/infra/security/authority.json').read_text(encoding='utf-8'))
    blockers = ['LIVE_AWS_EVIDENCE_REQUIRED', 'ACTIVE_COLOR_QUIESCENCE_AUTHORITY_MISSING',
                'NAT_EVENT_AND_INFLIGHT_RETIREMENT_REQUIRED', 'REVIEWABLE_DESTROY_PLAN_GATE_MISSING',
                'E13_NOTIFICATION_TOPIC_BINDING_MISMATCH']
    if not doc['wp6']['approvals']: blockers.append('WP6_INSTALLATION_GOVERNANCE_MISSING')
    if any(not doc['wp5'][key] for key in ('installations', 'runtime_approvals', 'environment_bindings')):
        blockers.append('WP5_INSTALLATION_MISSING')
    if action == 'down-preview':
        if not confirm_dev: blockers.append('DEV_DESTRUCTION_CONFIRMATION_REQUIRED')
        if sql_policy != 'DISPOSABLE' or not confirm_sql_loss: blockers.append('SQL_DATA_DECISION_AND_INDEPENDENT_CONFIRMATION_REQUIRED')
        if sql_policy == 'PRESERVE': blockers.append('E5_APPROVED_BACKUP_RESTORE_NOT_IMPLEMENTED')
    review = assess_notes(notes, account, region, rows) if notes is not None else None
    if review is not None: blockers.extend(review['blockers'])
    elif action in ('verify', 'residual', 'down-preview'): blockers.append('MISSING_LOCAL_NOTES')
    return dict(schema='E15_LOCAL_REVIEW_V1', environment='dev', account=account, region=region,
        classification='PARTIALLY_READY', source='REPOSITORY_DECLARATIONS_NOT_LIVE_STATE',
        execution_authorized=False, aws_verified=False, action=action,
        up_order=UP, down_order=DOWN, retained_layers=RETAINED_LAYERS, dependencies=DEPENDENCIES,
        protected_backend=dict(bucket=f'e1-lifecycle-dev-{account}-{region}',
            keys=[f'e1/lifecycle/dev/{layer}/terraform.tfstate' for layer in UP], deletion_permitted=False),
        gates=sorted(set(blockers)), declaration_inventory=rows, local_notes_review=review,
        budget=budget(budget_config) if budget_config is not None else dict(classification='REQUIRES_OWNER_DECISION'),
        cost_model=dict(up='retained baseline + runtime quantities * regional rates',
            down='retained bytes/keys/requests + any surviving DEV resources', estimate=None, zero_cost_claim=False),
        existing_interfaces=['WP6 plan-dev', 'WP6 infra-dev', 'WP6 infra-high-risk-dev', 'WP6 release', 'WP6 deploy-dev'],
        retry_contract='reuse existing UUID for retained status only; UNKNOWN/UNCERTAIN never reapplies or takes over')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('status','up-prepare','down-preview','verify','residual','down-execute'))
    parser.add_argument('--environment', default='dev')
    parser.add_argument('--account', required=True)
    parser.add_argument('--region', required=True)
    parser.add_argument('--notes', type=Path)
    parser.add_argument('--budget-config', type=Path, default=ROOT / 'ci/ephemeral/budget-draft.json')
    parser.add_argument('--confirm-dev-destruction', action='store_true')
    parser.add_argument('--confirm-sql-data-loss', action='store_true')
    parser.add_argument('--sql-policy', choices=('UNDECIDED','DISPOSABLE','PRESERVE'), default='UNDECIDED')
    args = parser.parse_args(argv)
    notes = decode(args.notes.read_text(encoding='utf-8')) if args.notes else None
    value = report(args.action, args.account, args.region, args.environment, notes,
        decode(args.budget_config.read_text(encoding='utf-8')), args.confirm_dev_destruction, args.confirm_sql_data_loss, args.sql_policy)
    print(json.dumps(value, indent=2))
    # Successful exit means local report rendered, never UP/DOWN completed.
    return 0


if __name__ == '__main__':
    try: raise SystemExit(main())
    except (ValueError, KeyError, TypeError, OSError):
        raise SystemExit('E15_LOCAL_REVIEW_REJECTED; no AWS action performed') from None
