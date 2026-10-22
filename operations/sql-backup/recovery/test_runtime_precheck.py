"""Metadata/query fixtures only, never native SQL, cloud or approval evidence."""
import io
import json
import types
import unittest
from unittest.mock import patch

import verify_effective as v
from test_verify_effective import FakePort as ObservationPort, CANARY
import host
from test_recovery import FakePort as DrillPort, NAME, IDENTITY, TARGET


class MetadataPort(ObservationPort):
    def __init__(self):
        super().__init__()
        self.props['MainPID']=['42']*10
        self.props['ActiveState']=['active']*10
        self.times=[1000_000_000_000]*3
        self.links['/proc/42/exe']='/opt/mssql/bin/sqlservr'
        self.raw_env=b'APP_PASSWORD='+CANARY.encode()+b'\0MSSQL_MEMORY_LIMIT_MB=2048\0'
        self.environment_reads=0
        self.environment_pids=[]
    def memory_projection(self,pid):
        self.environment_reads+=1
        self.environment_pids.append(pid)
        return v.project_memory_environment(io.BytesIO(self.raw_env))


def query(stdout='42|127.0.0.1|1433',rc=0):
    return types.SimpleNamespace(returncode=rc,stdout=stdout,stderr=CANARY)


class IntegrationGuardTests(unittest.TestCase):
    def test_source_rejects_observation_before_sql_or_app_secret(self):
        p=DrillPort();secrets=[];original=p.secret
        p.secret=lambda arn:(secrets.append(arn),original(arn))[1]
        p.runtime_precheck=lambda password:v.assess(ObservationPort())
        with self.assertRaises(ValueError):
            host.source(p,NAME,None,None,None,IDENTITY)
        self.assertEqual(p.commands,[])
        self.assertEqual(secrets,[host.SA_SECRET])

    def test_partial_report_or_failure_cannot_start_source(self):
        for report in ({'ExitCode':0}, {'Status':'REFUSED','Stage':'config_memory','Code':'MEMORY_CAP_NOT_2048','ExitCode':65}):
            p=DrillPort();p.runtime_precheck=lambda password:report
            with self.assertRaises(ValueError):host.source(p,NAME,None,None,None,IDENTITY)
            self.assertEqual(p.commands,[])

    def test_restore_rejects_old_source_receipt_before_side_effects(self):
        p=DrillPort()
        source=host.source(p,NAME,None,None,None,IDENTITY)
        failure=host.quiesce(p,source,IDENTITY)
        source.pop('RuntimePrecheck',None);p.commands.clear()
        with self.assertRaises(ValueError):host.restore(p,NAME,None,None,None,TARGET,source,failure)
        self.assertEqual(p.commands,[])

    def test_realistic_imds_extra_fields_and_host_binding(self):
        p=DrillPort();identity=dict(IDENTITY,architecture='x86_64',imageId='ami-fixture')
        source=host.source(p,NAME,None,None,None,identity)
        host.check_source_runtime(source)
        source['RuntimePrecheck']['HostBinding']['instanceId']=TARGET['instanceId']
        with self.assertRaises(ValueError):host.check_source_runtime(source)

    def test_runtime_failure_preserves_only_safe_codes_and_exit(self):
        for report,expected in [({'Status':'REFUSED','Stage':'fresh_sql_query','Code':'COMMAND_EXIT_NONZERO','ExitCode':17,'CommandExitCode':17,'raw':CANARY},17),
                                ({'Status':'REFUSED','Stage':'memory_environment','Code':'READ_FAILED','ExitCode':74},74),
                                ({'Status':'REFUSED','Stage':CANARY,'Code':CANARY,'ExitCode':65},65)]:
            error=host.RuntimePrecheckFailure(report)
            self.assertEqual(error.report['ExitCode'],expected);self.assertNotIn(CANARY,json.dumps(error.report))

    def test_native_query_adapter_uses_env_not_args_and_fixed_read_only_query(self):
        p=host.Port();captured={};metadata=MetadataPort()
        def child(args,**kwargs):
            captured.update(args=args,body=kwargs['input'],has_password=kwargs['env'].get('SQLCMDPASSWORD')==CANARY,timeout=kwargs['timeout'])
            self.assertNotIn(CANARY,str(args)+kwargs['input'])
            return query()
        with patch.object(v,'LocalPort',return_value=metadata),patch.object(host.subprocess,'run',side_effect=child):r=p.runtime_precheck(CANARY)
        v.require_runtime_precheck(r)
        self.assertTrue(captured['has_password']);self.assertEqual(captured['timeout'],15)
        self.assertIn(v.FRESH_QUERY,captured['body']);self.assertIn('tcp:127.0.0.1,1433',captured['args'])

    def test_target_observation_cannot_reach_restore_backup_or_ddl(self):
        p=DrillPort();source=host.source(p,NAME,None,None,None,IDENTITY);failure=host.quiesce(p,source,IDENTITY)
        p.commands.clear();p.runtime_precheck=lambda password:v.assess(ObservationPort())
        with self.assertRaises(ValueError):host.restore(p,NAME,None,None,None,TARGET,source,failure)
        self.assertEqual(p.commands,[])


class FileOnlyRegressionTests(unittest.TestCase):
    def test_file_only_2048_without_environment_override_is_configured_not_bound_input(self):
        p=MetadataPort();p.raw_env=b'PASSWORD='+CANARY.encode()+b'\0'
        r=v.assess_runtime(p,lambda:query());v.require_runtime_precheck(r)
        self.assertFalse(r['InitialMemoryInputBoundToProcess'])
        self.assertEqual(r['MemoryConfigurationBasis'],'FILE_NO_INITIAL_ENV_OVERRIDE')
        self.assertEqual(r['MemoryEnvironment'],{'Presence':'ABSENT','ValueIsAllowed2048':None,'Complete':True})
        self.assertFalse(r['ConfigurationConsumptionProven']);self.assertNotIn(CANARY,json.dumps(r))
    def test_ambiguous_partial_memory_key_is_not_certified_absent(self):
        for raw in (b'MSSQL_MEMORY_LIMIT_MB',b'MSSQL_MEMORY_LI\0'):
            with self.assertRaises(v.Problem):v.project_memory_environment(io.BytesIO(raw))
    def test_file_only_precheck_can_reach_existing_source_flow(self):
        p=DrillPort()
        def precheck(password):
            metadata=MetadataPort();metadata.raw_env=b''
            return v.assess_runtime(metadata,lambda:query())
        p.runtime_precheck=precheck
        r=host.source(p,NAME,None,None,None,IDENTITY)
        self.assertEqual(r['Status'],'SOURCE_BACKED_UP')
        self.assertFalse(r['RuntimePrecheck']['InitialMemoryInputBoundToProcess'])
        failure=host.quiesce(p,r,IDENTITY)
        restored=host.restore(p,NAME,None,None,None,TARGET,r,failure)
        self.assertEqual(restored['Status'],'TARGET_RECOVERED_REVIEW_EVIDENCE')
        self.assertEqual(restored['RuntimePrecheck']['MemoryConfigurationBasis'],'FILE_NO_INITIAL_ENV_OVERRIDE')
        self.assertFalse(restored['RuntimePrecheck']['InitialMemoryInputBoundToProcess'])

    def test_file_only_does_not_bypass_file_get_or_projection_consistency(self):
        for kind,stage,code in [('file','config_memory','MEMORY_CAP_NOT_2048'),('get','get_memory','SELECTED_GET_VALUE_MISMATCH')]:
            p=MetadataPort();p.raw_env=b''
            if kind=='file':p.texts['/var/opt/mssql/mssql.conf']=p.texts['/var/opt/mssql/mssql.conf'].replace('2048','4096')
            else:p.answers['memory.memorylimitmb']='4096'
            called=[];r=v.assess_runtime(p,lambda:(called.append(1),query())[1])
            self.assertEqual((r['Stage'],r['Code']),(stage,code));self.assertEqual(called,[])
        import copy
        p=MetadataPort();p.raw_env=b'';good=v.assess_runtime(p,lambda:query())
        for key,value in [('InitialMemoryInputBoundToProcess',True),('MemoryConfigurationBasis','FILE_AND_ALLOWED_INITIAL_ENV'),
                          ('MemoryEnvironment',{'Presence':'ABSENT','ValueIsAllowed2048':False,'Complete':True})]:
            r=copy.deepcopy(good);r[key]=value
            with self.assertRaises(v.Problem):v.require_runtime_precheck(r)

    def test_unknown_incomplete_or_contradictory_projection_is_not_absence(self):
        for projected in (None, {'Presence':'ABSENT','ValueIsAllowed2048':None},
                          {'Presence':'ABSENT','ValueIsAllowed2048':None,'Complete':False},
                          {'Presence':'UNKNOWN','ValueIsAllowed2048':None,'Complete':True},
                          {'Presence':'ABSENT','ValueIsAllowed2048':False,'Complete':True}):
            p=MetadataPort();p.memory_projection=lambda pid:projected
            r=v.assess_runtime(p,lambda:query())
            self.assertEqual((r['Stage'],r['Code']),('memory_environment','MEMORY_PROJECTION_INVALID'))
            self.assertNotIn(CANARY,json.dumps(r))


class ProjectionTests(unittest.TestCase):
    def project(self,raw):return v.project_memory_environment(io.BytesIO(raw))
    def test_only_permitted_presence_value_is_projected(self):
        for raw in (b'',b'PASSWORD='+CANARY.encode()+b'\0', b'MSSQL_MEMORY_LIMIT_MB_EXTRA=2048\0'):
            r=self.project(raw);self.assertEqual(r,{'Presence':'ABSENT','ValueIsAllowed2048':None,'Complete':True});self.assertNotIn(CANARY,json.dumps(r))
        for value,wanted in [(b'2048',True),(CANARY.encode(),False),(b'',False),(b'02048',False),(b'2048=secret',False)]:
            r=self.project(b'PASSWORD='+CANARY.encode()+b'\0MSSQL_MEMORY_LIMIT_MB='+value+b'\0TOKEN='+CANARY.encode()+b'\0')
            self.assertEqual(r,{'Presence':'PRESENT','ValueIsAllowed2048':wanted,'Complete':True});self.assertNotIn(CANARY,json.dumps(r))
    def test_chunk_boundaries_duplicate_truncation_and_size(self):
        class Short(io.BytesIO):
            def read(self,n):return super().read(1)
        self.assertTrue(v.project_memory_environment(Short(b'X=x\0MSSQL_MEMORY_LIMIT_MB=2048\0'))['ValueIsAllowed2048'])
        self.assertTrue(self.project(b'X=x\0MSSQL_MEMORY_LIMIT_MB=2048')['ValueIsAllowed2048'])
        self.assertFalse(self.project(b'MSSQL_MEMORY_LIMIT_MB=204')['ValueIsAllowed2048'])
        with self.assertRaises(v.Problem):self.project(b'MSSQL_MEMORY_LIMIT_MB')
        for raw,code in [(b'MSSQL_MEMORY_LIMIT_MB=2048\0MSSQL_MEMORY_LIMIT_MB=2048\0','MEMORY_ENV_DUPLICATE'),
                         (b'MSSQL_MEMORY_LIMIT_MB=2048\0MSSQL_MEMORY_LIMIT_MB=2048','MEMORY_ENV_DUPLICATE'),(b'X='+b'x'*1048576+b'\0','ENVIRONMENT_TOO_LARGE')]:
            with self.assertRaises(v.Problem) as caught:self.project(raw)
            self.assertEqual(caught.exception.code,code)


class RuntimeTests(unittest.TestCase):
    def check(self,p,callback=lambda:query()):
        r=v.assess_runtime(p,callback);self.assertNotIn(CANARY,json.dumps(r));return r
    def refused(self,p,callback,stage,code,exit=65):
        r=self.check(p,callback);self.assertEqual((r['Stage'],r['Code'],r['ExitCode']),(stage,code,exit));return r
    def test_bound_inputs_and_fresh_query_are_preconditions_not_consumption_measurement(self):
        p=MetadataPort();r=self.check(p)
        v.require_runtime_precheck(r)
        self.assertTrue(r['InitialMemoryInputBoundToProcess']);self.assertTrue(r['CurrentQueryReadinessProven'])
        self.assertFalse(r['MemoryRuntimePrecedenceProven'])
        self.assertFalse(r['MemoryConsumptionMeasured']);self.assertFalse(r['ConfigurationConsumptionProven']);self.assertFalse(r['RecoveryAcceptance'])
        self.assertEqual(p.environment_reads,1)
    def test_observation_is_not_enough(self):
        with self.assertRaises(v.Problem):v.require_runtime_precheck(v.assess(ObservationPort()))

    def test_malformed_or_extra_fields_cannot_be_promoted_to_precheck(self):
        import copy
        good=self.check(MetadataPort())
        for key,value in [('ExitCode',False),('ProcessBinding',None),('MemoryEnvironment',{'Presence':'PRESENT','ValueIsAllowed2048':1}),
                          ('MemoryConsumptionMeasured',True),('MemoryRuntimePrecedenceProven',True),('debug',CANARY),('Ipv4Loopback1433Only',1)]:
            r=copy.deepcopy(good);r[key]=value
            with self.assertRaises(v.Problem):v.require_runtime_precheck(r)

    def test_child_sql_pid_must_own_listener_and_only_it_is_projected(self):
        p=MetadataPort();p.texts['/proc/42/task/42/children']='43';p.texts['/proc/43/task/43/children']=''
        p.texts['/proc/43/stat']=p.texts['/proc/42/stat'].replace('42 (','43 (')
        p.links['/proc/43/exe']='/opt/mssql/bin/sqlservr';p.dirs['/proc/43/fd']=['/proc/43/fd/8'];p.links['/proc/43/fd/8']='socket:[700]'
        p.links['/proc/42/fd/3']='/tmp/'+CANARY
        r=self.check(p,lambda:query('43|127.0.0.1|1433'));v.require_runtime_precheck(r)
        self.assertEqual(p.environment_pids,[43]);self.assertEqual(r['ProcessBinding']['MainPid'],42)
    def test_pid_rotation_before_query_prevents_query_and_environment_read(self):
        for prop,value in [('MainPID','43')]:
            p=MetadataPort();p.props[prop]=['42','42',value]
            called=[];self.refused(p,lambda:(called.append(1),query())[1],'runtime_binding_before','PROCESS_IDENTITY_CHANGED')
            self.assertEqual(called,[]);self.assertEqual(p.environment_reads,0)
    def test_reused_pid_starttime_or_executable_change_after_query_refuses(self):
        for change in ('ticks','exe','pid','config'):
            p=MetadataPort()
            def action():
                if change=='ticks':p.texts['/proc/42/stat']=p.texts['/proc/42/stat'].rsplit(' ',1)[0]+' 600'
                elif change=='exe':p.links['/proc/42/exe']='/tmp/'+CANARY
                elif change=='pid':p.props['MainPID']=['43']
                else:p.times=[1000_000_000_001]
                return query()
            r=self.check(p,action);self.assertEqual(r['Status'],'REFUSED');self.assertEqual(r['Stage'],'runtime_binding_after')
    def test_fresh_query_wrong_pid_ip_port_format_and_raw_failure(self):
        for value,code in [('43|127.0.0.1|1433','FRESH_QUERY_WRONG_PROCESS'),('42|0.0.0.0|1433','FRESH_QUERY_BINDING_INVALID'),
                           ('42|127.0.0.1|1434','FRESH_QUERY_BINDING_INVALID'),(CANARY,'FRESH_QUERY_BINDING_INVALID')]:
            p=MetadataPort();self.refused(p,lambda:query(value),'fresh_sql_query',code);self.assertEqual(p.environment_reads,0)
        self.refused(MetadataPort(),lambda:query(CANARY,17),'fresh_sql_query','COMMAND_EXIT_NONZERO',17)
    def test_wrong_or_unreadable_environment_never_certifies(self):
        for raw,code in [(b'MSSQL_MEMORY_LIMIT_MB='+CANARY.encode()+b'\0','MEMORY_ENV_NOT_2048')]:
            p=MetadataPort();p.raw_env=raw;self.refused(p,lambda:query(),'memory_environment',code)
        p=MetadataPort();p.memory_projection=lambda pid:(_ for _ in ()).throw(OSError(CANARY))
        self.refused(p,lambda:query(),'memory_environment','READ_FAILED',74)

    def test_query_timeout_and_rotation_during_projection_are_refused(self):
        import subprocess
        p=MetadataPort()
        self.refused(p,lambda:(_ for _ in ()).throw(subprocess.TimeoutExpired(CANARY,15,output=CANARY,stderr=CANARY)),
                     'fresh_sql_query','READ_COMMAND_TIMEOUT',124)
        self.assertEqual(p.environment_reads,0)
        p=MetadataPort();original=p.memory_projection
        def rotated(pid):
            r=original(pid);p.texts['/proc/42/stat']=p.texts['/proc/42/stat'].rsplit(' ',1)[0]+' 600';return r
        p.memory_projection=rotated
        self.refused(p,lambda:query(),'runtime_binding_after','PROCESS_IDENTITY_CHANGED')
    def test_native_projection_adapter_reads_only_bound_path_and_emits_no_environment(self):
        with patch.object(v,'Path') as path:
            path.return_value.open.return_value.__enter__.return_value=io.BytesIO(b'TOKEN='+CANARY.encode()+b'\0MSSQL_MEMORY_LIMIT_MB=2048\0')
            r=v.LocalPort().memory_projection(42)
            path.assert_called_once_with('/proc/42/environ');self.assertTrue(r['ValueIsAllowed2048']);self.assertNotIn(CANARY,json.dumps(r))


if __name__=='__main__':unittest.main()
