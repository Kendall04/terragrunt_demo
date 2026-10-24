"""Offline diagnostic packet/collector tests. No AWS or native SSM acceptance."""
import ast,copy,datetime as dt,gzip,hashlib,importlib.util,json,os,subprocess,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import collector,harness,prepare
HERE=Path(__file__).resolve().parent

def audit(event,args):
    if event.startswith('socket.') or event in ('subprocess.Popen','os.system','os.posix_spawn'):raise AssertionError('EXTERNAL_EFFECT_FORBIDDEN')
sys.addaudithook(audit)
def cfg():return {'run':prepare.RUN,'account':prepare.A,'region':prepare.REG,'expires_at':'2026-10-25T12:00:00Z','log_group':prepare.GROUP,'role':prepare.RUN+'-node','source_sha256':hashlib.sha256((HERE/'collector.py').read_bytes().replace(b'\r\n',b'\n')).hexdigest()}
class Port:
    def __init__(self):self.calls=[];self.records=[]
    def identity(self):return {'Account':prepare.A,'Arn':f'arn:aws:sts::{prepare.A}:assumed-role/{prepare.RUN}-node/i-'+'a'*17}
    def command(self,args):
        self.calls.append(args)
        if 'show' in args:return subprocess.CompletedProcess(args,0,b'ActiveState=active\nSubState=running\nResult=success\nBogus=PRIVATE\n',b'PRIVATE')
        if '-version' in args:return subprocess.CompletedProcess(args,0,b'SSM Agent version: 3.3.4000.0',b'')
        return subprocess.CompletedProcess(args,0,b'{}',b'')
    def logs(self,path):return b'GetDocument AccessDenied Authorization=SECRET SessionToken=SECRET commandId: 12345678-1234-1234-1234-123456789abc'
    def put(self,c,r):self.records.append(r)
class CollectorTests(unittest.TestCase):
    def test_allowlist_does_not_export_secrets_or_arbitrary_error_text(self):
        poison=b'AccessDenied GetDocument Authorization: Bearer SENTINEL_SECRET AWS_SECRET_ACCESS_KEY=SENTINEL_SECRET password=SENTINEL_SECRET requestId: 12345678-1234-1234-1234-123456789abc\nSessionToken=SENTINEL_SECRET\n'
        rows=collector.sanitize(poison);text=json.dumps(rows)
        self.assertNotIn('SENTINEL_SECRET',text);self.assertNotIn('Authorization',text);self.assertNotIn('password',text)
        self.assertEqual(rows[0]['codes'],['AccessDenied']);self.assertEqual(rows[0]['actions'],['GetDocument']);self.assertEqual(len(rows[0]['requestIds']),1)
        self.assertEqual(rows[0]['lineSha256'],hashlib.sha256(poison.splitlines()[0]).hexdigest())
        self.assertEqual(collector.sanitize(b'unknown private error'),[])
        with self.assertRaises(ValueError):collector.sanitize(b'x'*65537)
    def test_snapshot_is_fixed_metadata_not_stdout_or_env_dump(self):
        p=Port();r=collector.snapshot(p,cfg(),0);self.assertNotIn('PRIVATE',json.dumps(r));self.assertNotIn('SECRET',json.dumps(r))
        self.assertEqual(r['agentService'],{'ActiveState':'active','SubState':'running','Result':'success'});self.assertEqual(r['agentVersion'],'3.3.4000.0');self.assertFalse(r['rawLogsExported'])
        p.identity=lambda:{'Account':'0'*12,'Arn':'arn:foreign'}
        with self.assertRaises(ValueError):collector.snapshot(p,cfg(),1)
    def test_finite_collection_expiry_and_export_error_never_retry(self):
        c=cfg();p=Port();at=dt.datetime(2026,10,24,13,tzinfo=dt.timezone.utc)
        with patch.object(os,'geteuid',return_value=0):collector.execute(c,p,lambda _:None,lambda:at)
        self.assertEqual(len(p.records),120);self.assertEqual(sum('create-log-stream' in x for x in p.calls),1)
        p=Port();p.put=lambda *_:(_ for _ in ()).throw(ValueError('DENIED'))
        with patch.object(os,'geteuid',return_value=0),self.assertRaises(ValueError):collector.execute(c,p,lambda _:None,lambda:at)
        self.assertEqual(sum('create-log-stream' in x for x in p.calls),1)
        with patch.object(os,'geteuid',return_value=0),self.assertRaises(ValueError):collector.execute(c,Port(),lambda _:None,lambda:at+dt.timedelta(days=2))
    def test_default_invocation_has_no_native_port_and_bad_config_refused(self):
        with patch.object(sys,'argv',['collector.py']),patch.object(collector,'Native',side_effect=AssertionError('NATIVE')),patch('builtins.print') as out:collector.main()
        self.assertIn('DESIGN_ONLY',out.call_args.args[0])
        for key,value in [('account','0'*12),('log_group','/other'),('role','Admin'),('source_sha256','x'),('expires_at','2026-10-25T12:00:00')]:
            c=cfg();c[key]=value
            with self.assertRaises(ValueError):collector.validate(c)
    def test_only_fixed_regular_log_files_are_read(self):
        with self.assertRaises(ValueError):collector.tail('/proc/self/environ')
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'test.log';p.write_bytes(b'x'*70000)
            with patch.object(collector,'LOGS',(str(p),)):self.assertEqual(len(collector.tail(str(p))),65536)
            d=Path(t)/'dir';d.mkdir()
            with patch.object(collector,'LOGS',(str(d),)),self.assertRaises((ValueError,OSError)):collector.tail(str(d))
    def test_export_acceptance_checks_rejections_and_no_stderr_disclosure(self):
        with tempfile.TemporaryDirectory() as d,patch.object(collector,'BASE',Path(d)):
            n=collector.Native();seen=[]
            def command(args):
                seen.append(json.loads((Path(d)/'export.json').read_text()))
                return subprocess.CompletedProcess(args,0,b'{"rejectedLogEventsInfo":{"tooOldLogEventEndIndex":0}}',b'SECRET')
            n.command=command
            with self.assertRaisesRegex(ValueError,'EXPORT_REJECTED'):n.put(cfg(),collector.snapshot(Port(),cfg(),0))
            self.assertEqual(len(seen),1);self.assertFalse((Path(d)/'export.json').exists())
            with self.assertRaises(ValueError):n.put(cfg(),{'password':'SECRET'})
            self.assertEqual(len(seen),1)
class HarnessTests(unittest.TestCase):
    def test_actual_control_ast_is_preserved_and_no_other_action_exposed(self):
        original=ast.parse((HERE.parent/'observer_host.py').read_text());subset=ast.parse(prepare.observer_source())
        for name in ['control','host','system','service_busy','validate']:
            find=lambda t:next(n for n in t.body if getattr(n,'name',None)==name)
            self.assertEqual(ast.dump(find(original)),ast.dump(find(subset)))
        with patch.object(sys,'argv',['harness.py','--action','start']),self.assertRaises(SystemExit):harness.main()
    def test_native_status_functions_execute_with_fake_systemctl_only(self):
        with tempfile.TemporaryDirectory() as d:
            b=Path(d);source=prepare.observer_source();(b/'observer_host.py').write_bytes(source);(b/'harness-config.json').write_text(json.dumps({'observerSha256':hashlib.sha256(source).hexdigest()}))
            # Extract the exact non-secret host configuration embedded by preparer.
            tree=ast.parse(prepare.boot_script().split("<<'PY'\n",1)[1].rsplit('\nPY',1)[0]);node=next(n for n in tree.body if isinstance(n,ast.Assign) and isinstance(n.targets[0],ast.Name) and n.targets[0].id=='host');c=ast.literal_eval(node.value);c['expires_at']='2026-10-25T12:00:00Z';(b/'host.json').write_text(json.dumps(c));(b/'state').mkdir();(b/'state/mode.json').write_text('{"mode":"missing"}')
            calls=[]
            def system(args,**_):
                calls.append(args);self.assertIn(args[1],['is-active','show'])
                return subprocess.CompletedProcess(args,3 if args[1]=='is-active' else 0,b'ActiveState=inactive\nMainPID=0\nControlPID=0\nControlGroup=\nTasksCurrent=0\n',b'')
            with patch.object(subprocess,'run',side_effect=system):r=harness.status(b)
            self.assertEqual(r['status'],'OBSERVED');self.assertFalse(r['timerActive']);self.assertFalse(r['serviceActiveOrUncertain']);self.assertFalse(r['backupAcceptance']);self.assertEqual(len(calls),2)
            (b/'observer_host.py').write_bytes(source+b'# changed')
            with self.assertRaisesRegex(ValueError,'SOURCE_CHANGED'):harness.status(b)
class PacketTests(unittest.TestCase):
    def originals(self):return {k:json.loads((HERE/'baseline'/f'{k}.json').read_text()) for k in ['part4','part7','backend']}
    def test_exact_fourteen_and_no_application_or_session_resources(self):
        xs=[prepare.bootstrap(),prepare.runtime()];self.assertEqual(sum(len(v) for x in xs for v in x['resource'].values()),14)
        alltypes={k for x in xs for k in x['resource']};self.assertFalse(any(x in str(alltypes).lower() for x in ['nat','lambda','sns','kms','secretsmanager','cloudformation']))
        node=xs[1]['resource']['aws_instance']['node'];self.assertEqual(node['credit_specification']['cpu_credits'],'standard');self.assertEqual(node['root_block_device']['volume_size'],8);self.assertTrue(node['root_block_device']['delete_on_termination']);self.assertTrue(node['root_block_device']['encrypted'])
        self.assertEqual(xs[1]['resource']['aws_security_group']['diag']['ingress'],[]);self.assertEqual(prepare.document()['parameters']['Action']['allowedValues'],['status'])
        self.assertLess(len(gzip.compress(prepare.boot_script().encode())),16384)
        import base64
        tree=ast.parse(prepare.boot_script().split("<<'PY'\n",1)[1].rsplit('\nPY',1)[0])
        node=next(n for n in tree.body if isinstance(n,ast.Assign) and isinstance(n.targets[0],ast.Name) and n.targets[0].id=='files')
        blobs=ast.literal_eval(node.value)
        self.assertTrue(all(b'\r\n' not in base64.b64decode(v) for v in blobs.values()))
        self.assertEqual(hashlib.sha256(base64.b64decode(blobs['collector.py'])).hexdigest(),cfg()['source_sha256'])
    def test_scope_no_iam_writes_no_sessions_no_changed_forwarded_leg(self):
        p=prepare.operator_policy('i-'+'a'*17);allactions={a for s in p['Statement'] for a in s['Action']}
        self.assertFalse(any(a.startswith('iam:') and a not in ['iam:GetRole','iam:ListInstanceProfilesForRole','iam:GetInstanceProfile','iam:PassRole'] for a in allactions));self.assertNotIn('ssm:StartSession',allactions);self.assertNotIn('ec2:DeleteVolume',allactions)
        send=[s for s in p['Statement'] if s['Action']==['ssm:SendCommand']];self.assertEqual(len(send),4)
        for s in send:
            self.assertNotIn('*',s['Resource']);self.assertNotIn('IfExists',json.dumps(s))
            if s['Condition']['Bool']['aws:ViaAWSService']=='true':self.assertNotIn('StringEquals',s['Condition'])
        n=prepare.node_policy();self.assertEqual(n,prepare.node_policy());self.assertFalse(any(a.split(':')[0] in ['s3','kms','secretsmanager','ec2','iam'] for s in n['Statement'] for a in s['Action']))
        self.assertTrue(all('DateLessThan' in s['Condition'] for s in p['Statement']))
    def test_backend_exact_delta_and_original_unchanged(self):
        base=self.originals();before=copy.deepcopy(base);proposal=prepare.amend_backend(base['backend']);self.assertEqual(base,before)
        self.assertEqual(len(proposal['Statement']),len(base['backend']['Statement'])+3)
        for old,new in zip(base['backend']['Statement'],proposal['Statement']):
            if old.get('Sid') in ['E16NoOtherDevObjects','E16RetainStateObjects']:
                k='NotResource' if 'NotResource' in old else 'Resource';delta=[v for v in new[k] if v not in old[k]];self.assertTrue(all(prepare.KEY in v for v in delta))
            else:self.assertEqual(old,new)
        for s in proposal['Statement'][-3:]:self.assertEqual(s['Principal']['AWS'],prepare.OP)
        with self.assertRaises(ValueError):prepare.amend_backend({'Statement':[]})
    def test_binding_foreign_generation_and_window_refused(self):
        v={'Account':prepare.A,'Region':prepare.REG,'InstanceId':'i-'+'a'*17,'ImageId':prepare.AMI,'State':'running','Trial':prepare.RUN,'ProfileArn':prepare.PROFILE,'LaunchTime':'2026-10-24T12:00:00Z','ObservedUtc':'2026-10-24T12:10:00Z'}
        r=prepare.bind_instance(v,'2026-10-25T12:00:00Z');self.assertFalse(r['EvidenceAuthenticated']);self.assertLess(len(prepare.canonical(r['Policy'])),10240)
        for k,val in [('Account','0'*12),('InstanceId','*'),('ImageId','ami-foreign'),('Trial','foreign'),('ProfileArn','arn:admin'),('State','terminated'),('LaunchTime','2026-10-23T12:00:00Z')]:
            x=v|{k:val}
            with self.assertRaises(ValueError):prepare.bind_instance(x,'2026-10-25T12:00:00Z')
    def test_create_and_retire_plan_reject_other_resources_updates_or_generations(self):
        x=prepare.runtime();addresses=[t+'.'+n for t,rs in x['resource'].items() for n in rs]
        plan={'resource_changes':[{'address':a,'change':{'actions':['create']}} for a in addresses]}
        self.assertEqual(prepare.review_saved_plan(plan,'runtime','create')['Count'],10)
        with self.assertRaises(ValueError):prepare.review_saved_plan({'resource_changes':plan['resource_changes'][:-1]},'runtime','create')
        bad=copy.deepcopy(plan);bad['resource_changes'][0]['address']='aws_instance.other'
        with self.assertRaises(ValueError):prepare.review_saved_plan(bad,'runtime','create')
        bad=copy.deepcopy(plan);bad['resource_changes'][0]['change']['actions']=['delete','create']
        with self.assertRaises(ValueError):prepare.review_saved_plan(bad,'runtime','create')
        retiring={'resource_changes':[{'address':'aws_instance.node','change':{'actions':['delete'],'before':{'id':'i-'+'a'*17}}}]}
        registry={'aws_instance.node':'i-'+'a'*17};self.assertFalse(prepare.review_saved_plan(retiring,'runtime','delete',registry)['AllowsExecution'])
        with self.assertRaises(ValueError):prepare.review_saved_plan(retiring,'runtime','delete',{'aws_instance.node':'i-'+'b'*17})

    def test_reproducible_packet_hashes_and_cost_no_old_budget_reset(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'packet';m=prepare.build(p,self.originals());self.assertEqual(json.loads((p/'inventory.json').read_text())['Count'],14)
            for name,digest in m['FilesSha256Lf'].items():self.assertEqual(prepare.sha((p/name).read_bytes().replace(b'\r\n',b'\n')),digest)
            for name in ['evidence_export.py','collector.py']:
                self.assertEqual((p/'operator'/name).read_bytes().replace(b'\r\n',b'\n'),(HERE/name).read_bytes().replace(b'\r\n',b'\n'))
                self.assertIn('operator/'+name,m['FilesSha256Lf'])
            c=json.loads((p/'cost.json').read_text());self.assertLess(c['TotalConservativeUsd'],1);self.assertEqual(c['Status'],'PROPOSED_NEW_BUDGET_NOT_APPROVED');self.assertEqual(c['PaidHoursIncludingCleanupReserve'],5.5)
            with self.assertRaises(ValueError):prepare.build(p,self.originals())
if __name__=='__main__':unittest.main()
