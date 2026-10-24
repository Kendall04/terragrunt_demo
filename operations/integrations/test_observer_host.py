"""Host/distribution source and archive tests. No AWS, systemd, installation or credentials."""
import ast
import gzip
import hashlib
import io
import json
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import patch
import observer_host as h

ROOT=Path(__file__).resolve().parents[2]
TF=ROOT/'terraform/infra/sentinel-backup'
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
class HostTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.c=self.root/'component';self.c.mkdir()
        files={'SqlBackup':b'NOT_A_NATIVE_BINARY_TEST_ONLY','libcoreclr.so':b'fake','SqlBackup.pdb':b'debug-only','SqlBackup.runtimeconfig.json':b'{}'}
        for name,b in files.items():(self.c/name).write_bytes(b)
        m={'Component':'SqlBackup','Runtime':'10.0.13','Rid':'linux-x64','SelfContained':True,'SourceCommit':'b'*40,'Files':{n:{'Sha256':digest(self.c/n),'Bytes':len(b)} for n,b in files.items()}}
        (self.c/'local-component-manifest.json').write_text(json.dumps(m));self.msha=digest(self.c/'local-component-manifest.json');self.bundle=self.root/'bundle.tar.gz'
        self.config={'account':'341936017254','region':'us-east-1','run_id':'ecs-sentinel-offline','subject':'sql-backup','bucket':'existing-backup-test-bucket','prefix':'old-native-read-only','missing_prefix':'sentinel-observer/ecs-sentinel-offline/empty','backup_key_arn':'arn:aws:kms:us-east-1:341936017254:key/'+'1'*8+'-'+'1'*4+'-'+'1'*4+'-'+'1'*4+'-'+'1'*12,'text_key_arn':'arn:aws:kms:us-east-1:341936017254:key/'+'2'*8+'-'+'2'*4+'-'+'2'*4+'-'+'2'*4+'-'+'2'*12,'database':'DemoDb','max_age_hours':168,'expires_at':'2026-10-25T00:00:00Z','cadence_seconds':60,'publish_attempts':3}
    def tearDown(self):self.tmp.cleanup()
    def build(self):return h.build(self.c,self.msha,'a'*40,self.bundle)
    def test_cli_wrong_source_commit_refused_before_bundle_write(self):
        args=['observer_host','build','--component',str(self.c),'--component-manifest-sha',self.msha,'--source-commit','a'*40,'--output',str(self.bundle)]
        with patch('sys.argv',args),patch.object(h.subprocess,'check_output',return_value='c'*40):
            with self.assertRaisesRegex(h.Refused,'SOURCE_COMMIT_MISMATCH'):h.main()
        self.assertFalse(self.bundle.exists())
    def test_bundle_inspection_and_exact_component_lineage(self):
        m=self.build();v=h.inspect(self.bundle,m['bundleSha256']);self.assertEqual(v['componentSourceCommit'],'b'*40);self.assertEqual(v['excludedSymbols'],['SqlBackup.pdb']);self.assertNotIn('checker/SqlBackup.pdb',v['files']);self.assertFalse(m['uploaded'])
    def test_bundle_is_byte_deterministic(self):
        m=self.build();other=self.root/'second.tar.gz';v=h.build(self.c,self.msha,'a'*40,other);self.assertEqual(m['bundleSha256'],v['bundleSha256'])
    def test_changed_component_refused(self):
        (self.c/'SqlBackup').write_bytes(b'changed')
        with self.assertRaisesRegex(h.Refused,'CONTENT_CHANGED'):self.build()
    def test_extra_component_file_refused(self):
        (self.c/'credentials').write_bytes(b'no secret value')
        with self.assertRaisesRegex(h.Refused,'INVENTORY'):self.build()
    def test_wrong_manifest_hash_refused(self):
        with self.assertRaisesRegex(h.Refused,'MANIFEST_HASH'):h.build(self.c,'0'*64,'a'*40,self.bundle)
    def test_wrong_bundle_digest_refused(self):
        self.build()
        with self.assertRaisesRegex(h.Refused,'BUNDLE_HASH'):h.inspect(self.bundle,'0'*64)
    def test_path_traversal_and_symlink_refused(self):
        for index,(name,typ) in enumerate([('../escape',tarfile.REGTYPE),('link',tarfile.SYMTYPE)]):
            p=self.root/('unsafe'+str(index)+'.tar.gz')
            with tarfile.open(p,'w:gz') as t:
                i=tarfile.TarInfo(name);i.type=typ;i.size=0;t.addfile(i,io.BytesIO())
            with self.assertRaisesRegex(h.Refused,'UNSAFE_MEMBER'):h.inspect(p,digest(p))
    def test_config_refuses_wrong_identity_and_credential_fields(self):
        for changes in [{'account':'999999999999'},{'region':'us-west-2'},{'password':'not-an-actual-secret'},{'missing_prefix':'old-native-read-only'},{'cadence_seconds':0},{'publish_attempts':4}]:
            with self.assertRaises(h.Refused):h.validate(self.config|changes)
    def test_modes_preserve_original_identity_and_isolate_state(self):
        baseline=h.options(self.config,'healthy');missing=h.options(self.config,'missing');stale=h.options(self.config,'stale')
        self.assertEqual(baseline['Prefix'],self.config['prefix']);self.assertEqual(missing['Prefix'],self.config['missing_prefix']);self.assertEqual(stale['ProposedMaxAgeHours'],1)
        self.assertNotEqual(baseline['StagingDirectory'],missing['StagingDirectory']);self.assertTrue(baseline['StagingDirectory'].startswith('/var/lib/'))
        for k in ['Bucket','BackupKeyArn','TextKeyArn','ExpectedEc2RoleName']:self.assertEqual(baseline[k],missing[k])
    def test_pending_or_running_work_never_discarded_for_mode_change(self):
        for active,pending in [(True,False),(False,True),(True,True)]:
            with self.assertRaisesRegex(h.Refused,'ACTIVE_OR_PENDING'):h.can_change(active,pending)
        h.can_change(False,False)
    def test_units_have_no_force_kill_restart_or_automatic_enable(self):
        u=h.unit(self.config);t=h.timer(self.config);self.assertIn('SendSIGKILL=no',u);self.assertIn('Restart=no',u);self.assertIn('ProtectSystem=strict',u);self.assertIn('/opt/terragrunt-demo/observer/observer_host.py tick',u);self.assertIn('OnUnitActiveSec=60',t)
        source=Path(h.__file__).read_text();self.assertNotIn("system('enable'",source);self.assertNotIn('kill -9',source)
    def test_environment_does_not_forward_credential_values(self):
        with patch.dict(h.os.environ,{'AWS_ACCESS_KEY_ID':'TEST_ONLY','AWS_SECRET_ACCESS_KEY':'TEST_ONLY','AWS_SESSION_TOKEN':'TEST_ONLY','AWS_PROFILE':'TEST_ONLY','AWS_ENDPOINT_URL':'TEST_ONLY'}):
            e=h.environment();self.assertNotIn('AWS_ACCESS_KEY_ID',e);self.assertNotIn('AWS_SESSION_TOKEN',e);self.assertNotIn('AWS_PROFILE',e);self.assertNotIn('AWS_ENDPOINT_URL',e);self.assertEqual(e['AWS_EC2_METADATA_V1_DISABLED'],'true')
    def test_python39_syntax_and_bootstrap_no_download_installer(self):
        for name in ['observer_host.py','../sql-backup/observer.py','../sql-backup/sentinel_publish.py','../sql-backup/signals.py']:ast.parse((Path(h.__file__).parent/name).read_text(),feature_version=(3,9))
        b=(TF/'modules/observer/bootstrap.sh.tftpl').read_text();self.assertIn('--version-id',b);self.assertIn('BUNDLE_HASH_MISMATCH',b);self.assertNotIn('pip install',b);self.assertNotIn('curl ',b);self.assertNotIn('set -x',b)
    def test_deactivating_or_uncertain_service_is_not_idle(self):
        class Result:
            returncode=0
            stdout=b'ActiveState=deactivating\nMainPID=123\nControlPID=0\nTasksCurrent=2\nControlGroup=/system.slice/own.service\n'
        with patch.object(h.subprocess,'run',return_value=Result()):self.assertTrue(h.service_busy())
        Result.stdout=b'ActiveState=inactive\nMainPID=0\nControlPID=0\nTasksCurrent=0\nControlGroup=\n'
        with patch.object(h.subprocess,'run',return_value=Result()):self.assertFalse(h.service_busy())
        Result.returncode=1
        with patch.object(h.subprocess,'run',return_value=Result()):self.assertTrue(h.service_busy())
    def test_retirement_evidence_exports_hashes_without_raw_payload(self):
        state=self.root/'state';path=state/'missing/delivery';path.mkdir(parents=True)
        (path/'pending.json').write_text(json.dumps({'Payload':'SYNTHETIC_RAW_NOT_TO_LOG','Attempts':2}))
        with patch.object(h,'STATE',state):value=h.evidence()
        self.assertEqual(value['files'][0]['attempts'],2);self.assertTrue(value['files'][0]['pending']);self.assertFalse(value['drained']);self.assertNotIn('SYNTHETIC_RAW_NOT_TO_LOG',json.dumps(value))
    def test_host_resource_count_no_sql_nat_or_ingress(self):
        x=json.loads((TF/'modules/observer/main.tf.json').read_text());r=x['resource'];self.assertEqual(sum(map(len,r.values())),14)
        text=json.dumps(r);self.assertNotIn('aws_nat_gateway',text);self.assertNotIn('aws_eip',text);self.assertNotIn('aws_db_instance',text)
        self.assertEqual(r['aws_security_group']['observer']['ingress'],[]);self.assertEqual(r['aws_instance']['observer']['credit_specification']['cpu_credits'],'standard');self.assertEqual(r['aws_instance']['observer']['metadata_options']['http_tokens'],'required')
        self.assertTrue(r['aws_instance']['observer']['root_block_device']['delete_on_termination']);self.assertNotIn('key_name',r['aws_instance']['observer'])
    def test_host_policy_boundary_matches_no_unrelated_mutations(self):
        x=json.loads((TF/'modules/observer/main.tf.json').read_text());r=x['resource'];self.assertEqual(r['aws_iam_policy']['observer_boundary']['policy'],r['aws_iam_role_policy']['observer']['policy'])
        p=json.loads(x['locals']['policy'][len('${jsonencode('):-2]);acts={a for s in p['Statement'] for a in s['Action']}
        self.assertFalse(any(a.startswith(('ec2:','iam:','sns:','dynamodb:','secretsmanager:')) for a in acts));self.assertNotIn('s3:PutObject',acts);self.assertEqual({a for a in acts if a.startswith('kms:')},{'kms:Decrypt'})
        self.assertTrue(all('DateLessThan' in s['Condition'] for s in p['Statement']));self.assertIn('ssmmessages:OpenDataChannel',acts)
    def test_default_off_and_same_sender_role_contract(self):
        r=json.loads((TF/'main.tf.json').read_text());self.assertFalse(r['variable']['enable_observer']['default']);self.assertIsNone(r['variable']['observer']['default']);self.assertIn('module.pipeline',r['module']['observer']['depends_on'])
        m=json.loads((TF/'modules/observer/main.tf.json').read_text());checks=json.dumps(m['resource']['aws_instance']['observer']['lifecycle']);self.assertIn('sender_role_arn==local.role_arn',checks)
    def test_control_document_cannot_accept_arbitrary_shell(self):
        x=json.loads((TF/'modules/observer/main.tf.json').read_text());s=x['resource']['aws_ssm_document']['observer_control']['content'];self.assertIn('allowedValues',s);self.assertIn('allowedPattern',s);self.assertNotIn('commands=',s);self.assertIn('observer_host.py control --action',s)

if __name__=='__main__':unittest.main()
