"""Offline IAM definitions for reviewed activation; never installs policies.

Input is the authenticated API_INSTALLATION_V1 configuration. Rendering fixtures
does not establish real PROD resources. Existing OIDC custom claims are retained.
"""
from .aws import validate_binding
from .model import REPOSITORY, require


def definitions(config, role_arn, binding_ref):
    env = config['environment']; account = config['account']; region = config['region']
    validate_binding(config, env, account, region)
    require(role_arn == f'arn:aws:iam::{account}:role/api-delivery-{env}', 'dedicated environment role')
    branch = 'develop' if env == 'dev' else 'main'
    subject = f'repo:{REPOSITORY}:environment:api-{env}:job_workflow_ref:{REPOSITORY}/.github/workflows/api-execute.yml@refs/heads/{branch}'
    trust = dict(Version='2012-10-17', Statement=[dict(Effect='Allow',
        Principal={'Federated': f'arn:aws:iam::{account}:oidc-provider/token.actions.githubusercontent.com'},
        Action='sts:AssumeRoleWithWebIdentity', Condition={'StringEquals': {
            'token.actions.githubusercontent.com:aud': 'sts.amazonaws.com',
            'token.actions.githubusercontent.com:sub': subject}})])
    colors = list(config['colors'].values()); cluster = colors[0]['service']['cluster']
    cluster_name = cluster.split('/')[-1]
    services = [f'arn:aws:ecs:{region}:{account}:service/{cluster_name}/' + c['service']['service'] for c in colors]
    families = [f'arn:aws:ecs:{region}:{account}:task-definition/demo-{env}-app-api-{color}:*' for color in ('blue', 'green')]
    tasks = f'arn:aws:ecs:{region}:{account}:task/{cluster_name}/*'
    bucket = config['evidence_bucket']; obj = 'arn:aws:s3:::' + bucket + '/'
    repository = f'arn:aws:ecr:{region}:{account}:repository/' + config['repository'].split('/', 1)[1]
    statements = []
    def allow(actions, resources, condition=None):
        record = dict(Effect='Allow', Action=actions, Resource=resources)
        if condition: record['Condition'] = condition
        statements.append(record)
    allow(['s3:GetObjectVersion'], ['arn:aws:s3:::' + binding_ref['bucket'] + '/' + binding_ref['key']],
          {'StringEquals': {'s3:VersionId': binding_ref['version']}})
    head = obj + f'arbitration/{env}/application.json'
    terminals = obj + f'arbitration/{env}/terminals/normal-delivery/' + ('deploy-dev' if env == 'dev' else 'promote-prod') + '/*'
    records = obj + f'api-delivery/{env}/operations/*'
    allow(['s3:GetObject'], [head, terminals])
    allow(['s3:GetObjectVersion'], [records])
    # The adapter first lists the exact terminal key (one item). An absent key
    # is proven by the allowed list, never inferred from GetObject AccessDenied.
    allow(['s3:ListBucket'], ['arn:aws:s3:::' + bucket],
          {'StringLike': {'s3:prefix': terminals.split(obj, 1)[1]}, 'NumericEquals': {'s3:max-keys': 1}})
    # Publication-only recovery enumerates every version of ONE exact release key.
    allow(['s3:ListBucketVersions'], ['arn:aws:s3:::' + bucket],
          {'StringLike': {'s3:prefix': f'api-delivery/{env}/operations/*/release.json'},
           'NumericLessThanEquals': {'s3:max-keys': 100}})
    allow(['s3:PutObject'], [head], {'Null': {'s3:if-match': 'false'}})
    allow(['s3:PutObject'], [terminals, records], {'StringEquals': {'s3:if-none-match': '*'}})
    allow(['kms:Decrypt', 'kms:GenerateDataKey'], [config['evidence_kms_key']],
          {'StringEquals': {'kms:ViaService': f's3.{region}.amazonaws.com', 'kms:CallerAccount': account},
           'StringLike': {'kms:EncryptionContext:aws:s3:arn': ['arn:aws:s3:::' + bucket, obj + '*']}})
    allow(['kms:Decrypt'], [config['binding_kms_key']],
          {'StringEquals': {'kms:ViaService': f's3.{region}.amazonaws.com', 'kms:CallerAccount': account},
           'StringLike': {'kms:EncryptionContext:aws:s3:arn': ['arn:aws:s3:::' + binding_ref['bucket'],
                        'arn:aws:s3:::' + binding_ref['bucket'] + '/' + binding_ref['key']]}})
    allow(['ecs:DescribeServices', 'ecs:UpdateService'], services, {'ArnEquals': {'ecs:cluster': cluster}})
    allow(['ecs:DescribeTasks'], [tasks])
    # ECS authorization table: DescribeTaskDefinition has no resource type;
    # RegisterTaskDefinition supports the task-definition ARN (including family).
    allow(['ecs:RegisterTaskDefinition'], families, {'StringEquals': {'aws:RequestedRegion': region}})
    allow(['ecs:DescribeTaskDefinition', 'ecs:ListTasks'], ['*'],
          {'StringEquals': {'aws:RequestedRegion': region}})
    allow(['elasticloadbalancing:DescribeListeners', 'elasticloadbalancing:DescribeRules',
           'elasticloadbalancing:DescribeTargetHealth'], ['*'], {'StringEquals': {'aws:RequestedRegion': region}})
    allow(['elasticloadbalancing:ModifyListener'], [colors[0]['listener_arn']])
    allow(['elasticloadbalancing:ModifyRule'], [colors[0]['candidate_rule_arn']])
    allow(['iam:PassRole'], sorted({role for c in colors for role in c['roles'].values()}),
          {'StringEquals': {'iam:PassedToService': 'ecs-tasks.amazonaws.com'}})
    allow(['ecr:DescribeImages', 'ecr:DescribeRepositories', 'ecr:BatchGetImage'], [repository])
    if env == 'dev':
        allow(['ecr:GetAuthorizationToken'], ['*'])
        allow(['ecr:BatchCheckLayerAvailability', 'ecr:InitiateLayerUpload', 'ecr:UploadLayerPart',
               'ecr:CompleteLayerUpload', 'ecr:PutImage'], [repository])
    else:
        scope = config['dev_evidence']
        dev_objects = 'arn:aws:s3:::' + scope['bucket'] + '/api-delivery/dev/operations/*/release.json'
        allow(['s3:GetObjectVersion'], [dev_objects])
        allow(['kms:Decrypt'], [scope['kms_key']], {'StringEquals': {
            'kms:ViaService': f's3.{region}.amazonaws.com', 'kms:CallerAccount': account},
            'StringLike': {'kms:EncryptionContext:aws:s3:arn': [dev_objects]}})
    return dict(trust=trust, permissions=dict(Version='2012-10-17', Statement=statements),
                environment=dict(name='api-' + env, protected_branch=branch, reviewers=[]),
                unresolved=['Exact CMK key policies must admit these S3-only role permissions',
                            'Versioned public binding, initialized existing E2 head and bucket conditional-write barriers',
                            'Readiness Describe/List permissions must be simulated against the installed graph'])


PROMOTION_RULE = {
    'type': 'required_status_checks',
    'parameters': {'strict_required_status_checks_policy': True,
                   'do_not_enforce_on_create': False,
                   'required_status_checks': [{'context': 'API Promotion Validation', 'integration_id': 15368}]},
}
# A MAIN-ONLY additional rule; never append this to the joint main/develop rule.
# Keep existing CI/CD Safety checks, no bypass and branch-update requirements.


def merge_only_rule(existing_pull_request_rule):
    """Main-only overlay: preserve every reviewed PR parameter except methods."""
    import copy
    require(existing_pull_request_rule['type'] == 'pull_request', 'PR rule required')
    result = copy.deepcopy(existing_pull_request_rule)
    result['parameters']['allowed_merge_methods'] = ['merge']
    return result
