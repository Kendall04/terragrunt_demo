"""Protected-port/state-machine fixtures only; no native approval or cloud proof."""
import copy
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))
from scripts.normal_delivery import authorization as a, delivery as d, recovery as r
from scripts.normal_delivery.e3 import Gate
from scripts.tests.normal_delivery.test_authorization import Fixture, ACCOUNT, REGION, URI, response, make_binding
from scripts.tests.delivery.fixtures import Records, Runtime, ProcessFixture, OP, NEXT


def audit(event,args):
    if event.startswith('socket.') or event in ('subprocess.Popen','os.system','os.posix_spawn'):
        raise AssertionError('RECOVERY_V2_EXTERNAL_EFFECT_FORBIDDEN')


sys.addaudithook(audit)


def approve(facts, operation=OP):
    base=copy.deepcopy(facts.bindings['deploy-dev']);base['max_replicas']=2
    if base['schema']==r.V2_BINDING:
        base.pop('recovery');base['schema']='E1_DELIVERY_BINDING_V1'
    evidence=dict(schema='E1_SQL_RECOVERY_EVIDENCE_V2',writer='RECOVERY_VERIFIER',
        account=ACCOUNT,region=REGION,recovery_id='r20261024c1t',
        source_instance_id='i-'+'1'*17,source_launch_epoch=700,source_state='terminated',source_terminated_at=825,
        target_instance_id='i-'+'2'*17,target_launch_epoch=850,target_state='running',recovery_requested_at=800,
        restore_started_at=875,restore_completed_at=900,observed_at=940,checkdb='RESTORED_CHECKDB_READABLE',
        endpoint='10.77.1.8',vpc_id='vpc-'+'a'*17,db_subnet_id='subnet-'+'b'*17,
        db_security_group_id='sg-'+'c'*17,task_security_groups=sorted(base['service']['networkConfiguration']['awsvpcConfiguration']['securityGroups']),
        source_fence_sha256='1'*64,network_sha256='2'*64,runtime_precheck_sha256='3'*64,
        connection_receipt_sha256='4'*64,restored_schema_sha256='f'*64,
        secret_arn=base['secret_arn'],secret_version_id='d'*32,secret_key_arn=base['kms_key_arn'])
    approval=dict(profile=r.PROFILE_NAME,model_sha256=r.PROFILE_SHA256,approval_id='aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa',
        writer='SECURITY_ADMIN',status='APPROVED',operation_id=operation,approved_at=950,expires_at=4000,
        base_binding_sha256=a.sha(a.canonical(base)),secret_version_id='d'*32,evidence=evidence,
        evidence_sha256=a.sha(a.canonical(evidence)),allowed_releases=[dict(release_id=facts.q['release_id'],
            image_uri=URI,qualification_sha256=a.sha(a.canonical(facts.q)),schema_sha256='f'*64)])
    base.update(schema=r.V2_BINDING,recovery=approval)
    facts.bindings['deploy-dev']=base
    return facts


class CurrentFacts(Fixture):
    def environment(self,endpoint):
        raw=a.canonical(self.bindings[endpoint])
        return dict(endpoint=endpoint,version_id='binding-'+a.sha(raw),bytes=raw)



def second_release():
    facts=Fixture();image_digest='sha256:'+'c'*64
    manifest=a.decode(facts.manifest_bytes)
    manifest['image'].update(digest=image_digest,uri=URI.replace('b'*64,'c'*64))
    facts.manifest_bytes=a.canonical(manifest)
    facts.ref.update(key='releases/demo-api/by-digest/'+image_digest.replace(':','-')+'.json',
                     sha256=a.sha(facts.manifest_bytes))
    facts.q['image_digest']=image_digest
    facts.q['release_id']='sha256-'+a.sha(a.canonical({k:v for k,v in facts.q.items() if k!='release_id'}))
    facts.q_raw=a.canonical(facts.q);facts.e['release_id']=facts.q['release_id']
    facts.available['digest']=image_digest
    return facts


class TwoReleaseFacts(CurrentFacts):
    def __init__(self):
        super().__init__();self.other=second_release()
    def qualification(self,release_id):
        return self.other.qualification(release_id) if release_id==self.other.q['release_id'] else super().qualification(release_id)
    def manifest(self,bucket,key,version_id):
        return self.other.manifest(bucket,key,version_id) if key==self.other.ref['key'] else super().manifest(bucket,key,version_id)
    def eligibility_current(self,release_id):
        return self.other.eligibility_current(release_id) if release_id==self.other.q['release_id'] else super().eligibility_current(release_id)
    def artifact(self,repository,digest):
        return self.other.artifact(repository,digest) if digest==self.other.q['image_digest'] else super().artifact(repository,digest)


def approve_both(facts,operation):
    approve(facts,operation)
    facts.bindings['deploy-dev']['recovery']['allowed_releases'].append(dict(
        release_id=facts.other.q['release_id'],image_uri=URI.replace('b'*64,'c'*64),
        qualification_sha256=a.sha(a.canonical(facts.other.q)),schema_sha256='f'*64))


def setup(operation=OP, records=None):
    facts=approve(CurrentFacts(),operation)
    clock=[1000]
    auth=r.RecoveryAuthorizer('deploy-dev',ACCOUNT,REGION,facts,operation_id=operation,clock=lambda:clock[0])
    raw=a.canonical(dict(action='deliver',release_id=facts.q['release_id'],replicas=2))
    intent=auth.authorize(a.canonical(dict(release_id=facts.q['release_id'],replicas=2)))
    records=records or Records();world=Runtime(intent,records,facts.members['dev']['colors'])
    auth.clock=world.now
    process=ProcessFixture(world);core=r.RecoveryDelivery(auth,world,records,Gate(process))
    return facts,auth,records,world,process,core,raw


class RecoveryV2Tests(unittest.TestCase):
    def test_opt_in_v2_authorizes_exact_secret_model_qualified_image_and_no_migrations(self):
        f,auth,_,_,_,_,_=setup()
        intent=auth.authorize(a.canonical(dict(release_id=f.q['release_id'],replicas=2)))
        self.assertEqual(intent['schema'],r.V2_INTENT)
        app,probe=intent['task']['containerDefinitions']
        self.assertEqual(app['environment'][-1],{'name':'Database__RunMigrationsOnStartup','value':'false'})
        self.assertEqual(app['secrets'][0]['valueFrom'],f.bindings['deploy-dev']['secret_arn']+':::'+'d'*32)
        self.assertNotIn('environment',probe);self.assertNotIn('secrets',probe)
        self.assertEqual(app['image'],URI);self.assertEqual(probe['image'],URI)
        self.assertEqual(intent['recovery']['operation_id'],OP)
        auth.validate_readback(intent,a.canonical(response(intent)))

    def test_v1_types_bindings_and_journals_do_not_implicitly_upgrade(self):
        facts=Fixture();normal=a.Authorizer('deploy-dev',ACCOUNT,REGION,facts)
        raw=a.canonical(dict(release_id=facts.q['release_id'],replicas=1))
        self.assertEqual(normal.authorize(raw)['schema'],'E1_AUTHORIZED_RUNTIME_INTENT_V1')
        facts=approve(CurrentFacts())
        with self.assertRaises(a.Rejected):a.Authorizer('deploy-dev',ACCOUNT,REGION,facts).authorize(raw)
        auth=r.RecoveryAuthorizer('deploy-dev',ACCOUNT,REGION,Fixture(),operation_id=OP,clock=lambda:1000)
        with self.assertRaises(a.Rejected):auth.authorize(raw)
        _,auth,records,world,process,core,raw=setup()
        with self.assertRaises(a.Rejected):d.Delivery(auth,world,records,Gate(process))
        op=core.accept(OP,raw)
        self.assertEqual(op['schema'],r.V2_OPERATION)
        normal=d.Delivery(a.Authorizer('deploy-dev',ACCOUNT,REGION,Fixture()),world,records,Gate(process))
        with self.assertRaises(d.JournalError):normal.retained_operation(OP)

    def test_no_caller_profile_secret_evidence_or_authority_override(self):
        f,auth,_,_,_,_,_=setup()
        for key in ('recovery','profile','secret_version_id','approved','task','image','roles','endpoint','account','region'):
            raw=a.canonical(dict(release_id=f.q['release_id'],replicas=1,**{key:True}))
            with self.assertRaises(a.Rejected):auth.authorize(raw)

    def test_wrong_version_profile_roles_account_region_and_model_refuse(self):
        for change in (
            lambda b:b['recovery'].update(secret_version_id='e'*32),
            lambda b:b['recovery'].update(profile='NORMAL_WITH_MIGRATIONS'),
            lambda b:b['recovery'].update(model_sha256='0'*64),
            lambda b:b['roles'].update(task=b['roles']['execution']),
            lambda b:b.update(account='000000000000'),
            lambda b:b.update(region='us-west-2'),
            lambda b:b.update(secret_arn=b['secret_arn']+':::'+'d'*32),
            lambda b:b['recovery'].update(command=['unexpected'])):
            f,auth,*_=setup();change(f.bindings['deploy-dev'])
            with self.assertRaises(a.Rejected):auth.authorize(a.canonical(dict(release_id=f.q['release_id'],replicas=1)))

    def test_wrong_image_qualification_or_restored_schema_refuse(self):
        for change in (
            lambda b:b['recovery']['allowed_releases'][0].update(image_uri=URI.replace('b'*64,'c'*64)),
            lambda b:b['recovery']['allowed_releases'][0].update(qualification_sha256='0'*64),
            lambda b:b['recovery']['allowed_releases'][0].update(schema_sha256='e'*64),
            lambda b:b['recovery']['allowed_releases'].append(copy.deepcopy(b['recovery']['allowed_releases'][0]))):
            f,auth,*_=setup();change(f.bindings['deploy-dev'])
            with self.assertRaises(a.Rejected):auth.authorize(a.canonical(dict(release_id=f.q['release_id'],replicas=1)))

    def test_evidence_hash_fencing_private_network_and_secret_correlations_refuse(self):
        for change in (
            lambda e:e.update(source_state='stopped'),
            lambda e:e.update(target_instance_id=e['source_instance_id']),
            lambda e:e.update(target_launch_epoch=750),
            lambda e:e.update(source_terminated_at=890),
            lambda e:e.update(endpoint='0.0.0.0'),
            lambda e:e.update(endpoint='169.254.169.254'),
            lambda e:e.update(account='000000000000'),
            lambda e:e.update(region='us-west-2'),
            lambda e:e.update(secret_version_id='e'*32),
            lambda e:e.update(secret_key_arn='arn:foreign'),
            lambda e:e.update(task_security_groups=['sg-foreign'])):
            f,auth,*_=setup();b=f.bindings['deploy-dev'];change(b['recovery']['evidence'])
            # Retain a valid checksum so semantic checks, not checksum failures,
            # must reject these approved-record mutations.
            b['recovery']['evidence_sha256']=a.sha(a.canonical(b['recovery']['evidence']))
            with self.assertRaises(a.Rejected):auth.authorize(a.canonical(dict(release_id=f.q['release_id'],replicas=1)))
        f,auth,*_=setup();f.bindings['deploy-dev']['recovery']['evidence_sha256']='0'*64
        with self.assertRaises(a.Rejected):auth.authorize(a.canonical(dict(release_id=f.q['release_id'],replicas=1)))

    def test_expiry_wrong_operation_unapproved_and_stale_at_approval_refuse(self):
        for change in (
            lambda b:b['recovery'].update(status='REVOKED'),
            lambda b:b['recovery'].update(operation_id=NEXT),
            lambda b:b['recovery'].update(expires_at=1000),
            lambda b:b['recovery'].update(expires_at=100000),
            lambda b:b['recovery'].update(approved_at=1001),
            lambda b:b['recovery'].update(approved_at=1841)):
            f,auth,*_=setup();change(f.bindings['deploy-dev'])
            with self.assertRaises(a.Rejected):auth.authorize(a.canonical(dict(release_id=f.q['release_id'],replicas=1)))
        f,auth,_,world,*_=setup();f.bindings['deploy-dev']['recovery']['approved_at']=2000;world.time=2500
        with self.assertRaises(a.Rejected):auth.authorize(a.canonical(dict(release_id=f.q['release_id'],replicas=1)))
        f,auth,*_=setup()
        with self.assertRaises(a.Rejected):r.RecoveryAuthorizer('promote-prod',ACCOUNT,REGION,f,operation_id=OP,clock=lambda:1000)

    def test_distinct_image_rollback_from_v1_history_uses_same_recovered_database(self):
        from scripts.tests.delivery.fixtures import setup as normal_setup
        *_,normal,normal_raw=normal_setup()
        first=normal.run(OP,normal_raw);self.assertEqual(first['status'],'SUCCESS')
        records=normal.records
        facts=TwoReleaseFacts();facts.bindings['deploy-dev']=make_binding('dev','green')
        approve_both(facts,NEXT)
        auth=r.RecoveryAuthorizer('deploy-dev',ACCOUNT,REGION,facts,operation_id=NEXT,clock=lambda:1000)
        release_b=facts.other.q['release_id']
        intent=auth.authorize(a.canonical(dict(release_id=release_b,replicas=2)))
        world=Runtime(intent,records,facts.members['dev']['colors']);auth.clock=world.now
        core=r.RecoveryDelivery(auth,world,records,Gate(ProcessFixture(world)))
        recovered=core.run(NEXT,a.canonical(dict(action='deliver',release_id=release_b,replicas=2)))
        self.assertEqual(recovered['status'],'SUCCESS')
        self.assertEqual(recovered['intent']['task']['containerDefinitions'][0]['image'],URI.replace('b'*64,'c'*64))
        rollback_op='77777777-2222-3333-4444-555555555555'
        facts.bindings['deploy-dev']=make_binding('dev','blue');approve_both(facts,rollback_op)
        auth=r.RecoveryAuthorizer('deploy-dev',ACCOUNT,REGION,facts,operation_id=rollback_op,clock=lambda:1000)
        intent=auth.authorize(a.canonical(dict(release_id=facts.q['release_id'],replicas=2)))
        world=Runtime(intent,records,facts.members['dev']['colors']);auth.clock=world.now
        core=r.RecoveryDelivery(auth,world,records,Gate(ProcessFixture(world)))
        result=core.run(rollback_op,a.canonical(dict(action='rollback-release',history=OP,replicas=2)))
        self.assertEqual(result['status'],'SUCCESS')
        self.assertEqual(result['intent']['task']['containerDefinitions'][0]['image'],URI)
        self.assertEqual(result['intent']['task']['containerDefinitions'][0]['secrets'],recovered['intent']['task']['containerDefinitions'][0]['secrets'])
        self.assertNotEqual(first['intent']['task']['containerDefinitions'][0]['secrets'],result['intent']['task']['containerDefinitions'][0]['secrets'])

    def test_registered_task_wrong_version_profile_roles_commands_or_digest_refuse(self):
        f,auth,*_=setup();intent=auth.authorize(a.canonical(dict(release_id=f.q['release_id'],replicas=1)))
        for change in (
            lambda x:x['taskDefinition']['containerDefinitions'][0]['secrets'][0].update(valueFrom=f.bindings['deploy-dev']['secret_arn']+':::'+'e'*32),
            lambda x:x['taskDefinition']['containerDefinitions'][0]['environment'][-1].update(value='true'),
            lambda x:x['taskDefinition'].update(taskRoleArn=x['taskDefinition']['executionRoleArn']),
            lambda x:x['taskDefinition']['containerDefinitions'][0].update(command=['unreviewed']),
            lambda x:x['taskDefinition']['containerDefinitions'][1].update(image=URI.replace('b'*64,'c'*64))):
            observed=response(intent);change(observed)
            with self.assertRaises(a.Rejected):auth.validate_readback(intent,a.canonical(observed))

    def test_same_state_machine_completes_and_replays_without_new_effects(self):
        _,_,records,world,_,core,raw=setup()
        result=core.run(OP,raw)
        self.assertEqual(result['status'],'SUCCESS')
        self.assertEqual([stage for stage,_ in world.calls],['register','drain','attach','start','e3','switch','candidate','cleanup'])
        count=len(world.calls);self.assertEqual(core.run(OP,raw),result);self.assertEqual(len(world.calls),count)
        self.assertEqual(a.decode(records.data['dev/'+OP+'/intent'])['schema'],r.V2_OPERATION)

    def test_corrupt_retained_v2_summary_refuses_even_with_recomputed_intent_hash(self):
        for change in (lambda i:i.update(recovery='not-a-record'),
                       lambda i:i['recovery'].pop('evidence_sha256'),
                       lambda i:i['recovery'].update(operation_id=NEXT),
                       lambda i:i['recovery'].update(approval_sha256='not-a-digest')):
            _,_,records,world,_,core,raw=setup();op=core.accept(OP,raw)
            change(op['intent'])
            op['intent']['intent_sha256']=a.sha(a.canonical({k:v for k,v in op['intent'].items() if k!='intent_sha256'}))
            records.data['dev/'+OP+'/intent']=a.canonical(op)
            with self.assertRaises(d.JournalError):core.retained_operation(OP)
            self.assertNotEqual(core.run(OP,raw)['status'],'SUCCESS')
            self.assertEqual(world.calls,[])

    def test_revoke_or_change_approved_version_before_switch_stops_existing_operation(self):
        for change in ('revoke','version'):
            facts,_,_,world,process,core,raw=setup()
            def mutate():
                p=facts.bindings['deploy-dev']['recovery']
                if change=='revoke':p['status']='REVOKED'
                else:
                    p['secret_version_id']='e'*32;p['evidence']['secret_version_id']='e'*32
                    p['evidence_sha256']=a.sha(a.canonical(p['evidence']))
            process.after=mutate
            self.assertNotEqual(core.run(OP,raw)['status'],'SUCCESS')
            self.assertNotIn('switch',[stage for stage,_ in world.calls])

    def test_rollback_reauthorizes_same_restored_database_and_rejects_other_operation(self):
        facts,_,records,_,_,core,raw=setup()
        first=core.run(OP,raw);self.assertEqual(first['status'],'SUCCESS')
        approve(facts,NEXT)
        auth=r.RecoveryAuthorizer('deploy-dev',ACCOUNT,REGION,facts,operation_id=NEXT,clock=lambda:1000)
        intent=auth.authorize(a.canonical(dict(release_id=facts.q['release_id'],replicas=2)))
        world=Runtime(intent,records,facts.members['dev']['colors']);auth.clock=world.now
        rollback=r.RecoveryDelivery(auth,world,records,Gate(ProcessFixture(world)))
        request=a.canonical(dict(action='rollback-release',history=OP,replicas=2))
        result=rollback.run(NEXT,request)
        self.assertEqual(result['status'],'SUCCESS')
        self.assertEqual(result['intent']['task']['containerDefinitions'][0]['secrets'],first['intent']['task']['containerDefinitions'][0]['secrets'])
        self.assertEqual(result['history']['operation_id'],OP)
        with self.assertRaises(a.Rejected):rollback.accept(OP,request)


if __name__=='__main__':unittest.main()
