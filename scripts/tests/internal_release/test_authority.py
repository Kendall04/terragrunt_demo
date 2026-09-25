"""Effective policy decisions and concrete project topology, not hash-only proof."""
import copy
import json
import re
import tempfile
from pathlib import Path
import unittest

import internal
import e1_contract as c
from evaluator import Decision

ROOT=Path(__file__).resolve().parents[3]
ACCOUNT='111122223333'; REGION='us-east-1'
EVIDENCE='demo-release-artifacts-'+ACCOUNT
EXCHANGE='e1-quarantine-'+ACCOUNT+'-'+REGION
BUNDLES='e1-control-bundles-'+ACCOUNT+'-'+REGION
REFS={k:dict(key='bundles/sha256/'+'a'*64+'.json',version_id='fixture-version') for k in c.CONTROLLERS}


def policies():
    return internal.policies(ACCOUNT,REGION,EVIDENCE,EXCHANGE,BUNDLES,REFS)


def decision(policy,action,resource,context=None):
    # WP1 deliberately does not model CodeBuild. This separately scoped model
    # admits only the literal identity-policy grammar emitted for WP3C. It makes
    # no resource-policy, SCP, trust, service dependency or live-AWS claim.
    assert set(policy)=={'Version','Statement'} and policy['Version']=='2012-10-17'
    granted=False
    def matches(pattern,value):
        assert isinstance(pattern,str) and '${' not in pattern
        return re.fullmatch(re.escape(pattern).replace(r'\*','.*').replace(r'\?','.'),value) is not None
    for statement in policy['Statement']:
        assert set(statement) <= {'Effect','Action','Resource','Condition'}
        assert statement['Effect'] in ('Allow','Deny')
        assert isinstance(statement['Action'],list) and isinstance(statement['Resource'],list)
        tests=statement.get('Condition',{})
        assert set(tests)<= {'StringEquals','StringLike','NumericEquals'}
        condition=all((context or {}).get(k)==v for k,v in tests.get('StringEquals',{}).items())
        condition=condition and all(any(matches(pattern,(context or {}).get(k,'')) for pattern in (v if isinstance(v,list) else [v])) for k,v in tests.get('StringLike',{}).items())
        condition=condition and all(str((context or {}).get(k))==str(v) for k,v in tests.get('NumericEquals',{}).items())
        if condition and any(matches(p.lower(),action.lower()) for p in statement['Action']) and any(matches(p,resource) for p in statement['Resource']):
            if statement['Effect']=='Deny':return Decision.DENY
            granted=True
    return Decision.ALLOW if granted else Decision.DENY


DENIED={
    'ecr:PutImage':f'arn:aws:ecr:{REGION}:{ACCOUNT}:repository/demo-shared-demo-ms',
    's3:PutObject':f'arn:aws:s3:::{EVIDENCE}/attempts/demo-api/attempt.json',
    's3:GetObjectVersion':f'arn:aws:s3:::{BUNDLES}/bundles/sha256/'+'a'*64+'.json',
    's3:GetObject':f'arn:aws:s3:::{EXCHANGE}/quarantine/demo-api/another/source.json',
    's3:ListBucket':f'arn:aws:s3:::{EXCHANGE}',
    'codebuild:StartBuild':f'arn:aws:codebuild:{REGION}:{ACCOUNT}:project/e1-controller-release',
    'lambda:InvokeFunction':f'arn:aws:lambda:{REGION}:{ACCOUNT}:function:e1-qualification-finalizer',
    'iam:PassRole':f'arn:aws:iam::{ACCOUNT}:role/e1-controller-release-exec',
    'iam:PutRolePolicy':f'arn:aws:iam::{ACCOUNT}:role/e1-controller-release-exec',
    'sts:AssumeRole':f'arn:aws:iam::{ACCOUNT}:role/e1-controller-release-exec',
    'ecs:UpdateService':f'arn:aws:ecs:{REGION}:{ACCOUNT}:service/demo/api',
    'elasticloadbalancing:ModifyListener':f'arn:aws:elasticloadbalancing:{REGION}:{ACCOUNT}:listener/app/demo/id/id',
    'kms:Decrypt':f'arn:aws:kms:{REGION}:{ACCOUNT}:key/11111111-1111-1111-1111-111111111111',
    'secretsmanager:GetSecretValue':f'arn:aws:secretsmanager:{REGION}:{ACCOUNT}:secret:protected-abcdef',
    'ssm:GetParameter':f'arn:aws:ssm:{REGION}:{ACCOUNT}:parameter/protected',
}


def compromise_ceiling(policy):
    for action,resource in DENIED.items():
        assert decision(policy,action,resource,{'s3:if-none-match':'*','s3:VersionId':'fixture-version'}) == Decision.DENY, action
    for prefix in ('qualifications/','eligibility/','operations/'):
        assert decision(policy,'s3:PutObject',f'arn:aws:s3:::{EVIDENCE}/'+prefix+'attempt',{'s3:if-none-match':'*'}) == Decision.DENY
    for project in c.WORKERS.values():
        assert decision(policy,'codebuild:StartBuild',f'arn:aws:codebuild:{REGION}:{ACCOUNT}:project/'+project)==Decision.DENY


def topology(tf):
    r=tf['resource'];outer=r['aws_codebuild_project']['wp3'];worker=r['aws_codebuild_project']['payload']
    assert outer['source']['type']=='NO_SOURCE'
    phases=json.loads(outer['source']['buildspec'])['phases']
    assert phases=={'build':{'on-failure':'ABORT','commands':['python3 /opt/e1/scripts/internal_release/runtime.py']}}
    assert outer['environment']['privileged_mode'] is False
    assert outer['service_role']=='${local.wp3_role_arns[each.key]}'
    assert worker['service_role']=='${aws_iam_role.payload["payload"].arn}'
    assert worker['source']=={'type':'NO_SOURCE','buildspec':'${jsonencode(each.value.buildspec)}'}
    assert worker['environment']['environment_variable']==[]
    assert worker['environment']['image']=='${each.value.runtime.uri}'
    assert worker['environment']['privileged_mode']=='${each.value.privileged}'
    for project in (outer,worker):
        assert not set(project)&{'vpc_config','file_system_locations','secondary_sources'}
        assert project['cache']=={'type':'NO_CACHE'}
        assert project['artifacts']=={'type':'NO_ARTIFACTS'}
    trust=json.loads(r['aws_iam_role']['payload']['assume_role_policy'])['Statement']
    assert len(trust)==1
    st=trust[0]
    assert st['Principal']=={'Service':'codebuild.amazonaws.com'} and st['Action']=='sts:AssumeRole'
    assert st['Condition']['StringEquals']=={'aws:SourceAccount':'${var.account_id}'}
    expected=['arn:aws:codebuild:${var.region}:${var.account_id}:project/'+n for n in c.WORKERS.values()]
    assert st['Condition']['ArnEquals']['aws:SourceArn']==expected
    event=json.loads(r['aws_cloudwatch_event_rule']['completion']['event_pattern'])
    assert event['detail']['project-name']==['e1-controller-release']
    assert r['aws_lambda_permission']['completion']['principal']=='events.amazonaws.com'


class Authority(unittest.TestCase):
    def setUp(self):
        self.ps=policies()
        self.tf=json.loads((ROOT/'terraform/infra/security/modules/controller_compute/main.tf.json').read_text())

    def test_each_worker_stolen_credentials_and_docker_ownership(self):
        for kind in c.WORKERS:
            with self.subTest(worker=kind,compromise='FULL_RUNTIME_AND_ROLE'):
                compromise_ceiling(self.ps['payload'])
                resource=f'arn:aws:logs:{REGION}:{ACCOUNT}:log-group:/aws/codebuild/{c.WORKERS[kind]}:log-stream:fixture'
                self.assertEqual(decision(self.ps['payload'],'logs:PutLogEvents',resource),Decision.ALLOW)
        actions={a for s in self.ps['payload']['Statement'] for a in s['Action']}
        self.assertEqual(actions,{'logs:CreateLogStream','logs:PutLogEvents'})

    def test_controller_scope_and_forbidden_cross_authority(self):
        for binding in c.CONTROLLERS:
            for action in ('iam:PassRole','iam:PutRolePolicy','ecs:UpdateService','elasticloadbalancing:ModifyListener','kms:Decrypt','secretsmanager:GetSecretValue'):
                self.assertEqual(decision(self.ps[binding],action,DENIED[action]),Decision.DENY,(binding,action))
        for kind,name in c.WORKERS.items():
            resource=f'arn:aws:codebuild:{REGION}:{ACCOUNT}:project/{name}'
            self.assertEqual(decision(self.ps['build/release'],'codebuild:StartBuild',resource),Decision.ALLOW)
            self.assertEqual(decision(self.ps['request-gateway/release'],'codebuild:StartBuild',resource),Decision.DENY)
        self.assertEqual(decision(self.ps['request-gateway/release'],'codebuild:StartBuild',DENIED['codebuild:StartBuild']),Decision.ALLOW)
        for binding in ('qualification-finalizer/qualification','status/status-neutral'):
            self.assertEqual(decision(self.ps[binding],'ecr:PutImage',DENIED['ecr:PutImage']),Decision.DENY)
        for binding in ('build/release','request-gateway/release','status/status-neutral'):
            self.assertEqual(decision(self.ps[binding],'s3:PutObject',f'arn:aws:s3:::{EVIDENCE}/qualifications/demo-api/a',{'s3:if-none-match':'*'}),Decision.DENY)

    def test_fixed_topology(self):topology(self.tf)

    def test_evidence_and_quarantine_retention_distinct(self):
        tf=json.loads((ROOT/'terraform/infra/security/modules/protected_resources/main.tf.json').read_text())
        # No generic expiry anywhere in the neutral protected evidence rule.
        authority=json.loads((ROOT/'terraform/infra/security/authority.json').read_text())
        evidence=authority['ownership_closure']['resources']['neutral/artifacts']
        self.assertNotIn('noncurrent_version_expiration',json.dumps(evidence))
        quarantine=self.tf['resource']['aws_s3_bucket_lifecycle_configuration']['quarantine']
        self.assertEqual(quarantine['rule']['noncurrent_version_expiration'],{'noncurrent_days':1})

    def test_request_and_unrelated_identity_reservations(self):
        authority=json.loads((ROOT/'terraform/infra/security/authority.json').read_text())
        self.assertEqual(len(authority['request_identities']),11)
        nodes=authority['controller_compute']['nodes'];self.assertEqual(len(nodes),18)
        self.assertFalse(authority['controller_compute']['operational'])
        for trust in authority['controller_compute']['role_trust'].values():
            self.assertTrue(all(s['Effect']=='Deny' for s in trust['Statement']))
        self.assertEqual(authority['internal_release']['installations'],{})
        self.assertEqual(authority['internal_release']['runtime_approvals'],{})

    def test_worker_authority_mutations_detected_by_effective_decision(self):
        for action,resource in DENIED.items():
            mutant=copy.deepcopy(self.ps['payload'])
            mutant['Statement'].append({'Effect':'Allow','Action':[action],'Resource':[resource]})
            with self.subTest(action=action):
                with self.assertRaises(AssertionError):compromise_ceiling(mutant)

    def test_controller_cross_authority_mutations_detected(self):
        cases=[('request-gateway/release','codebuild:StartBuild',f'arn:aws:codebuild:{REGION}:{ACCOUNT}:project/'+c.WORKERS['image']),
            ('build/release','s3:PutObject',f'arn:aws:s3:::{EVIDENCE}/qualifications/demo-api/a'),
            ('qualification-finalizer/qualification','ecr:PutImage',DENIED['ecr:PutImage']),
            ('status/status-neutral','s3:PutObject',DENIED['s3:PutObject'])]
        cases += [(binding,action,DENIED[action]) for binding in c.CONTROLLERS for action in ('iam:PassRole','ecs:UpdateService')]
        for binding,action,resource in cases:
            with self.subTest(binding=binding,action=action):
                self.assertEqual(decision(self.ps[binding],action,resource),Decision.DENY)
                mutant=copy.deepcopy(self.ps[binding]);mutant['Statement'].append({'Effect':'Allow','Action':[action],'Resource':[resource]})
                self.assertEqual(decision(mutant,action,resource),Decision.ALLOW)

    def test_bounded_missing_object_lookup(self):
        for binding in c.CONTROLLERS:
            resource=f'arn:aws:s3:::{EVIDENCE}'
            for prefix in ('','another/','quarantine/'):
                self.assertEqual(decision(self.ps[binding],'s3:ListBucket',resource,{'s3:prefix':prefix,'s3:max-keys':'1'}),Decision.DENY)
            self.assertEqual(decision(self.ps[binding],'s3:ListBucket',resource,{'s3:prefix':'operations/demo-api/a','s3:max-keys':'1'}),Decision.ALLOW)
            self.assertEqual(decision(self.ps[binding],'s3:ListBucket',resource,{'s3:prefix':'operations/demo-api/a','s3:max-keys':'1000'}),Decision.DENY)

    def test_protected_resource_writer_exclusivity(self):
        replacements={'${var.account_id}':ACCOUNT,'${var.region}':REGION,
            '${var.admin_arn}':f'arn:aws:iam::{ACCOUNT}:role/Admin',
            '${local.evidence_bucket}':EVIDENCE,'${local.exchange_bucket}':EXCHANGE}
        def decode(raw):
            for key,value in replacements.items():raw=raw.replace(key,value)
            return json.loads(raw)
        evidence=decode(self.tf['resource']['aws_s3_bucket_policy']['evidence']['policy'])
        quarantine=decode(self.tf['resource']['aws_s3_bucket_policy']['quarantine']['policy'])
        ecr=decode(self.tf['resource']['aws_ecr_repository_policy']['probe']['policy'])
        def denied(policy,action,resource,principal,header='*',secure='true'):
            context={'aws:PrincipalArn':principal,'s3:if-none-match':header,'aws:SecureTransport':secure}
            match=lambda pattern,value:re.fullmatch(re.escape(pattern).replace(r'\*','.*'),value) is not None
            for st in policy['Statement']:
                if st['Effect']!='Deny':continue
                assert st['Principal']=='*'
                if not any(match(a.lower(),action.lower()) for a in st['Action']):continue
                if not any(match(r,resource) for r in st.get('Resource',['*'])):continue
                conditions=[]
                for operator,values in st.get('Condition',{}).items():
                    assert operator in ('ArnNotEquals','StringNotEquals','Bool')
                    for key,value in values.items():
                        candidates=value if isinstance(value,list) else [value]
                        conditions.append(context.get(key) not in candidates if operator.endswith('NotEquals') else context.get(key) in candidates)
                if all(conditions):return True
            return False
        roles={binding:f'arn:aws:iam::{ACCOUNT}:role/{value[0]}-exec' for binding,value in c.CONTROLLERS.items()}
        roles['payload']=f'arn:aws:iam::{ACCOUNT}:role/{c.WORKER_ROLE}'
        owners={'operations/':'request-gateway/release','attempts/':'build/release','releases/demo-api/by-digest/':'build/release','qualifications/':'qualification-finalizer/qualification','eligibility/':None,'source-approvals/':None}
        for prefix,owner in owners.items():
            for binding,role in roles.items():
                self.assertEqual(denied(evidence,'s3:PutObject',f'arn:aws:s3:::{EVIDENCE}/'+prefix+'a',role),binding!=owner,(prefix,binding))
        for role in roles.values():
            self.assertTrue(denied(evidence,'s3:DeleteObjectVersion',f'arn:aws:s3:::{EVIDENCE}/attempts/a',role))
        build=roles['build/release']
        self.assertTrue(denied(evidence,'s3:PutObject',f'arn:aws:s3:::{EVIDENCE}/attempts/a',build,header=None))
        self.assertTrue(denied(quarantine,'s3:GetObject',f'arn:aws:s3:::{EXCHANGE}/quarantine/a',roles['payload']))
        self.assertFalse(denied(quarantine,'s3:PutObject',f'arn:aws:s3:::{EXCHANGE}/quarantine/a',build))
        for binding,role in roles.items():
            self.assertEqual(denied(ecr,'ecr:PutImage',DENIED['ecr:PutImage'],role),binding!='build/release')
            self.assertTrue(denied(ecr,'ecr:SetRepositoryPolicy',DENIED['ecr:PutImage'],role))

    def test_extra_runtime_source_rejected(self):
        authority=json.loads((ROOT/'terraform/infra/security/authority.json').read_text())
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            for name in internal.SUPPORT:
                target=root/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes((ROOT/name).read_bytes())
            internal.validate(root,authority)
            extra=root/'scripts/internal_release/untracked_helper.py';extra.write_text('print("not admitted")')
            with self.assertRaisesRegex(ValueError,'unadmitted runtime source'):internal.validate(root,authority)

    def test_topology_mutations_detected(self):
        changes=[('outer_privileged',lambda r:r['aws_codebuild_project']['wp3']['environment'].update(privileged_mode=True)),
          ('outer_source',lambda r:r['aws_codebuild_project']['wp3']['source'].update(type='GITHUB')),
          ('outer_payload',lambda r:r['aws_codebuild_project']['wp3']['source'].update(buildspec=json.dumps({'phases':{'build':{'commands':['dotnet test']}}}))),
          ('shared_efs',lambda r:r['aws_codebuild_project']['payload'].update(file_system_locations=[{'location':'controller'}])),
          ('shared_vpc',lambda r:r['aws_codebuild_project']['payload'].update(vpc_config={'vpc_id':'controller'})),
          ('controller_role_on_worker',lambda r:r['aws_codebuild_project']['payload'].update(service_role='${local.wp3_role_arns["build/release"]}')),
          ('worker_role_on_controller',lambda r:r['aws_codebuild_project']['wp3'].update(service_role='${aws_iam_role.payload["payload"].arn}')),
          ('worker_environment_secret',lambda r:r['aws_codebuild_project']['payload']['environment'].update(environment_variable=[{'name':'CONTROLLER_SECRET','value':'canary'}])),
          ('worker_app_buildspec',lambda r:r['aws_codebuild_project']['payload']['source'].update(buildspec='demo-api/buildspec.yml')),
          ('worker_trust_widened',lambda r:r['aws_iam_role']['payload'].update(assume_role_policy=json.dumps({'Statement':[{'Effect':'Allow','Action':'sts:AssumeRole','Principal':{'Service':'codebuild.amazonaws.com'}}]})))]
        for name,change in changes:
            mutant=copy.deepcopy(self.tf);change(mutant['resource'])
            with self.subTest(mutation=name):
                with self.assertRaises((AssertionError,KeyError)):topology(mutant)

    def test_unchanged_mutation_control(self):
        compromise_ceiling(copy.deepcopy(self.ps['payload']))
        topology(copy.deepcopy(self.tf))
