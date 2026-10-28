"""Real transition/journal code with explicit host/cloud doubles; no native actions."""
import copy
import hashlib
import io
import json
import os
import stat
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock,patch
from contextlib import redirect_stdout
import host
import prepare
from test_private_listener import service_input,private_kernel
from test_recovery import FakePort
from test_kernel_query_binding import CapturedPidPort
from test_runtime_precheck import query

class PrivateFixturePath(type(Path())):
    """POSIX permission metadata double only; no claim of Windows/POSIX ACL proof."""
    def stat(self, *, follow_symlinks=True):
        value = super().stat(follow_symlinks=follow_symlinks)
        if stat.S_ISDIR(value.st_mode):
            fields = list(value);fields[0] = stat.S_IFDIR | 0o700
            return os.stat_result(fields)
        return value


class ListenerTransitionTests(unittest.TestCase):
    def setUp(self):
        self.value=service_input();self.identity=self.value['ColdReceipt']['Target']
        self.temp=tempfile.TemporaryDirectory(prefix='ecs-listener-offline-');self.addCleanup(self.temp.cleanup)
        self.directory=PrivateFixturePath(self.temp.name)
        self.digest=hashlib.sha256(prepare.encoded(self.value)).hexdigest()
        self.clock=patch.object(host,'utc',return_value='2026-10-24T19:10:01Z');self.clock.start();self.addCleanup(self.clock.stop)
        self.network={'SourceState':'terminated','TargetInstanceId':self.identity['instanceId'],'FixtureOnly':True}
        self.port=host.Port();self.port.application_network=Mock(return_value=self.network)
        self.port.secret=Mock(return_value='SYNTHETIC_NOT_EXPORTED')
        self.port.runtime_precheck=Mock(return_value=FakePort().runtime_precheck('fixture'))
        self.port.sql_stopped_observation=Mock(return_value={'ServiceState':'inactive','MainPid':0,'Tcp1433Listeners':0})
        self.port.selected_listener=Mock()
        self.calls=[]
        def run(argv,**kwargs):
            self.calls.append(argv)
            phase={0:'stop-intent',1:'config-intent',2:'start-intent'}[len(self.calls)-1]
            index=host.LISTENER_PHASES.index(phase)
            self.assertTrue((self.directory/('listener-transition-phase-'+str(index)+'.json')).exists())
            return ''
        self.port.run=Mock(side_effect=run)
        self.final={'Status':'APPLICATION_LISTENER_OBSERVATION_ONLY','NetworkBinding':self.network,
                    'RuntimePrecheck':{'FixtureOnly':True},'AllowsActivation':False}
        self.listener=patch.object(host,'check_application_listener',return_value=self.final)
        self.observe=self.listener.start();self.addCleanup(self.listener.stop)

    def call(self,ack=None):
        return host.transition_application_listener(self.port,self.value,self.identity,self.directory,
                                                   self.digest if ack is None else ack)

    def phases(self):
        return [json.loads(p.read_text())['Phase'] for p in sorted(self.directory.glob('listener-transition-phase-*.json'))]

    def test_ordered_fixed_steps_record_intent_before_each_effect_and_leave_no_secret(self):
        result=self.call()
        self.assertEqual(self.calls,[['systemctl','stop','mssql-server'],
            ['/opt/mssql/bin/mssql-conf','set','network.ipaddress','10.77.1.8'],
            ['systemctl','start','mssql-server']])
        self.assertEqual(self.phases(),list(host.LISTENER_PHASES))
        self.assertEqual(self.port.application_network.call_count,4)
        self.assertEqual(self.port.sql_stopped_observation.call_count,2)
        self.port.selected_listener.assert_called_once_with('10.77.1.8')
        self.assertEqual(result['Status'],'APPLICATION_LISTENER_TRANSITION_VERIFIED')
        self.assertFalse(result['AllowsActivation']);self.assertFalse(result['FullEcsRecoveryProven'])
        self.assertFalse(result['OwnerAuthorityEstablishedByAcknowledgement'])
        text=json.dumps(result)+''.join(p.read_text() for p in self.directory.iterdir())
        self.assertNotIn('SYNTHETIC_NOT_EXPORTED',text)

    def test_second_call_has_no_repeat_effect_and_readonly_review_does_not_claim_original_outcome(self):
        self.call();saved={p.name:p.read_bytes() for p in self.directory.iterdir()}
        with self.assertRaisesRegex(ValueError,'PREVIOUS_LISTENER_TRANSITION'):self.call()
        self.assertEqual(self.port.run.call_count,3)
        result=host.review_listener_transition(self.port,self.value,self.identity,self.directory)
        self.assertEqual(result['RecordedPhases'],list(host.LISTENER_PHASES))
        self.assertFalse(result['SafeToReplayTransition']);self.assertFalse(result['OriginalActionOutcomeResolved'])
        self.assertEqual(saved,{p.name:p.read_bytes() for p in self.directory.iterdir()})
        self.assertEqual(self.port.run.call_count,3)

    def test_each_unknown_effect_stops_and_preserves_intent_without_retry_or_compensation(self):
        for fail_at in (1,2,3):
            with self.subTest(fail_at=fail_at),tempfile.TemporaryDirectory() as tmp:
                self.directory=PrivateFixturePath(tmp);self.calls.clear();self.port.run.reset_mock()
                def run(argv,**kwargs):
                    self.calls.append(argv)
                    if len(self.calls)==fail_at:raise ValueError('CHILD_OUTCOME_UNKNOWN')
                    return ''
                self.port.run.side_effect=run
                with self.assertRaisesRegex(ValueError,'CHILD_OUTCOME_UNKNOWN'):self.call()
                self.assertEqual(len(self.calls),fail_at)
                self.assertEqual(self.phases()[-1],{1:'stop-intent',2:'config-intent',3:'start-intent'}[fail_at])
                with self.assertRaisesRegex(ValueError,'PREVIOUS_LISTENER_TRANSITION'):self.call()
                self.assertEqual(len(self.calls),fail_at)
                review=host.review_listener_transition(self.port,self.value,self.identity,self.directory)
                self.assertFalse(review['SafeToReplayTransition'])
                self.assertNotIn('verified',review['RecordedPhases'])
                self.assertEqual(len(self.calls),fail_at)

    def test_wrong_ack_stale_review_wrong_target_or_uncertain_fence_never_mutates(self):
        with self.assertRaisesRegex(ValueError,'EXACT_LISTENER_TRANSITION_ACK'):self.call('0'*64)
        with patch.object(host,'utc',return_value='2026-10-24T19:30:00Z'):
            with self.assertRaisesRegex(ValueError,'FRESH_LISTENER_TRANSITION_REVIEW'):self.call()
        old=self.identity;self.identity=dict(old,instanceId='i-'+'9'*17)
        with self.assertRaisesRegex(ValueError,'LISTENER_TARGET_IDENTITY'):self.call()
        self.identity=old;self.port.application_network.side_effect=ValueError('LISTENER_SOURCE_FENCE_UNCERTAIN')
        with self.assertRaisesRegex(ValueError,'FENCE_UNCERTAIN'):self.call()
        self.port.run.assert_not_called();self.port.secret.assert_not_called();self.assertFalse(list(self.directory.iterdir()))

    def test_still_active_wrong_config_or_changed_network_stops_before_start(self):
        for kind in ('active','config','network'):
            with self.subTest(kind=kind),tempfile.TemporaryDirectory() as tmp:
                self.directory=PrivateFixturePath(tmp);self.calls.clear();self.port.run.reset_mock()
                self.port.sql_stopped_observation.side_effect=None;self.port.selected_listener.side_effect=None
                self.port.application_network.side_effect=None
                if kind=='active':self.port.sql_stopped_observation.side_effect=ValueError('LISTENER_SQL_STOP_UNCONFIRMED')
                if kind=='config':self.port.selected_listener.side_effect=ValueError('SELECTED_GET_VALUE_MISMATCH')
                if kind=='network':self.port.application_network.side_effect=[self.network,self.network,dict(self.network,FixtureOnly=False)]
                with self.assertRaises(ValueError):self.call()
                self.assertNotIn(['systemctl','start','mssql-server'],self.calls)

    def test_failed_final_private_query_never_records_verified_or_changes_back(self):
        self.observe.side_effect=ValueError('FRESH_QUERY_BINDING_INVALID')
        with self.assertRaisesRegex(ValueError,'FRESH_QUERY_BINDING_INVALID'):self.call()
        self.assertEqual(len(self.calls),3)
        self.assertEqual(self.phases()[-1],'start-intent')
        self.assertFalse((self.directory/'listener-transition-phase-6.json').exists())

    def test_review_refuses_other_input_or_target_and_performs_no_mutations(self):
        self.call();path=self.directory/'listener-transition-phase-1.json'
        record=json.loads(path.read_text());record['ServiceInputSha256']='0'*64;path.write_text(json.dumps(record))
        with self.assertRaisesRegex(ValueError,'HISTORY_MISMATCH'):
            host.review_listener_transition(self.port,self.value,self.identity,self.directory)
        self.assertEqual(self.port.run.call_count,3)

    def test_review_rejects_changed_network_or_tampered_recorded_generation(self):
        self.call()
        self.observe.return_value=dict(self.final,NetworkBinding=dict(self.network,FixtureOnly=False))
        with self.assertRaisesRegex(ValueError,'LISTENER_NETWORK_CHANGED'):
            host.review_listener_transition(self.port,self.value,self.identity,self.directory)
        self.observe.return_value=self.final
        path=self.directory/'listener-transition-phase-1.json';original=json.loads(path.read_text())
        for change in (lambda x:x.update(NetworkSha256='0'*64),
                       lambda x:x['Target'].update(instanceId='i-'+'9'*17)):
            altered=copy.deepcopy(original);change(altered);path.write_text(json.dumps(altered))
            with self.assertRaisesRegex(ValueError,'HISTORY_MISMATCH'):
                host.review_listener_transition(self.port,self.value,self.identity,self.directory)
        self.assertEqual(self.port.run.call_count,3)

    def test_selected_listener_reuses_strict_native_get_parser(self):
        p=private_kernel()
        with patch.object(host.runtime_verify,'LocalPort',return_value=p):
            host.Port().selected_listener('10.77.1.8')
        p=private_kernel();p.answers['network.ipaddress']='ipaddress : 0.0.0.0'
        with patch.object(host.runtime_verify,'LocalPort',return_value=p):
            with self.assertRaises(host.runtime_verify.Problem):host.Port().selected_listener('10.77.1.8')

    def test_cli_default_is_inert_and_started_marker_refuses_replay(self):
        for action in ('listener-transition','listener-transition-review'):
            out=io.StringIO()
            with patch.object(sys,'argv',['host.py',action,'--trial',self.value['Trial'],'--directory',str(self.directory)]),patch.object(host,'Port') as factory,redirect_stdout(out):
                host.main()
            factory.assert_not_called();self.assertEqual(json.loads(out.getvalue())['Status'],'HOST_PLAN_ONLY')
        with patch.object(sys,'argv',['host.py','source','--trial',self.value['Trial'],'--directory',str(self.directory),
                                      '--listener-transition-approved-sha256',self.digest]):
            with self.assertRaisesRegex(ValueError,'ACK_ACTION_MISMATCH'):host.main()
        plan=self.directory/'plan.json';plan.write_text(json.dumps(self.value))
        args=['host.py','listener-transition','--trial',self.value['Trial'],'--directory',str(self.directory),
              '--execute','--acknowledge',self.value['Trial'],'--listener-plan',str(plan),
              '--expected-instance-id',self.identity['instanceId'],'--expected-az',self.identity['availabilityZone'],
              '--listener-transition-approved-sha256',self.digest]
        self.port.identity=Mock(return_value=self.identity)
        proxy=SimpleNamespace(**{k:getattr(os,k) for k in dir(os)})
        proxy.name='posix';proxy.geteuid=lambda:0;proxy.environ={}
        with patch.object(host,'os',proxy),patch.object(host,'Path',PrivateFixturePath),patch.object(sys,'argv',args),patch.object(host,'Port',return_value=self.port),patch.object(host,'transition_application_listener',side_effect=ValueError('OUTCOME_UNKNOWN')) as transition:
            with self.assertRaisesRegex(ValueError,'OUTCOME_UNKNOWN'):host.main()
            with self.assertRaisesRegex(ValueError,'PREVIOUS_ACTION_REQUIRES_REVIEW'):host.main()
        self.assertEqual(transition.call_count,1)
        self.assertTrue((self.directory/'listener-transition-receipt.started').exists())

    def test_native_readonly_stopped_adapter_rejects_lingering_service_or_socket(self):
        for state,pid,tcp in [('inactive','0','header\n'),('active','0','header\n'),('inactive','42','header\n'),
                              ('inactive','0','header\n0: 00000000:0599 0:0 0A 0 0 0 0 0 700\n'),
                              ('inactive','0',''),('inactive','0','header\nmalformed row\n')]:
            p=CapturedPidPort();p.props['ActiveState']=[state];p.props['MainPID']=[pid]
            p.texts['/proc/net/tcp']=tcp;p.texts['/proc/net/tcp6']='header\n'
            with patch.object(host.runtime_verify,'LocalPort',return_value=p):
                if state=='inactive' and pid=='0' and tcp=='header\n':
                    self.assertEqual(host.Port().sql_stopped_observation()['Tcp1433Listeners'],0)
                else:
                    with self.assertRaises(ValueError):host.Port().sql_stopped_observation()

if __name__=='__main__':unittest.main(verbosity=2)
