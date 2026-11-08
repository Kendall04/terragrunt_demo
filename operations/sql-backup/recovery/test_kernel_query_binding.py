"""Captured PID regression with synthetic kernel ports; no native execution claim."""
import copy
import json
from pathlib import Path
import unittest
from unittest.mock import patch

import host
import verify_effective as v
from test_runtime_precheck import MetadataPort, query
from test_verify_effective import CANARY, ROW, NativeGetProtocol
from test_recovery import FakePort as DrillPort, NAME, IDENTITY

CAPTURE=json.loads((Path(__file__).parent/'fixtures/native-sql-pid-observation.json').read_text())


class CapturedPidPort(NativeGetProtocol, MetadataPort):
    def __init__(self):
        super().__init__()
        self.props['MainPID']=['16']*10
        for pid,start,children in [(16,4579,'18'),(18,4686,'')]:
            self.texts[f'/proc/{pid}/stat']=f'{pid} (sqlservr) S '+'0 '*18+str(start)
            self.texts[f'/proc/{pid}/task/{pid}/children']=children
            self.links[f'/proc/{pid}/exe']='/opt/mssql/bin/sqlservr'
        self.dirs['/proc/16/fd']=[]
        self.dirs['/proc/18/fd']=['/proc/18/fd/8']
        self.links['/proc/18/fd/8']='socket:[700]'


class KernelQueryBindingTests(unittest.TestCase):
    def run_check(self,port=None,action=None):
        port=port or CapturedPidPort()
        answer=f"{CAPTURE['ObservedSqlReportedProcessId']}|{CAPTURE['ObservedQueryEndpoint']}"
        report=v.assess_runtime(port,action or (lambda:query(answer)))
        self.assertNotIn(CANARY,json.dumps(report))
        return port,report

    def test_captured_distinct_logical_and_kernel_ids_bind_only_kernel_environment(self):
        port,report=self.run_check()
        v.require_runtime_precheck(report)
        self.assertEqual(report['ProcessBinding'],{'MainPid':16,'KernelSqlPid':18,'KernelSqlStartTicks':4686,'SqlReportedProcessId':380,'ListenerInode':700})
        self.assertEqual(port.environment_pids,[18])
        for key in ('MemoryRuntimePrecedenceProven','MemoryConsumptionMeasured','ConfigurationConsumptionProven','RecoveryAcceptance'):
            self.assertFalse(report[key])

    def test_foreign_listener_before_query_never_queries_or_projects_environment(self):
        port=CapturedPidPort();port.links['/proc/18/fd/8']='socket:[900]';called=[]
        _,report=self.run_check(port,lambda:(called.append(1),query())[1])
        self.assertEqual(report['Code'],'LISTENER_NOT_SQL_SERVICE')
        self.assertEqual(called,[]);self.assertEqual(port.environment_pids,[])

    def test_shared_listener_descriptor_is_ambiguous_and_refuses_before_query(self):
        port=CapturedPidPort();port.dirs['/proc/16/fd']=['/proc/16/fd/7'];port.links['/proc/16/fd/7']='socket:[700]';called=[]
        _,report=self.run_check(port,lambda:(called.append(1),query())[1])
        self.assertEqual((report['Stage'],report['Code']),('runtime_binding_before','LISTENER_NOT_SQL_SERVICE'))
        self.assertEqual(called,[])

    def test_foreign_owner_or_disappearing_listener_during_query_refuses(self):
        for change in ('owner','gone','additional'):
            port=CapturedPidPort()
            def action():
                if change=='owner':port.links['/proc/18/fd/8']='socket:[900]'
                elif change=='gone':port.texts['/proc/net/tcp']='header\n'
                else:port.texts['/proc/net/tcp']+='\n'+ROW.replace('700','900')+'\n'
                return query('380|127.0.0.1|1433')
            _,report=self.run_check(port,action)
            self.assertEqual(report['Status'],'REFUSED');self.assertEqual(report['Stage'],'runtime_binding_after')

    def test_same_pid_reopened_socket_cannot_pass_by_retaining_only_process_start(self):
        port=CapturedPidPort()
        def action():
            port.texts['/proc/net/tcp']=port.texts['/proc/net/tcp'].replace('700','701')
            port.links['/proc/18/fd/8']='socket:[701]'
            return query('380|127.0.0.1|1433')
        _,report=self.run_check(port,action)
        self.assertEqual((report['Stage'],report['Code']),('runtime_binding_after','PROCESS_IDENTITY_CHANGED'))

    def test_listener_restart_or_wrong_executable_after_query_refuses(self):
        for change in ('ticks','exe','parent'):
            port=CapturedPidPort()
            def action():
                if change=='ticks':port.texts['/proc/18/stat']=port.texts['/proc/18/stat'].rsplit(' ',1)[0]+' 9000'
                elif change=='exe':port.links['/proc/18/exe']='/tmp/'+CANARY
                else:port.texts['/proc/16/task/16/children']=''
                return query('380|127.0.0.1|1433')
            _,report=self.run_check(port,action)
            self.assertEqual(report['Status'],'REFUSED');self.assertEqual(report['Stage'],'runtime_binding_after')

    def test_socket_change_between_observation_and_query_refuses_before_query(self):
        port=CapturedPidPort();original=port.text;reads=[];called=[]
        def text(path):
            if path=='/proc/net/tcp':
                reads.append(1)
                if len(reads)>1:return original(path).replace('700','701')
            return original(path)
        port.text=text
        _,report=self.run_check(port,lambda:(called.append(1),query())[1])
        self.assertEqual((report['Stage'],report['Code']),('runtime_binding_before','PROCESS_IDENTITY_CHANGED'))
        self.assertEqual(called,[]);self.assertEqual(port.environment_pids,[])

    def test_logical_id_never_overrides_wrong_endpoint(self):
        for output in ('380|127.0.0.1|1434','380|0.0.0.0|1433','380|::1|1433','0|127.0.0.1|1433'):
            port,report=self.run_check(action=lambda:query(output))
            self.assertEqual((report['Stage'],report['Code']),('fresh_sql_query','FRESH_QUERY_BINDING_INVALID'))
            self.assertEqual(port.environment_pids,[])

    def test_old_or_contradictory_binding_report_is_not_accepted(self):
        _,good=self.run_check()
        for binding in ({'MainPid':16,'SqlPid':380,'SqlStartTicks':4686},
                        dict(good['ProcessBinding'],KernelSqlPid=0),
                        dict(good['ProcessBinding'],ListenerInode=True),
                        dict(good['ProcessBinding'],SqlReportedProcessId=0)):
            report=copy.deepcopy(good);report['ProcessBinding']=binding
            with self.assertRaises(v.Problem):v.require_runtime_precheck(report)

    def test_actual_source_adapter_uses_replacement_binding_before_synthetic_backup(self):
        drill=DrillPort();ports=[]
        def precheck(password):
            port=CapturedPidPort();ports.append(port)
            with patch.object(v,'LocalPort',return_value=port),patch.object(host.subprocess,'run',return_value=query('380|127.0.0.1|1433')):
                return host.Port().runtime_precheck(password)
        drill.runtime_precheck=precheck
        report=host.source(drill,NAME,None,None,None,IDENTITY)
        self.assertEqual(report['Status'],'SOURCE_BACKED_UP')
        self.assertEqual(report['RuntimePrecheck']['ProcessBinding']['KernelSqlPid'],18)
        self.assertEqual(report['RuntimePrecheck']['ProcessBinding']['SqlReportedProcessId'],380)
        self.assertEqual(ports[0].environment_pids,[18])
        self.assertFalse(report['RuntimePrecheck']['RecoveryAcceptance'])


if __name__=='__main__':unittest.main()
