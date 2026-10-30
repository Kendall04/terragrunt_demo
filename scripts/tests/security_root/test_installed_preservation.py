"""Closed installed-graph preservation; all public fixtures are synthetic.

Real readbacks remain private. No fixture digest grants owner approval, and no
Terraform provider/backend is used by the console checks below.
"""
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

import internal
import wp4d
import wp6
from terraform_console import decode

ROOT = Path(__file__).resolve().parents[3]


def encoded(value):
    # Terraform jsonencode's canonical representation (including HTML escapes).
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False).replace(
        '&', '\\u0026').replace('<', '\\u003c').replace('>', '\\u003e')


def fingerprint(value):
    return hashlib.sha256(encoded(value).encode()).hexdigest()


def fixture():
    account, region = '123456789012', 'us-east-1'
    authority = json.loads((ROOT/'terraform/infra/security/authority.json').read_text())
    contract = authority['internal_release']
    installs, runtimes, pins = {}, {}, {}
    evidence = 'demo-release-artifacts-' + account
    for key in internal.PRESERVED_WP3:
        if key.startswith('payload/'):
            worker = key.split('/')[1]; v = contract['workers'][worker]
            runtime = dict(binding=key, owner='SECURITY_ROOT_OWNED', preservation='OBSERVED_EXISTING',
                role=v['role'], support_sha256=contract['support_sha256'],
                uri=f'{account}.dkr.ecr.{region}.amazonaws.com/e1-payload-{worker}@sha256:'+'b'*64)
            configuration = dict(binding=key, account=account, region=region, runtime_image=runtime['uri'],
                support_sha256=contract['support_sha256'], source=v['source'], privileged=v['privileged'])
            role=v['role']; spec=encoded(v['buildspec']); engine='CODEBUILD'
        else:
            v=contract['selected'][key]; engine=v['engine']; role=v['name']+'-exec'
            install=dict({k:v for k,v in authority['control_bundles']['consumer_references'][key].items()
                          if k in ('class','consumer','sha256','key')},
                bucket=f'e1-control-bundles-{account}-{region}', version_id='observed-'+key.replace('/','-'),
                readback='EXACT_VERSION_BYTES_VERIFIED', preservation='OBSERVED_EXISTING',
                configuration=contract['support_sha256'])
            installs[key]=install
            suffix='build' if key=='build/release' else key.replace('/','-')
            runtime=dict(binding=key,owner='SECURITY_ROOT_OWNED',preservation='OBSERVED_EXISTING',
                support_sha256=contract['support_sha256'],
                uri=f'{account}.dkr.ecr.{region}.amazonaws.com/e1-controller-{suffix}@sha256:'+'a'*64)
            configuration=dict(binding=key,account=account,region=region,
                bundle={k:install[k] for k in ('class','consumer','bucket','key','version_id','sha256')},
                runtime_image=runtime['uri'],support_sha256=contract['support_sha256'],
                evidence_bucket=evidence,exchange_bucket=f'e1-quarantine-{account}-{region}')
            spec=encoded({'version':'0.2','phases':{'build':{'on-failure':'ABORT',
                'commands':['python3 /opt/e1/scripts/internal_release/runtime.py']}}}) if key=='build/release' else None
        runtimes[key]=runtime
        identity=internal.preservation_identity(key,v['name'],engine,
            f'arn:aws:iam::{account}:role/{role}',configuration,spec)
        pins[key]=fingerprint(identity)
    # Reuse the independently constructed network fixture, not real identifiers.
    import sys
    sys.path.insert(0,str(ROOT/'scripts/tests/wp4d'))
    from test_wp4d import installed_projection
    ni,nr,bindings=installed_projection(authority)
    network={k:v for k,v in bindings['dev'].items() if k in wp4d.NAT_ENV_FIELDS}
    network['schema']='E1_WP4D_PROTECTED_NAT_NETWORK_V1'
    network['repository']='demo-dev-shared-demo-ms'
    for slot,side in zip(network['nat_slots'],('a','b')):
        slot['spec']['launch_template_version']=2
        slot['asg']='demo-dev-asg-nat-'+side
    natpins={}; configurations={}
    for key,pin in wp4d.HISTORICAL_NAT.items():
        ni[key]={k:ni[key][k] for k in ('binding','bucket','key','version_id','sha256','readback')}
        ni[key].update(sha256=pin['package_sha256'],key='bundles/sha256/'+pin['package_sha256']+'.json',
                       source_commit=wp4d.HISTORICAL_SOURCE,preservation='OBSERVED_EXISTING')
        nr[key].pop('approval'); nr[key].update(package_sha256=pin['package_sha256'],preservation='OBSERVED_EXISTING')
        v=authority['wp4d']['selected'][key]
        config=dict(binding=key,account=account,region=region,environment='dev',
            bundle={k:ni[key][k] for k in ('binding','bucket','key','version_id','sha256')},
            runtime_image=nr[key]['uri'],project=v['name'],evidence_bucket=f'e1-wp4-dev-{account}-{region}',
            dev_evidence_bucket=f'e1-wp4-dev-{account}-{region}',admin_bucket=f'e1-evidence-{account}-{region}',
            repository=network['repository'],resources={},nat_slots=network['nat_slots'])
        identity=dict(account=account,region=region,address=pin['address'],name=v['name'],engine='LAMBDA',
            role=f'arn:aws:iam::{account}:role/{v["name"]}-exec',published_version='4',configuration=config)
        natpins[key]={**pin,'installation_sha256':fingerprint(identity)};configurations[key]=config
    return dict(authority=authority,account_id=account,region=region,admin_arn=f'arn:aws:iam::{account}:role/SeparateAdmin',installations=installs,
        runtime_approvals=runtimes,wp4d_installations={k:ni[k] for k in natpins},
        wp4d_runtime_approvals={k:nr[k] for k in natpins},wp4d_environment_bindings={'dev':network},
        dev_cicd_installation_only=True,wp3_preservation_approval_sha256='c'*64,
        dev_nat_preservation_approval_sha256='c'*64),pins,natpins,configurations


class InstalledPreservation(unittest.TestCase):
    def test_wp3_allowlist_covers_exact_controllers_and_workers(self):
        self.assertEqual(set(internal.PRESERVED_WP3),{'request-gateway/release','build/release',
            'qualification-finalizer/qualification','payload/dotnet','payload/image','payload/probe'})

    def test_no_historical_approval_is_fabricated(self):
        values,_,_,_=fixture()
        for record in values['installations'].values():
            self.assertNotIn('installation',record);self.assertNotIn('publisher',record)
            self.assertNotIn('version_origin',record)
        for record in values['runtime_approvals'].values():self.assertNotIn('approval',record)

    def test_wp3_fingerprint_covers_config_role_address_and_buildspec(self):
        identity=internal.preservation_identity('build/release','controller','CODEBUILD','role',{'bundle':'x'},'build')
        for field in identity:
            changed={**identity,field:'foreign'}
            self.assertNotEqual(fingerprint(identity),fingerprint(changed))

    def test_nat_allowlist_is_dev_only_and_catalog_is_separate(self):
        a=json.loads((ROOT/'terraform/infra/security/authority.json').read_text())
        self.assertEqual(set(wp4d.HISTORICAL_NAT),{'nat-recovery/nat-dev/'+k for k in ('assign_eip','change_rt','disable_sdc')})
        for k,v in wp4d.HISTORICAL_NAT.items():
            self.assertNotEqual(v['package_sha256'],a['wp4d']['selected'][k]['package_sha256'])
            self.assertIn(k,v['address'])

    def test_preservation_inputs_default_inert_and_require_new_approval(self):
        t=json.loads((ROOT/'terraform/infra/security/modules/controller_compute/main.tf.json').read_text())
        for name in ('wp3_preservation_approval_sha256','dev_nat_preservation_approval_sha256'):
            self.assertIsNone(t['variable'][name]['default'])
            self.assertIn('[0-9a-f]{64}',t['variable'][name]['validation']['condition'])
        self.assertIn('var.dev_nat_inhibited',t['variable']['dev_nat_preservation_approval_sha256']['validation']['condition'])

    def test_partial_preservation_has_blocking_preconditions(self):
        t=json.loads((ROOT/'terraform/infra/security/modules/controller_compute/main.tf.json').read_text())
        self.assertIn('wp3_preservation_complete',t['output']['internal_release']['precondition']['condition'])
        self.assertIn('wp4d_historical_nat_ready',t['output']['wp4d']['precondition']['condition'])
        request=json.loads((ROOT/'terraform/infra/security/modules/request_identities/main.tf.json').read_text())
        self.assertEqual(set(wp6.PRESERVED_WP6),{'release','deploy-dev'})
        self.assertEqual(set(wp6.PRESERVED_WP6_SHA256),set(wp6.PRESERVED_WP6))
        self.assertIsNone(request['variable']['wp6_preservation_approval_sha256']['default'])
        self.assertNotIn('wp6_preservation_fingerprints',request['variable'])
        self.assertIn('wp6_preservation_complete',request['output']['wp6']['precondition']['condition'])
        self.assertIn('ADMIN_VERIFIED_G1_G9',request['locals']['wp6_normal_active'])
        self.assertNotIn('governance',json.dumps(wp6.PRESERVED_WP6))

    def test_normal_installation_receipts_remain_required(self):
        t=json.loads((ROOT/'terraform/infra/security/modules/controller_compute/main.tf.json').read_text())
        for term in ('CONDITIONAL_WRITE_RETURN','SECURITY_ADMIN_EXTERNAL_BOOTSTRAP','ADMIN_VERIFIED'):
            self.assertIn(term,t['locals']['wp3_normal_ready'])
            self.assertIn(term,t['locals']['wp4d_ready'])

    def test_limited_ecr_selection_is_closed_not_caller_controlled(self):
        t=json.loads((ROOT/'terraform/infra/security/modules/controller_compute/main.tf.json').read_text())
        self.assertEqual(set(t['locals']['wp4d_installed_repository_bindings']),set(wp4d.HISTORICAL_DELIVERY)|set(wp4d.HISTORICAL_NAT))
        self.assertIn('!var.dev_cicd_installation_only',t['locals']['wp4d_repositories'])
        self.assertNotIn('var.repositories',t['locals']['wp4d_repositories'])
        self.assertIn('!var.dev_cicd_installation_only',t['locals']['wp5_repositories'])
        self.assertIn('e1-controller-status-status-neutral',t['locals']['runtime_repositories'])
        self.assertEqual(t['resource']['terraform_data']['declaration']['for_each'],
                         '${var.dev_cicd_installation_only ? {} : local.nodes}')
        self.assertEqual(t['output']['foundation']['precondition'],
                         t['resource']['terraform_data']['declaration']['lifecycle']['precondition'])
        protected=json.loads((ROOT/'terraform/infra/security/modules/protected_resources/main.tf.json').read_text())
        prod=[v for resources in protected['resource'].values() for name,v in resources.items() if name.startswith('prod_')]
        self.assertEqual(len(prod),29)
        self.assertTrue(all('count' not in v and 'for_each' not in v for v in prod))


def check_terraform(terraform,environment):
    values,pins,natpins,natconfigs=fixture()
    module=json.loads((ROOT/'terraform/infra/security/modules/controller_compute/main.tf.json').read_text())
    local={k:v for k,v in module['locals'].items() if k.startswith(('wp3_','worker_','wp4d_'))
           and k not in ('wp3_role_arns','wp4d_policy_templates','wp4d_role_arns')}
    # Only the closed admission/config/selector graph, no AWS resource references.
    local={k:v for k,v in local.items() if 'aws_' not in str(v) or k in (
        'wp3_preservation_identities','worker_preservation_identities','wp4d_nat_preservation_identities',
        'wp4d_historical_installations','wp4d_historical_nat_installations')}
    local.update(evidence_bucket='demo-release-artifacts-'+values['account_id'],
        exchange_bucket='e1-quarantine-'+values['account_id']+'-us-east-1',nodes={},
        payloads=module['locals']['payloads'],wp3_preservation_fingerprints=pins,
        wp4d_historical_nat_installations=natpins)
    with tempfile.TemporaryDirectory(prefix='installed-preservation-offline-') as directory:
        path=Path(directory)/'main.tf.json'
        def evaluate(changes=None,locals_override=None):
            current={k:v.get('default') for k,v in module['variable'].items() if 'default' in v}
            current.update(copy.deepcopy(values));current.update(changes or {})
            path.write_text(json.dumps({'variable':{k:{'type':'any','default':v} for k,v in current.items()},
                'locals':{**local,**(locals_override or {}),'nat_valid':module['variable']['dev_nat_preservation_approval_sha256']['validation']['condition'],
                'wp4d_valid':module['output']['wp4d']['precondition']['condition']}}),encoding='utf-8')
            query='jsonencode({wp3=keys(local.wp3_active),workers=keys(local.payloads),wp3_valid=local.wp3_preservation_complete,nat=keys(local.wp4d_historical_nat_ready),nat_valid=local.nat_valid,wp4d_valid=local.wp4d_valid,config=local.wp4d_config,repositories=keys(local.wp4d_repositories)})'
            run=subprocess.run([terraform,'console','-no-color'],cwd=directory,input=query+'\n',
                capture_output=True,text=True,env=environment,timeout=30)
            if run.returncode or 'Error:' in run.stderr:raise AssertionError(run.stderr)
            return decode(run.stdout)
        for limited in (True,False):
            out=evaluate({'dev_cicd_installation_only':limited})
            assert out['wp3_valid'] and out['nat_valid'] and out['wp4d_valid'], out
            assert len(out['wp3'])==3 and out['workers']==['dotnet','image','probe'] and out['nat']==sorted(natpins)
            assert len(out['repositories'])==(6 if limited else 16)
            for key,config in natconfigs.items():assert json.loads(out['config'][key])==config
        assert not evaluate({'wp3_preservation_approval_sha256':None})['wp3']
        assert not evaluate({'dev_nat_preservation_approval_sha256':None})['nat']
        assert not evaluate({'dev_nat_inhibited':False})['nat_valid']
        assert not evaluate({'dev_nat_inhibited':False})['nat']
        # Every installed object is required; no partial approval can turn into deletion.
        for missing in values['installations']:
            i=copy.deepcopy(values['installations']);del i[missing]
            assert not evaluate({'installations':i})['wp3_valid']
        for missing in values['runtime_approvals']:
            r=copy.deepcopy(values['runtime_approvals']);del r[missing]
            assert not evaluate({'runtime_approvals':r})['wp3_valid']
        for field in ('version_id','sha256','bucket','key','readback','configuration'):
            i=copy.deepcopy(values['installations'])
            for record in i.values():record[field]='foreign'
            assert not evaluate({'installations':i})['wp3_valid']
        for field in ('uri','support_sha256','binding','owner'):
            r=copy.deepcopy(values['runtime_approvals'])
            for record in r.values():record[field]='foreign'
            assert not evaluate({'runtime_approvals':r})['wp3_valid']
        for field in ('version_id','sha256','source_commit','readback'):
            i=copy.deepcopy(values['wp4d_installations'])
            for record in i.values():record[field]='foreign'
            assert not evaluate({'wp4d_installations':i})['wp4d_valid']
        for value in (None,3):
            b=copy.deepcopy(values['wp4d_environment_bindings'])
            for slot in b['dev']['nat_slots']:slot['spec']['launch_template_version']=value
            assert not evaluate({'wp4d_environment_bindings':b})['wp4d_valid']
        for field in ('account_id','region'):
            assert not evaluate({field:'foreign'})['wp3_valid']
            assert not evaluate({field:'foreign'})['wp4d_valid']
        assert not evaluate(locals_override={'wp3_outer_buildspec':{'version':'foreign'}})['wp3_valid']
    check_reconciliation(terraform,environment)
    print('Installed graph: closed WP3/NAT/WP6 preservation, negative mutations, inhibition and limited selectors PASS')


def check_reconciliation(terraform, environment):
    """Evaluate the generated expressions; fixtures never approve real resources."""
    authority=json.loads((ROOT/'terraform/infra/security/authority.json').read_text())
    request=json.loads((ROOT/'terraform/infra/security/modules/request_identities/main.tf.json').read_text())
    compute=json.loads((ROOT/'terraform/infra/security/modules/controller_compute/main.tf.json').read_text())
    foundation=json.loads((ROOT/'terraform/infra/security/modules/lifecycle_foundations/main.tf.json').read_text())
    account='123456789012';region='us-east-1';readbacks={};pins={}
    for key,record in wp6.PRESERVED_WP6.items():
        name='e1-gateway-'+key
        readback=dict(function_name=name,qualified_arn=f'arn:aws:lambda:{region}:{account}:function:{name}:{record["gateway_version"]}',
            role=f'arn:aws:iam::{account}:role/{name}-exec',image_uri=f'{account}.dkr.ecr.{region}.amazonaws.com/fixture@sha256:'+'a'*64,
            configuration=encoded({'binding':'request-gateway/'+key,'fixture':True}))
        identity=dict(identity=key,role_address='module.request_identities.aws_iam_role.request['+json.dumps(key)+']',
            policy_address='module.request_identities.aws_iam_role_policy.wp6['+json.dumps(key)+']',role_name='e1-request-'+key,
            role_arn=f'arn:aws:iam::{account}:role/e1-request-{key}',trust=wp6.trust(key,record,account),
            policy=wp6.policy(key,record,account,region),gateway=readback)
        pins[key]=fingerprint(identity);readbacks[key]=readback
    values=dict(authority=authority,account_id=account,region=region,endpoints={
        'request-gateway/'+k:v['qualified_arn'] for k,v in readbacks.items()},dev_cicd_installation_only=True,
        wp6_preservation_approval_sha256='c'*64,wp6_preservation_required=True,wp6_preservation_readbacks=readbacks,
        latest_version='27',preserved={k:{} for k in internal.PRESERVED_WP3})
    local=copy.deepcopy(request['locals']);local['wp6_preservation_fingerprints']=pins
    for key in ('runtime_repository_reservations','runtime_repositories','wp5_repository_reservations','wp5_repositories','nodes'):
        local[key]=compute['locals'][key]
    local['wp3_preserved_ready']='${var.preserved}'
    local['completion_qualifier']=compute['locals']['wp3_completion_qualifier'].replace(
        'aws_lambda_function.wp3["qualification-finalizer/qualification"].version','var.latest_version')
    local['foundation_selection']=foundation['resource']['aws_s3_bucket']['state']['for_each']
    local['declaration_selection']=compute['resource']['terraform_data']['declaration']['for_each']
    local['declaration_guard']=compute['output']['foundation']['precondition']['condition']
    concurrency=compute['resource']['aws_lambda_function']['wp3']['reserved_concurrent_executions'][2:-1].replace('each.key','key')
    local['concurrency']='${{for key in ["request-gateway/release","qualification-finalizer/qualification"]:key=>'+concurrency+'}}'
    with tempfile.TemporaryDirectory(prefix='security-reconciliation-offline-') as directory:
        path=Path(directory)/'main.tf.json'
        def evaluate(changes=None):
            current=copy.deepcopy(values);current.update(changes or {})
            path.write_text(json.dumps({'variable':{k:{'type':'any','default':v} for k,v in current.items()},'locals':local}),encoding='utf-8')
            query='jsonencode({active=keys(local.wp6_active),complete=local.wp6_preservation_complete,trusts=local.wp6_trusts,policies=local.wp6_policies,qualifier=local.completion_qualifier,concurrency=local.concurrency,repositories=keys(local.runtime_repositories),wp5=keys(local.wp5_repositories),states=local.foundation_selection,declarations=keys(local.declaration_selection),declaration_guard=local.declaration_guard})'
            p=subprocess.run([terraform,'console','-no-color'],cwd=directory,input=query+'\n',capture_output=True,text=True,env=environment,timeout=30)
            if p.returncode or 'Error:' in p.stderr:raise AssertionError(p.stderr)
            return decode(p.stdout)
        out=evaluate();assert out['active']==['deploy-dev','release'] and out['complete']
        for key,record in wp6.PRESERVED_WP6.items():
            assert out['trusts'][key]==wp6.trust(key,record,account)
            assert out['policies'][key]==wp6.policy(key,record,account,region)
        assert out['qualifier']=='1' and out['concurrency']=={'request-gateway/release':0,'qualification-finalizer/qualification':1}
        assert len(out['repositories'])==6 and not out['wp5'] and out['states']==['dev'] and not out['declarations'] and out['declaration_guard']
        for field in ('creation_supported','operational'):
            changed=copy.deepcopy(authority);changed['controller_compute'][field]=True
            assert not evaluate({'authority':changed})['declaration_guard']
        for digest in (None,'not-an-approval'):
            out=evaluate({'wp6_preservation_approval_sha256':digest});assert not out['complete'] and not out['active']
        for missing in readbacks:
            changed=copy.deepcopy(readbacks);del changed[missing]
            assert not evaluate({'wp6_preservation_readbacks':changed})['complete']
        for field in ('function_name','qualified_arn','role','image_uri','configuration'):
            changed=copy.deepcopy(readbacks);changed['release'][field]='foreign'
            assert not evaluate({'wp6_preservation_readbacks':changed})['complete']
        for field in ('account_id','region'):
            assert not evaluate({field:'foreign'})['complete']
        out=evaluate({'dev_cicd_installation_only':False,'wp6_preservation_approval_sha256':None,
                      'wp6_preservation_required':False,'preserved':{}})
        assert out['complete'] and not out['active'] and out['qualifier']=='27'
        assert all(v==1 for v in out['concurrency'].values())
        assert len(out['repositories'])==7 and len(out['wp5'])==8 and out['states']==['dev','prod'] and len(out['declarations'])==18
