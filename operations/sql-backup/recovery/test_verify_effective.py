"""Hermetic metadata fixtures, not native SQL/Ubuntu/authority evidence."""
import contextlib
import io
import json
from pathlib import Path
import subprocess
import sys
import types
import unittest

import verify_effective as v

CANARY = 'AWS_SECRET_ACCESS_KEY'
CONFIG = '[memory]\nmemorylimitmb = 2048\n[network]\nipaddress = 127.0.0.1\n'
ROW = '0: 0100007F:0599 00000000:0000 0A 0:0 00:0 0 0 0 700 1'


class FakePort:
    def __init__(self):
        self.props = {'ActiveState': ['active', 'active'], 'DropInPaths': [''], 'MainPID': ['42', '42']}
        self.texts = {'/var/log/ecs-recovery-bootstrap.log': 'RECOVERY_SQL_ENGINE_READY\n',
                      '/var/opt/mssql/mssql.conf': CONFIG, '/proc/stat': 'btime 1000\n',
                      '/proc/42/stat': '42 (sql worker) S ' + '0 ' * 18 + '500',
                      '/proc/42/task/42/children': '', '/proc/net/tcp': 'header\n' + ROW + '\n',
                      '/proc/net/tcp6': 'header\n'}
        self.times = [1000_000_000_000, 1000_000_000_000]
        self.dirs = {'/proc/42/fd': ['/proc/42/fd/3', '/proc/42/fd/4']}
        self.links = {'/proc/42/fd/3': 'socket:[700]', '/proc/42/fd/4': '/tmp/' + CANARY}
        self.answers = {'memory.memorylimitmb': '[memory]\nmemorylimitmb = 2048\n',
                        'network.ipaddress': '[network]\nipaddress = 127.0.0.1\n'}
        self.exit = 0
        self.stderr = ''
        self.calls = []
        self.authorized_host = True
        self.ticks = 100

    def guard(self): return self.authorized_host
    def text(self, path):
        value = self.texts[path]
        if isinstance(value, Exception): raise value
        return value
    def mtime(self, path): return self.times.pop(0)
    def children(self, path): return self.dirs[path]
    def link(self, path):
        value = self.links[path]
        if isinstance(value, Exception): raise value
        return value
    def clock_ticks(self): return self.ticks
    def run(self, args):
        self.calls.append(args)
        if args[0] == 'systemctl':
            name = args[3].removeprefix('--property=')
            values = self.props[name]
            value = values.pop(0) if len(values) > 1 else values[0]
            if isinstance(value, Exception): raise value
            return types.SimpleNamespace(returncode=self.exit, stdout=value, stderr=self.stderr)
        if args[:2] == ['/opt/mssql/bin/mssql-conf', 'get']:
            value = self.answers[args[2]]
            if isinstance(value, Exception): raise value
            return types.SimpleNamespace(returncode=self.exit, stdout=value, stderr=self.stderr)
        raise RuntimeError(CANARY)


class DiagnosticRegressionTests(unittest.TestCase):
    def test_authored_alphanumeric_code_and_exact_stage_survive(self):
        error = v.Problem('MEMORY_CAP_NOT_2048') if hasattr(v, 'Problem') else AssertionError('MEMORY_CAP_NOT_2048')
        r = v.failure('config_memory', error)
        self.assertEqual(r.get('Stage'), 'config_memory')
        self.assertEqual(r['Code'], 'MEMORY_CAP_NOT_2048')
        self.assertEqual(r['ExitCode'], 65)

    def test_arbitrary_uppercase_assertion_canary_is_never_a_code(self):
        r = v.failure('config_memory', AssertionError(CANARY))
        self.assertNotIn(CANARY, json.dumps(r))
        self.assertEqual(r['Code'], 'UNEXPECTED_ERROR')

    def test_exception_message_never_becomes_output(self):
        r = v.failure('config_memory', ValueError(CANARY))
        self.assertEqual(r.get('Stage'), 'config_memory')
        self.assertEqual(r['Code'], 'METADATA_INVALID')
        self.assertNotIn(CANARY, json.dumps(r))


class VerifierTests(unittest.TestCase):
    def result(self, port):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            rc = v.main(port)
        self.assertEqual(err.getvalue(), '')
        self.assertEqual(len(out.getvalue().splitlines()), 1)
        self.assertNotIn(CANARY, out.getvalue())
        r = json.loads(out.getvalue())
        self.assertEqual(r['ExitCode'], rc)
        return r

    def refused(self, port, stage, code, exit=65):
        r = self.result(port)
        self.assertEqual((r['Status'], r['Stage'], r['Code'], r['ExitCode']), ('REFUSED', stage, code, exit))
        return r

    def test_success_is_observation_only_not_runtime_precedence_or_recovery(self):
        r = self.result(FakePort())
        self.assertEqual(r['Status'], 'CONFIGURATION_OBSERVATION_ONLY')
        self.assertFalse(r['MemoryRuntimePrecedenceProven'])
        self.assertFalse(r['CurrentQueryReadinessProven'])
        self.assertFalse(r['RecoveryAcceptance'])
        self.assertTrue(r['Ipv4Loopback1433Only'])

    def test_unsupported_environment_never_reads_or_runs(self):
        p = FakePort(); p.authorized_host = False
        self.refused(p, 'environment', 'ENVIRONMENT_UNSUPPORTED', 69)
        self.assertEqual(p.calls, [])

    def test_missing_marker_has_json_stage_and_ignores_raw_log(self):
        for value in (CANARY, CANARY+'\nRECOVERY_SQL_ENGINE_READY extra\n'):
            p = FakePort(); p.texts['/var/log/ecs-recovery-bootstrap.log'] = value
            self.refused(p, 'bootstrap_marker', 'SQL_READY_MARKER_MISSING')

    def test_service_state_override_and_pid_branches(self):
        for key, value, stage, code in [('ActiveState','inactive','service_state','SQL_NOT_ACTIVE'),
            ('DropInPaths',CANARY,'service_overrides','UNEXPECTED_UNIT_OVERRIDE'),
            ('MainPID','0','service_pid','INVALID_MAIN_PID'), ('MainPID',CANARY,'service_pid','METADATA_INVALID')]:
            with self.subTest(stage=stage, value=value):
                p=FakePort();p.props[key]=[value];self.refused(p,stage,code)

    def test_config_file_missing_malformed_section_option_and_selected_values(self):
        for value, stage, code in [(OSError(CANARY),'config_file','READ_FAILED'),
            (CANARY,'config_file','CONFIG_PARSE_ERROR'),('[network]\nipaddress=127.0.0.1\n','config_memory','CONFIG_SECTION_MISSING'),
            ('[memory]\n[network]\nipaddress=127.0.0.1\n','config_memory','CONFIG_OPTION_MISSING'),
            (CONFIG.replace('2048',CANARY),'config_memory','METADATA_INVALID'),
            (CONFIG.replace('2048','4096'),'config_memory','MEMORY_CAP_NOT_2048'),
            (CONFIG.replace('127.0.0.1','0.0.0.0'),'config_ip','IP_NOT_LOOPBACK')]:
            with self.subTest(code=code):
                p=FakePort();p.texts['/var/opt/mssql/mssql.conf']=value
                self.refused(p,stage,code,74 if isinstance(value,OSError) else 65)

    def test_selected_get_accepts_only_existing_scalar_or_exact_single_field_ini(self):
        for answers in [{'memory.memorylimitmb':'2048\n','network.ipaddress':'127.0.0.1\n'},
                        {'memory.memorylimitmb':'[memory]\r\nmemorylimitmb = 2048\r\n','network.ipaddress':'[network]\nipaddress=127.0.0.1\n'}]:
            p=FakePort();p.answers=answers
            self.assertEqual(self.result(p)['ExitCode'],0)

    def test_selected_get_rejects_extra_rows_defaults_comments_wrong_fields_and_canary(self):
        for key in ('memory.memorylimitmb','network.ipaddress'):
            for value in [CANARY, '[memory]\nmemorylimitmb=4096', '[DEFAULT]\npassword='+CANARY+'\n[memory]\nmemorylimitmb=2048',
                          '[memory]\nmemorylimitmb=2048\npassword='+CANARY, '2048\n'+CANARY, '#'+CANARY+'\n2048',
                          '[memory]\nmemorylimitmb=2048\n[memory]\nmemorylimitmb=2048']:
                with self.subTest(key=key,value=value):
                    p=FakePort();p.answers[key]=value
                    code='SELECTED_GET_VALUE_MISMATCH' if key=='memory.memorylimitmb' and value=='[memory]\nmemorylimitmb=4096' else 'SELECTED_GET_FORMAT_UNSUPPORTED'
                    self.refused(p,'get_memory' if key.startswith('memory') else 'get_ip',code)
        for key,value,stage in [('memory.memorylimitmb','4096','get_memory'),('network.ipaddress','0.0.0.0','get_ip')]:
            p=FakePort();p.answers[key]=value;self.refused(p,stage,'SELECTED_GET_VALUE_MISMATCH')

    def test_command_stdout_stderr_and_exit_codes_never_echo_raw_data(self):
        p=FakePort();p.stderr=CANARY;self.assertEqual(self.result(p)['ExitCode'],0)
        for rc, expected in [(42,42),(-15,143),(255,255)]:
            p=FakePort();p.exit=rc;p.props['ActiveState']=[CANARY];p.stderr=CANARY
            r=self.refused(p,'service_state','COMMAND_EXIT_NONZERO',expected)
            self.assertEqual(r['CommandExitCode'],rc)
        p=FakePort();base=p.run
        def get_failure(args):
            if args[0].endswith('mssql-conf'):
                return types.SimpleNamespace(returncode=17,stdout=CANARY,stderr=CANARY)
            return base(args)
        p.run=get_failure
        self.refused(p,'get_memory','COMMAND_EXIT_NONZERO',17)

    def test_read_command_timeout_and_exceptions_have_fixed_codes_no_output(self):
        for error,code,exit in [(subprocess.TimeoutExpired(CANARY,10,output=CANARY,stderr=CANARY),'READ_COMMAND_TIMEOUT',124),
                                (RuntimeError(CANARY),'UNEXPECTED_ERROR',65), (OSError(CANARY),'READ_FAILED',74)]:
            p=FakePort();p.props['ActiveState']=[error]
            self.refused(p,'service_state',code,exit)

    def test_proc_boot_clock_and_start_metadata_branches(self):
        for path,value in [('/proc/stat',CANARY),('/proc/stat','btime -1'),('/proc/42/stat',CANARY)]:
            p=FakePort();p.texts[path]=value;self.refused(p,'process_start','METADATA_INVALID')
        p=FakePort();p.ticks=0;self.refused(p,'process_start','METADATA_INVALID')
        p=FakePort();p.times=[1007_000_000_000]*2;self.refused(p,'config_time','CONFIG_AFTER_CURRENT_START')

    def test_process_tree_child_socket_and_regular_fd_are_supported(self):
        p=FakePort();p.texts['/proc/42/task/42/children']='43';p.texts['/proc/43/task/43/children']=''
        p.dirs['/proc/43/fd']=['/proc/43/fd/9'];p.links['/proc/43/fd/9']='socket:[700]';p.links['/proc/42/fd/3']='/data/'+CANARY
        self.assertEqual(self.result(p)['ExitCode'],0)

    def test_bad_child_metadata_and_fd_race_or_read_failure(self):
        p=FakePort();p.texts['/proc/42/task/42/children']=CANARY
        self.refused(p,'process_tree','METADATA_INVALID')
        p=FakePort();p.links['/proc/42/fd/4']=FileNotFoundError(CANARY)
        self.assertEqual(self.result(p)['ExitCode'],0)
        p=FakePort();p.links['/proc/42/fd/4']=PermissionError(CANARY)
        self.refused(p,'socket_ownership','READ_FAILED',74)

    def test_listener_skip_non_listen_other_port_and_all_refusals(self):
        p=FakePort();p.texts['/proc/net/tcp']+='1: 00000000:1234 0:0 0A 0 0 0 0 0 999\n2: 00000000:0599 0:0 01 0 0 0 0 0 999\n'
        self.assertEqual(self.result(p)['ExitCode'],0)
        for path,value,code in [('/proc/net/tcp','header\n','NO_SQL_LISTENER'),
            ('/proc/net/tcp','header\n'+ROW.replace('0100007F','00000000'),'NON_LOOPBACK_LISTENER'),
            ('/proc/net/tcp6','header\n'+ROW,'NON_LOOPBACK_LISTENER'),
            ('/proc/net/tcp','header\n'+ROW.replace('700','999'),'LISTENER_NOT_SQL_SERVICE'),
            ('/proc/net/tcp','header\n'+CANARY,'METADATA_INVALID')]:
            p=FakePort();p.texts[path]=value;self.refused(p,'listeners',code)

    def test_final_config_pid_or_state_change_refuses(self):
        for kind in ('config','pid','state'):
            p=FakePort()
            if kind=='config':p.times[1]+=1
            elif kind=='pid':p.props['MainPID']=['42','43']
            else:p.props['ActiveState']=['active','deactivating']
            self.refused(p,'stability','SERVICE_CHANGED_DURING_OBSERVATION')

    def test_unknown_safe_looking_code_and_unknown_stage_cannot_leak_canary(self):
        r=v.failure('config_memory',v.Problem(CANARY));self.assertNotIn(CANARY,json.dumps(r));self.assertEqual(r['Code'],'INVALID_DIAGNOSTIC_CODE')
        r=v.failure(CANARY,v.Problem('MEMORY_CAP_NOT_2048'));self.assertNotIn(CANARY,json.dumps(r));self.assertEqual(r['Stage'],'verification_internal')
        for stage in (None, [CANARY]):
            self.assertEqual(v.failure(stage,ValueError(CANARY))['Code'],'INVALID_DIAGNOSTIC_STAGE')

    def test_command_output_type_size_and_invalid_returncodes_fail_closed(self):
        for value,code in [(None,'COMMAND_OUTPUT_INVALID'),('x'*65537,'COMMAND_OUTPUT_TOO_LARGE')]:
            p=FakePort();p.props['ActiveState']=[value];self.refused(p,'service_state',code)
        for rc in (0.0,False,256,-65,'42'):
            p=FakePort();p.exit=rc;self.refused(p,'service_state','INVALID_COMMAND_EXIT_CODE')

    def test_config_ip_missing_section_option_and_parse_errors_keep_stage(self):
        for value,code in [('[memory]\nmemorylimitmb=2048','CONFIG_SECTION_MISSING'),
                           ('[memory]\nmemorylimitmb=2048\n[network]','CONFIG_OPTION_MISSING')]:
            p=FakePort();p.texts['/var/opt/mssql/mssql.conf']=value;self.refused(p,'config_ip',code)
        p=FakePort();p.texts['/var/opt/mssql/mssql.conf']=UnicodeDecodeError('utf-8',b'\xff',0,1,CANARY)
        self.refused(p,'config_file','TEXT_INVALID')

    def test_both_selected_get_command_failure_stages_remain_distinct(self):
        for key,stage in [('memory.memorylimitmb','get_memory'),('network.ipaddress','get_ip')]:
            p=FakePort();p.answers[key]=subprocess.TimeoutExpired(CANARY,10,output=CANARY,stderr=CANARY)
            self.refused(p,stage,'READ_COMMAND_TIMEOUT',124)

    def test_duplicate_boot_record_negative_child_and_repeated_tree_nodes(self):
        p=FakePort();p.texts['/proc/stat']='btime 1000\nbtime 1000\n';self.refused(p,'process_start','METADATA_INVALID')
        p=FakePort();p.texts['/proc/42/task/42/children']='0';self.refused(p,'process_tree','METADATA_INVALID')
        p=FakePort();p.texts['/proc/42/task/42/children']='43 43';p.texts['/proc/43/task/43/children']='42';p.dirs['/proc/43/fd']=[]
        self.assertEqual(self.result(p)['ExitCode'],0)

    def test_real_adapter_methods_are_mocked_and_read_only(self):
        from unittest.mock import patch
        port=v.LocalPort()
        node=types.SimpleNamespace(open=lambda *a,**k:contextlib.nullcontext(io.StringIO('public')),stat=lambda:types.SimpleNamespace(st_mtime_ns=7),iterdir=lambda:iter([Path('fd')]))
        with patch.object(v,'Path',return_value=node):
            self.assertEqual(port.text('fixture'),'public');self.assertEqual(port.mtime('fixture'),7);self.assertEqual(port.children('fixture'),['fd'])
        node.open=lambda *a,**k:contextlib.nullcontext(io.StringIO('x'*1048577))
        with patch.object(v,'Path',return_value=node):
            with self.assertRaises(v.Problem):port.text('fixture')
        with patch.object(v.os,'readlink',return_value='socket:[7]') as call:
            self.assertEqual(port.link('fixture'),'socket:[7]');call.assert_called_once_with('fixture')
        with patch.object(v.os,'sysconf',return_value=100,create=True):self.assertEqual(port.clock_ticks(),100)
        with patch.object(v.subprocess,'run',return_value=types.SimpleNamespace(returncode=0,stdout='public',stderr=CANARY)) as call:
            port.run(['systemctl','show'])
            self.assertEqual(call.call_args.kwargs,{'capture_output':True,'text':True,'check':False,'timeout':10})
        with patch.object(v.os,'name','nt'):self.assertFalse(port.guard())
        for name,uid,wanted in [('Linux',0,True),('Linux',1,False),('Darwin',0,False)]:
            with patch.object(v,'os',types.SimpleNamespace(name='posix',uname=lambda:types.SimpleNamespace(sysname=name),geteuid=lambda:uid)):
                self.assertEqual(port.guard(),wanted)

    def test_optimization_does_not_disable_security_checks(self):
        env={k:val for k,val in __import__('os').environ.items() if not k.startswith(('AWS_','TF_'))}
        body="import test_verify_effective as t, verify_effective as v; p=t.FakePort(); p.texts['/var/opt/mssql/mssql.conf']=t.CONFIG.replace('2048','4096'); r=v.assess(p); print(r['Code']); raise SystemExit(0 if r['Code']=='MEMORY_CAP_NOT_2048' else 1)"
        r=subprocess.run([sys.executable,'-O','-c',body],cwd=Path(__file__).parent,env=env,capture_output=True,text=True,timeout=10)
        self.assertEqual(r.returncode,0,r.stderr);self.assertEqual(r.stdout.strip(),'MEMORY_CAP_NOT_2048')


if __name__=='__main__':unittest.main()
