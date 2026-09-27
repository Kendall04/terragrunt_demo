"""Protected storage, clock, process and runtime doubles; never live SDKs."""
import copy
from scripts.normal_delivery import authorization as a
from scripts.normal_delivery import delivery as d
from scripts.normal_delivery.e3 import Gate, Process
from scripts.tests.normal_delivery.test_authorization import Fixture, ACCOUNT, REGION, response

OP = '11111111-2222-3333-4444-555555555555'
NEXT = '66666666-2222-3333-4444-555555555555'


class Records(d.Records):
    def __init__(self):
        self.data = {}; self.fail = None; self.ack_lost = False
    def read(self, key):
        if key not in self.data: return None
        return dict(version_id='version-' + a.sha(self.data[key]), bytes=self.data[key])
    def create(self, key, raw):
        if self.fail and self.fail in key: raise OSError('storage unavailable')
        if key in self.data: raise FileExistsError()
        self.data[key] = raw
        if self.ack_lost: raise TimeoutError()


class Runtime(d.Runtime):
    def __init__(self, intent, records, members):
        self.intent=copy.deepcopy(intent);self.records=records;self.members=members
        self.time=1000;self.calls=[];self.effects={};self.hidden=set();self.ambiguous=set()
        self.fail=set();self.readback=None;self.on_snapshot=None;self.on_mutation=None
        self.snapshot_calls=0
        self.task = response(intent)['taskDefinition'];self.revision=self.task['taskDefinitionArn']
        other = 'green' if intent['color']=='blue' else 'blue'
        self.state=dict(environment=intent['environment'],color=intent['color'],
            cluster=intent['service']['cluster'],service=intent['service']['service'],
            listener=intent['routing']['listener_arn'],rule=intent['routing']['candidate_rule_arn'],
            normal_target=members[other]['target_group'],candidate_target=members[intent['color']]['target_group'],
            task_definition=self.revision.rsplit(':',1)[0]+':1',desired=0,running=0,pending=0,
            cohort=[],deployment='ecs-svc/old',service_snapshot={},observed_at=self.time)
    def now(self):return self.time
    def snapshot(self, intent, deadline):
        self.snapshot_calls+=1
        if self.on_snapshot:self.on_snapshot(self)
        result=copy.deepcopy(self.state);service=copy.deepcopy(intent['service'])
        service.update(desiredCount=result['desired'],taskDefinition=result['task_definition'])
        result.update(service_snapshot=service,observed_at=self.time)
        return result
    def effect(self, token, deadline):
        stage=token.split('/')[-1]
        if stage in self.hidden:return dict(token=token,request_sha256=None,state='UNKNOWN',result=None)
        return copy.deepcopy(self.effects.get(token,dict(token=token,request_sha256=None,state='ABSENT',result=None)))
    def read_task(self, revision, deadline):
        return a.canonical(self.readback if self.readback is not None else self.task)
    def apply(self, stage, token, request):
        self.calls.append((stage,copy.deepcopy(request)))
        if self.on_mutation:self.on_mutation(self,stage)
        if stage in self.fail:raise TimeoutError('no proven effect')
        result=copy.deepcopy(request)
        if stage=='register':result=dict(task_definition_arn=self.revision)
        elif stage in ('drain','attach','start'):
            self.state.update(desired=request['desiredCount'],running=request['desiredCount'],pending=0)
            if 'taskDefinition' in request:self.state['task_definition']=request['taskDefinition']
            self.state['cohort']=['arn:aws:ecs:'+REGION+':'+ACCOUNT+':task/cluster/task'+str(n)
                                 for n in range(request['desiredCount'])]
            if stage=='start':self.state['deployment']='ecs-svc/new'
        elif stage=='switch':self.state['normal_target']=request['target']
        elif stage=='candidate':self.state['candidate_target']=request['target']
        self.effects[token]=dict(token=token,request_sha256=a.sha(a.canonical(request)),state='APPLIED',result=result)
        if stage in self.ambiguous:raise TimeoutError('ack lost after applied effect')
    def register(self,token,request,deadline):self.apply('register',token,request)
    def drain(self,token,request,deadline):self.apply('drain',token,request)
    def attach(self,token,request,deadline):self.apply('attach',token,request)
    def start(self,token,request,deadline):self.apply('start',token,request)
    def switch(self,token,request,deadline):self.apply('switch',token,request)
    def candidate(self,token,request,deadline):self.apply('candidate',token,request)
    def cleanup(self,token,request,deadline):self.apply('cleanup',token,request)


class ProcessFixture(Process):
    def __init__(self,runtime):
        self.runtime=runtime;self.calls=[];self.exit=0;self.mutate=None;self.after=None
    def execute(self,argv,timeout):
        self.calls.append((argv,timeout));self.runtime.calls.append(('e3',{}))
        assert argv[:2]==['python3',str(a.ROOT/'scripts/bounded-process.py')]
        assert argv[3:5]==['bash',str(a.ROOT/'scripts/normal_delivery/e3-evidence.sh')]
        context=argv[5]
        evidence=dict(schema='E1_E3_OBSERVATION_V1',context_sha256=context,
                      cohort=copy.deepcopy(self.runtime.state['cohort']),fingerprint='f'*64)
        if self.mutate:self.mutate(evidence)
        if self.after:self.after()
        return dict(exit_code=self.exit,stdout=b'E3 diagnostic output\n'+a.canonical(evidence))


def setup(endpoint='deploy-dev',records=None):
    facts=Fixture();auth=a.Authorizer(endpoint,ACCOUNT,REGION,facts)
    raw=a.canonical(dict(action='deliver',release_id=facts.q['release_id'],replicas=2))
    intent=auth.authorize(a.canonical(dict(release_id=facts.q['release_id'],replicas=2)))
    records=records or Records();runtime=Runtime(intent,records,facts.members[a.ENDPOINTS[endpoint]]['colors'])
    process=ProcessFixture(runtime);core=d.Delivery(auth,runtime,records,Gate(process))
    return facts,auth,records,runtime,process,core,raw
