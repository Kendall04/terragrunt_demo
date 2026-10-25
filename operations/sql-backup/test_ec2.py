"""Offline review/provisioning contracts; no AWS, real SQL or host installation."""
import copy
import hashlib
import io
import json
import os
from pathlib import Path
import sys
import tarfile
import tempfile
import unittest

BASE=Path(__file__).resolve().parent
sys.path.insert(0,str(BASE))
import ec2_prepare as plan
import ec2_credentials as credentials

class Packet(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='sql-ec2-review-'); self.root=Path(self.temp.name)
        self.snapshot={'Identity':{'Account':plan.ACCOUNT,'Arn':plan.ADMIN},'Region':plan.REGION,'ReadUtc':'2026-10-16T00:00:00Z',
            'Role':{'Arn':plan.ROLE},'Versioning':{'Status':'Enabled'},'BackupKey':{'Arn':plan.KEY,'State':'Enabled'},
            'Encryption':{'ServerSideEncryptionConfiguration':{'Rules':[{'ApplyServerSideEncryptionByDefault':{'KMSMasterKeyID':plan.KEY},'BucketKeyEnabled':False}]}},
            'SecretsMetadata':[{'Arn':plan.SA,'KmsKeyId':plan.TEXT_KEY}], 'Instances':[], 'Vpcs':[{'Id':'vpc-12345678','Default':True}],
            'BackupKeyPolicy':{'Version':'2012-10-17','Statement':[{'Sid':'ExistingAdministrator','Action':'kms:PutKeyPolicy'}]},
            'BucketPolicy':{'Version':'2012-10-17','Statement':[{'Sid':'ExistingTLS','Action':'s3:*','Effect':'Deny'}]},
            'Lifecycle':{'Rules':[{'ID':'preserved-lab','Status':'Enabled','Filter':{'Prefix':'historical/'} ,'Expiration':{'Days':2}}]}}
        self.snapshot['PriceQuotes']={name:[{'Unit':'Hrs','USD':rate}] for name,rate in [('t3a.small','0.0188'),('t3.micro','0.0104')]}
        self.archive=self.root/'package.tar'
        manifest={'Target':'linux-x64','Runtime':'10.0.13','SourceCommit':'a'*40,'Files':{name:{} for name in ('host.py','package.py','ec2_credentials.py')}}
        body=json.dumps(manifest).encode()
        with tarfile.open(self.archive,'w') as out:
            entry=tarfile.TarInfo('manifest.json');entry.size=len(body);out.addfile(entry,io.BytesIO(body))
        self.sha=hashlib.sha256(self.archive.read_bytes()).hexdigest(); self.out=self.root/'review'
    def tearDown(self): self.temp.cleanup()
    def render(self,network=None): return plan.render(self.snapshot,self.archive,self.sha,self.out,network)
    def read(self,name): return json.loads((self.out/name).read_text())
    def test_preserves_existing_policies_retention_and_explicit_absence(self):
        before=copy.deepcopy(self.snapshot); receipt=self.render()
        self.assertEqual(before,self.snapshot); self.assertFalse(receipt['AwsMutations'])
        self.assertEqual(self.snapshot['BucketPolicy']['Statement'][0],self.read('bucket-policy.after.json')['Statement'][0])
        self.assertEqual(self.snapshot['BackupKeyPolicy']['Statement'][0],self.read('backup-key-policy.after.json')['Statement'][0])
        self.assertEqual(self.snapshot['Lifecycle']['Rules'][0],self.read('lifecycle.after.json')['Rules'][0])
        self.assertFalse((self.out/'s3-endpoint.candidate.tf.json').exists())
        approval=self.read('approval.json');self.assertEqual('ORIGINAL_DEV_NETWORK_ABSENT',approval['Network']['Status'])
        self.assertFalse(approval['Security']['OriginalTextKeyPolicyChanged']); self.assertEqual(2,approval['Acceptance']['RealHourlyTimerActivations'])
    def test_no_delete_list_passrole_or_secret_creation_grant(self):
        self.render(); policy=self.read('role-inline-policy.json')
        actions=[]
        for s in policy['Statement']: actions += [s['Action']] if isinstance(s['Action'],str) else s['Action']
        self.assertEqual({'s3:PutObject','s3:GetObject','s3:GetObjectVersion','kms:GenerateDataKey','kms:Decrypt'},set(actions))
        self.assertNotIn('lab-fa48a32dc9',json.dumps(policy)); self.assertNotIn('secretsmanager:',json.dumps(policy))
        self.assertEqual(plan.ROLE,self.read('backup-key-policy.after.json')['Statement'][1]['Principal']['AWS'])
    def test_new_prefix_and_artifact_require_conditional_encrypted_writes(self):
        self.render(); statements=self.read('bucket-policy.after.json')['Statement'][1:]
        self.assertEqual(6,len(statements));self.assertTrue(all(s['Effect']=='Deny' for s in statements))
        self.assertEqual(2,sum('s3:if-none-match' in s['Condition']['StringNotEquals'] for s in statements))
    def test_wrong_account_key_or_package_rejected_without_writes(self):
        for field in ('account','key','package'):
            saved=copy.deepcopy(self.snapshot); saved_sha=self.sha
            if field=='account': self.snapshot['Identity']['Account']='000000000000'
            if field=='key': self.snapshot['BackupKey']['State']='Disabled'
            if field=='package': self.sha='0'*64
            with self.assertRaises(ValueError): self.render()
            self.assertFalse(self.out.exists()); self.snapshot=saved;self.sha=saved_sha
    def test_existing_review_is_never_overwritten(self):
        self.render();before=(self.out/'approval.json').read_bytes()
        with self.assertRaisesRegex(ValueError,'NEW_REVIEW'): self.render()
        self.assertEqual(before,(self.out/'approval.json').read_bytes())
    def test_price_increase_cannot_silently_keep_old_five_dollar_envelope(self):
        self.snapshot['PriceQuotes']['t3a.small'][0]['USD']='2.00'
        with self.assertRaisesRegex(ValueError,'REESTIMATE'): self.render()
        self.assertFalse(self.out.exists())
    def test_default_vpc_and_duplicate_private_routes_are_rejected(self):
        network={'VpcId':'vpc-12345678','PrivateRouteTableIds':['rtb-12345678','rtb-12345679'],'Project':'demo','Environment':'dev'}
        with self.assertRaisesRegex(ValueError,'PROJECT_VPC'): self.render(network)
        self.assertFalse(self.out.exists())
        self.snapshot['Vpcs']=[{'Id':network['VpcId'],'Default':False,'Tags':[{'Key':'Project','Value':'demo'},{'Key':'Environment','Value':'dev'}]}]
        network['PrivateRouteTableIds'][1]=network['PrivateRouteTableIds'][0]
        with self.assertRaisesRegex(ValueError,'TWO_DISTINCT'): self.render(network)
    def test_two_route_candidate_is_explicit_admin_review_only(self):
        network={'VpcId':'vpc-12345678','PrivateRouteTableIds':['rtb-12345678','rtb-12345679'],'Project':'demo','Environment':'dev'}
        self.snapshot['Vpcs']=[{'Id':network['VpcId'],'Default':False,'Tags':[{'Key':'Project','Value':'demo'},{'Key':'Environment','Value':'dev'}]}]
        self.render(network)
        endpoint=self.read('s3-endpoint.candidate.tf.json')['resource']['aws_vpc_endpoint']['sql_backup_s3']
        self.assertEqual('Gateway',endpoint['vpc_endpoint_type']);self.assertEqual(network['PrivateRouteTableIds'],endpoint['route_table_ids'])
    def test_observed_private_sql_host_is_recorded_without_claiming_readiness(self):
        self.snapshot['Instances']=[{'Id':'i-12345678901234567','PublicIp':None,'Profile':f'arn:aws:iam::{plan.ACCOUNT}:instance-profile/demo-dev-data-sql-ec2-profile','Tags':[{'Key':'Name','Value':'demo-dev-data-sql-instance'}]}]
        self.render();runtime=self.read('approval.json')['Runtime']
        self.assertEqual('i-12345678901234567',runtime['InstanceId']);self.assertEqual('OBSERVED_NEEDS_SSM_SQL_VERIFICATION',runtime['HostStatus'])

class FakeHost:
    def __init__(self,sql_failure=False,wrong_identity=False): self.calls=[];self.batches=[];self.sql_failure=sql_failure;self.wrong=wrong_identity
    def aws(self,*args):
        self.calls.append(args)
        if args[0]=='sts':return {'Account':'000000000000' if self.wrong else plan.ACCOUNT,'Arn':f'arn:aws:sts::{plan.ACCOUNT}:assumed-role/{credentials.ROLE}/i-synthetic'}
        return {'SecretString':'SECRET-SENTINEL-SA'}
    def sql(self,password,batch):
        self.batches.append((password,batch))
        if self.sql_failure: raise ValueError('SQL_BOOTSTRAP_FAILED_OR_UNKNOWN')

class Credential(unittest.TestCase):
    def setUp(self):
        Packet.setUp(self); Packet.render(self);self.system=self.root/'fixture';self.system.mkdir()
        base=self.system/'etc/terragrunt-demo/sql-backup';base.mkdir(parents=True)
        (base/'config.json').write_bytes((self.out/'config.json').read_bytes())
        installed=self.system/'opt/terragrunt-demo/sql-backup';installed.mkdir(parents=True)
        (installed/'install-receipt.json').write_text(json.dumps({'PackageSha256':self.sha,'SourceCommit':'a'*40}))
        units=self.system/'etc/systemd/system';units.mkdir(parents=True);(units/'sql-backup.service').write_text('isolated inert fixture')
        self.confirm=hashlib.sha256((self.out/'approval.json').read_bytes()).hexdigest();self.host=FakeHost()
    def tearDown(self): Packet.tearDown(self)
    def call(self,apply=False,confirmation=None): return credentials.operate(self.out/'approval.json',self.out/'config.json',self.system,apply,confirmation,self.host)
    def test_default_plan_has_no_process_calls_or_credentials(self):
        self.assertEqual('CREDENTIAL_PLAN',self.call()['Status']);self.assertEqual([],self.host.calls)
        self.assertFalse((self.system/'etc/terragrunt-demo/sql-backup/credentials').exists())
    def test_missing_confirmation_blocks_before_secret_access(self):
        with self.assertRaisesRegex(ValueError,'CONFIRMATION'): self.call(True)
        self.assertEqual([],self.host.calls)
    def test_real_host_is_never_used_by_fixture(self): self.assertNotEqual(Path('/'),self.system)
    @unittest.skipUnless(os.geteuid()==0,'root only inside isolated fixture container')
    def test_root_fixture_keeps_secrets_local_and_refuses_replay(self):
        result=self.call(True,self.confirm);self.assertEqual('PROVISIONED_NOT_STARTED',result['Status'])
        base=self.system/'etc/terragrunt-demo/sql-backup/credentials'
        self.assertEqual(0o700,base.stat().st_mode&0o777)
        for name in ('backup-connection','verify-connection','bootstrap-receipt.json'): self.assertEqual(0o600,(base/name).stat().st_mode&0o777)
        receipt=(base/'bootstrap-receipt.json').read_text(); self.assertNotIn('SECRET-SENTINEL',receipt+json.dumps(result))
        self.assertIn('Database=master',(base/'verify-connection').read_text())
        self.assertIn('GRANT CREATE DATABASE',self.host.batches[0][1]);self.assertNotIn('db_owner',self.host.batches[0][1])
        calls=len(self.host.calls)
        with self.assertRaisesRegex(ValueError,'EXISTING_CREDENTIAL'):self.call(True,self.confirm)
        self.assertEqual(calls,len(self.host.calls))
    @unittest.skipUnless(os.geteuid()==0,'root only inside isolated fixture container')
    def test_failed_sql_keeps_unknown_receipt_and_no_connection_files(self):
        self.host.sql_failure=True
        with self.assertRaisesRegex(ValueError,'UNKNOWN'):self.call(True,self.confirm)
        base=self.system/'etc/terragrunt-demo/sql-backup/credentials'
        self.assertEqual('PREPARING_OR_UNKNOWN',json.loads((base/'bootstrap-receipt.json').read_text())['Status'])
        self.assertFalse((base/'backup-connection').exists())
        with self.assertRaisesRegex(ValueError,'EXISTING_CREDENTIAL'):self.call(True,self.confirm)
    @unittest.skipUnless(os.geteuid()==0,'root only inside isolated fixture container')
    def test_wrong_instance_role_never_reads_secret_or_writes_credentials(self):
        self.host.wrong=True
        with self.assertRaisesRegex(ValueError,'ROLE_MISMATCH'):self.call(True,self.confirm)
        self.assertEqual(1,len(self.host.calls));self.assertFalse((self.system/'etc/terragrunt-demo/sql-backup/credentials').exists())
    def test_sql_names_and_passwords_cannot_inject_statements(self):
        with self.assertRaisesRegex(ValueError,'DATABASE'):credentials.sql_batch('demodb];DROP DATABASE x','Synthetic!'+'a'*48,'Synthetic!'+'b'*48)
        with self.assertRaisesRegex(ValueError,'PASSWORD'):credentials.sql_batch('demodb',"';DROP LOGIN sa;--",'Synthetic!'+'b'*48)
    def private_approval(self,endpoint='10.77.1.8'):
        approval=json.loads((self.out/'approval.json').read_text())
        approval['Runtime'].update(SqlEndpoint=endpoint,InstanceId='i-'+'2'*17)
        (self.out/'approval.json').write_text(json.dumps(approval))
        self.confirm=hashlib.sha256((self.out/'approval.json').read_bytes()).hexdigest()
        return approval
    def test_private_endpoint_is_explicit_and_plan_only(self):
        self.private_approval()
        result=self.call();self.assertEqual(result['SqlEndpoint'],'10.77.1.8')
        self.assertEqual(self.host.calls,[])
    def test_wildcard_public_and_noncanonical_endpoints_refuse_before_secret_access(self):
        for bad in ('0.0.0.0','::','8.8.8.8','169.254.169.254','10.077.1.8','10.77.1.8;bad'):
            self.private_approval(bad)
            with self.assertRaisesRegex(ValueError,'PRIVATE_SQL_ENDPOINT'):self.call()
        self.assertEqual(self.host.calls,[])
    @unittest.skipUnless(os.geteuid()==0,'root only inside isolated fixture')
    def test_private_credentials_and_sql_bootstrap_use_same_bound_own_ip(self):
        from unittest.mock import Mock
        self.private_approval()
        self.host.identity=Mock(return_value={'accountId':plan.ACCOUNT,'region':'us-east-1',
            'instanceId':'i-'+'2'*17,'privateIp':'10.77.1.8'})
        self.host.sql=Mock()
        result=self.call(True,self.confirm)
        self.assertEqual(result['Status'],'PROVISIONED_NOT_STARTED')
        self.assertEqual(self.host.sql.call_args.kwargs,{'endpoint':'10.77.1.8'})
        base=self.system/'etc/terragrunt-demo/sql-backup/credentials'
        for name in ('backup-connection','verify-connection'):
            self.assertIn('Server=10.77.1.8,1433;', (base/name).read_text())
        self.assertNotIn('SECRET-SENTINEL',json.dumps(result))
    @unittest.skipUnless(os.geteuid()==0,'root only inside isolated fixture')
    def test_foreign_native_ip_or_generation_never_reads_sa_secret(self):
        from unittest.mock import Mock
        self.private_approval()
        self.host.identity=Mock(return_value={'accountId':plan.ACCOUNT,'region':'us-east-1',
            'instanceId':'i-'+'2'*17,'privateIp':'10.77.1.9'})
        with self.assertRaisesRegex(ValueError,'PRIVATE_ENDPOINT_HOST'):self.call(True,self.confirm)
        self.assertEqual(len(self.host.calls),1)
        self.assertFalse((self.system/'etc/terragrunt-demo/sql-backup/credentials').exists())
    def test_new_endpoint_cannot_reuse_old_review_acknowledgement(self):
        old=self.confirm;self.private_approval()
        with self.assertRaisesRegex(ValueError,'CONFIRMATION'):self.call(True,old)
        self.assertEqual(self.host.calls,[])
    def test_host_aws_environment_ignores_all_existing_credentials(self):
        env=credentials.HostPort().environment()
        self.assertNotIn('AWS_PROFILE',env);self.assertNotIn('AWS_ACCESS_KEY_ID',env)
        self.assertEqual('/dev/null',env['AWS_SHARED_CREDENTIALS_FILE']);self.assertEqual('true',env['AWS_EC2_METADATA_V1_DISABLED'])

if __name__=='__main__':unittest.main(verbosity=2)
