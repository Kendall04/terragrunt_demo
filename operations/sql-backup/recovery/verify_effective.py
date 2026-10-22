"""Linux observations and an explicit caller-supplied fresh SQL read probe.

No AWS calls or recovery acceptance claim. Imports are inert; fixtures are not live proof.
Never format exception messages, child output, config or environment in reports.
"""
import configparser
import json
import os
from pathlib import Path
import re
import subprocess

STAGES = frozenset(('environment', 'bootstrap_marker', 'service_state',
    'service_overrides', 'service_pid', 'config_file', 'config_memory', 'config_ip',
    'get_memory', 'get_ip', 'process_start', 'config_time', 'process_tree',
    'socket_ownership', 'listeners', 'stability', 'complete', 'verification_internal', 'runtime_binding_before', 'runtime_binding_after', 'fresh_sql_query', 'memory_environment', 'runtime_gate'))
CODES = frozenset(('ENVIRONMENT_UNSUPPORTED', 'SQL_READY_MARKER_MISSING',
    'SQL_NOT_ACTIVE', 'UNEXPECTED_UNIT_OVERRIDE', 'INVALID_MAIN_PID',
    'MEMORY_CAP_NOT_2048', 'IP_NOT_LOOPBACK', 'SELECTED_GET_FORMAT_UNSUPPORTED', 'SELECTED_GET_VALUE_MISMATCH',
    'CONFIG_AFTER_CURRENT_START', 'NON_LOOPBACK_LISTENER', 'LISTENER_NOT_SQL_SERVICE',
    'NO_SQL_LISTENER', 'SERVICE_CHANGED_DURING_OBSERVATION', 'COMMAND_EXIT_NONZERO',
    'INVALID_COMMAND_EXIT_CODE', 'COMMAND_OUTPUT_INVALID', 'COMMAND_OUTPUT_TOO_LARGE',
    'CONFIG_SECTION_MISSING', 'CONFIG_OPTION_MISSING', 'CONFIG_PARSE_ERROR',
    'METADATA_INVALID', 'READ_FAILED', 'TEXT_INVALID', 'READ_COMMAND_TIMEOUT',
    'UNEXPECTED_ERROR', 'INVALID_DIAGNOSTIC_CODE', 'INVALID_DIAGNOSTIC_STAGE', 'FILE_TOO_LARGE', 'ENVIRONMENT_TOO_LARGE', 'ENVIRONMENT_FORMAT_INVALID', 'MEMORY_ENV_DUPLICATE', 'MEMORY_ENV_ABSENT_REQUIRES_REVIEW', 'MEMORY_ENV_NOT_2048', 'MEMORY_PROJECTION_INVALID', 'PROCESS_IDENTITY_CHANGED', 'SQL_EXECUTABLE_MISMATCH', 'FRESH_QUERY_BINDING_INVALID', 'FRESH_QUERY_WRONG_PROCESS', 'RUNTIME_PRECHECK_INCOMPLETE'))


class Problem(Exception):
    def __init__(self, code, command_exit=None):
        super().__init__()  # No raw values/message in Exception.args.
        self.code, self.command_exit = code, command_exit


def failure(stage, error):
    child = None
    if not isinstance(stage, str) or stage not in STAGES:
        stage, code, exit = 'verification_internal', 'INVALID_DIAGNOSTIC_STAGE', 65
    elif isinstance(error, Problem):
        code = error.code
        if not isinstance(code, str) or not re.fullmatch(r'[A-Z][A-Z0-9_]{0,63}', code) or code not in CODES:
            code = 'INVALID_DIAGNOSTIC_CODE'
        exit = 69 if code == 'ENVIRONMENT_UNSUPPORTED' else 65
        if code == 'COMMAND_EXIT_NONZERO':
            child = error.command_exit
            if type(child) is not int or not (-64 <= child <= 255) or child == 0:
                code, child = 'INVALID_COMMAND_EXIT_CODE', None
            else: exit = child if child > 0 else 128 - child
    elif isinstance(error, subprocess.TimeoutExpired): code, exit = 'READ_COMMAND_TIMEOUT', 124
    elif isinstance(error, configparser.NoSectionError): code, exit = 'CONFIG_SECTION_MISSING', 65
    elif isinstance(error, configparser.NoOptionError): code, exit = 'CONFIG_OPTION_MISSING', 65
    elif isinstance(error, configparser.Error): code, exit = 'CONFIG_PARSE_ERROR', 65
    elif isinstance(error, UnicodeError): code, exit = 'TEXT_INVALID', 65
    elif isinstance(error, (ValueError, IndexError, StopIteration, TypeError, KeyError)):
        code, exit = 'METADATA_INVALID', 65
    elif isinstance(error, OSError): code, exit = 'READ_FAILED', 74
    else: code, exit = 'UNEXPECTED_ERROR', 65
    report = {'Status': 'REFUSED', 'Stage': stage, 'Code': code, 'ExitCode': exit}
    if child is not None: report['CommandExitCode'] = child
    return report


class LocalPort:
    def guard(self): return os.name == 'posix' and os.uname().sysname == 'Linux' and os.geteuid() == 0
    def text(self, path):
        with Path(path).open('r', encoding='utf-8') as stream: value = stream.read(1_048_577)
        if len(value) > 1_048_576: raise Problem('FILE_TOO_LARGE')
        return value
    def mtime(self, path): return Path(path).stat().st_mtime_ns
    def children(self, path): return [str(v) for v in Path(path).iterdir()]
    def link(self, path): return os.readlink(path)
    def clock_ticks(self): return os.sysconf('SC_CLK_TCK')
    def memory_projection(self, pid):
        with Path(f'/proc/{pid}/environ').open('rb', buffering=0) as stream:
            return project_memory_environment(stream)
    def run(self, args):
        # Read-only commands only; timeout never stops/restarts/kills SQL.
        return subprocess.run(args, capture_output=True, text=True, check=False, timeout=10)


class Verifier:
    def __init__(self, port): self.port, self.stage = port, 'environment'
    def require(self, condition, code):
        if not condition: raise Problem(code)
    def command(self, args):
        return self.command_result(self.port.run(args))
    def command_result(self, result):
        if type(result.returncode) is not int: raise Problem('INVALID_COMMAND_EXIT_CODE')
        if result.returncode: raise Problem('COMMAND_EXIT_NONZERO', result.returncode)
        self.require(isinstance(result.stdout, str), 'COMMAND_OUTPUT_INVALID')
        self.require(len(result.stdout) <= 65_536, 'COMMAND_OUTPUT_TOO_LARGE')
        return result.stdout.strip()
    def prop(self, name):
        return self.command(['systemctl', 'show', 'mssql-server', '--property=' + name, '--value'])
    def selected(self, section, key, expected):
        value = self.command(['/opt/mssql/bin/mssql-conf', 'get', section + '.' + key])
        # Two previously allowed forms, now exact: no arbitrary INI/defaults,
        # extra options/comments, or raw lines used as diagnostic codes.
        scalar = r'[0-9]+' if section == 'memory' else r'[0-9]{1,3}(?:\.[0-9]{1,3}){3}'
        if re.fullmatch(scalar, value): parsed = value
        else:
            ini = r'\[' + re.escape(section) + r'\][ \t]*\r?\n[ \t]*' + re.escape(key) + r'[ \t]*=[ \t]*(' + scalar + ')'
            match = re.fullmatch(ini, value)
            self.require(match is not None, 'SELECTED_GET_FORMAT_UNSUPPORTED')
            parsed = match[1]
        self.require(parsed == expected, 'SELECTED_GET_VALUE_MISMATCH')
    def verify(self):
        p = self.port
        self.require(p.guard(), 'ENVIRONMENT_UNSUPPORTED')
        self.stage = 'bootstrap_marker'
        self.require('RECOVERY_SQL_ENGINE_READY' in p.text('/var/log/ecs-recovery-bootstrap.log').splitlines(), 'SQL_READY_MARKER_MISSING')
        self.stage = 'service_state'; self.require(self.prop('ActiveState') == 'active', 'SQL_NOT_ACTIVE')
        self.stage = 'service_overrides'; self.require(self.prop('DropInPaths') == '', 'UNEXPECTED_UNIT_OVERRIDE')
        self.stage = 'service_pid'; pid = int(self.prop('MainPID')); self.require(pid > 1, 'INVALID_MAIN_PID'); self._main_pid = pid
        self.stage = 'config_file'
        before = p.mtime('/var/opt/mssql/mssql.conf'); self._config_time = before
        cfg = configparser.ConfigParser(interpolation=None); cfg.read_string(p.text('/var/opt/mssql/mssql.conf'))
        self.stage = 'config_memory'; self.require(cfg.getint('memory', 'memorylimitmb') == 2048, 'MEMORY_CAP_NOT_2048')
        self.stage = 'config_ip'; self.require(cfg.get('network', 'ipaddress') == '127.0.0.1', 'IP_NOT_LOOPBACK')
        self.stage = 'get_memory'; self.selected('memory', 'memorylimitmb', '2048')
        self.stage = 'get_ip'; self.selected('network', 'ipaddress', '127.0.0.1')
        self.stage = 'process_start'
        boot = [x.split()[1] for x in p.text('/proc/stat').splitlines() if x.startswith('btime ')]
        if len(boot) != 1: raise ValueError()
        btime = int(boot[0]); ticks = int(p.text(f'/proc/{pid}/stat').rsplit(')', 1)[1].split()[19])
        hz = p.clock_ticks()
        if btime < 0 or ticks < 0 or type(hz) is not int or hz <= 0: raise ValueError()
        self._main_ticks = ticks
        started = btime + ticks / hz
        self.stage = 'config_time'; self.require(before / 1e9 <= started + 1, 'CONFIG_AFTER_CURRENT_START')
        self.stage = 'process_tree'; pids, pending = {pid}, [pid]
        while pending:
            parent = pending.pop()
            for value in p.text(f'/proc/{parent}/task/{parent}/children').split():
                child = int(value)
                if child <= 1: raise ValueError()
                if child not in pids: pids.add(child); pending.append(child)
        self.stage = 'socket_ownership'; inodes = set(); inode_pids = {}; self._listener_pids = set()
        for value in pids:
            for fd in p.children(f'/proc/{value}/fd'):
                try: target = p.link(fd)
                except FileNotFoundError: continue  # Descriptor closed during observation.
                match = re.fullmatch(r'socket:\[(\d+)\]', target)
                if match:
                    inodes.add(match[1]); inode_pids.setdefault(match[1], set()).add(value)
        self.stage = 'listeners'; listeners = []
        for family in ('tcp', 'tcp6'):
            for row in p.text('/proc/net/' + family).splitlines()[1:]:
                fields = row.split()
                if len(fields) < 10: raise ValueError()
                address, port = fields[1].split(':')
                if fields[3] == '0A' and int(port, 16) == 1433:
                    self.require(family == 'tcp' and address == '0100007F', 'NON_LOOPBACK_LISTENER')
                    self.require(fields[9] in inodes, 'LISTENER_NOT_SQL_SERVICE')
                    listeners.append(fields[9]); self._listener_pids.update(inode_pids[fields[9]])
        self.require(bool(listeners), 'NO_SQL_LISTENER')
        self.stage = 'stability'
        self.require(p.mtime('/var/opt/mssql/mssql.conf') == before and int(self.prop('MainPID')) == pid and self.prop('ActiveState') == 'active', 'SERVICE_CHANGED_DURING_OBSERVATION')
        self.stage = 'complete'
        return {'Status': 'CONFIGURATION_OBSERVATION_ONLY', 'Stage': self.stage, 'ExitCode': 0,
                'PersistedMemoryPlatformCapMb': 2048, 'Ipv4Loopback1433Only': True,
                'ListenerOwnedBySqlServiceProcessTree': True, 'SqlQueryReadyMarkerPresent': True,
                'ConfigStartCorrelationToleranceSeconds': 1,
                'MemoryRuntimePrecedenceProven': False, 'CurrentQueryReadinessProven': False, 'RecoveryAcceptance': False}


def assess(port):
    verifier = Verifier(port)
    try: return verifier.verify()
    except Exception as error: return failure(verifier.stage, error)


def main(port=None):
    result = assess(LocalPort() if port is None else port)
    print(json.dumps(result, separators=(',', ':')))
    return result['ExitCode']


FRESH_QUERY = "SELECT CONCAT(CONVERT(varchar(12),SERVERPROPERTY('ProcessID')),'|',CONVERT(varchar(48),CONNECTIONPROPERTY('local_net_address')),'|',CONVERT(varchar(6),CONNECTIONPROPERTY('local_tcp_port')));"


def project_memory_environment(stream):
    """NUL stream projection: never assemble other keys/values or a raw environment.

    Only exact presence and equality to the single permitted value are returned.
    Buffers are transient Python memory, not a zeroization guarantee.
    """
    prefix, expected = b'MSSQL_MEMORY_LIMIT_MB=', b'2048'
    pos = count = total = 0
    candidate = equal = True
    permitted = False
    for chunk in iter(lambda: stream.read(4096), b''):
        total += len(chunk)
        if total > 1_048_576: raise Problem('ENVIRONMENT_TOO_LARGE')
        for byte in chunk:
            if byte == 0:
                if candidate and pos >= len(prefix):
                    count += 1
                    permitted = equal and pos - len(prefix) == len(expected)
                pos = 0; candidate = equal = True
            else:
                if pos < len(prefix): candidate = candidate and byte == prefix[pos]
                elif candidate:
                    offset = pos - len(prefix)
                    equal = equal and offset < len(expected) and byte == expected[offset]
                pos += 1
    # Linux documents NUL separators with an optional final NUL. EOF itself
    # terminates the last record; a partial/wrong selected value cannot match.
    if pos and candidate and pos >= len(prefix):
        count += 1
        permitted = equal and pos - len(prefix) == len(expected)
    if count > 1: raise Problem('MEMORY_ENV_DUPLICATE')
    return {'Presence': 'PRESENT' if count else 'ABSENT', 'ValueIsAllowed2048': permitted if count else None}


class RuntimeVerifier(Verifier):
    def __init__(self, port, query):
        super().__init__(port); self.query = query

    def token(self, pid):
        raw = self.port.text(f'/proc/{pid}/stat')
        if int(raw.split(' ', 1)[0]) != pid: raise Problem('PROCESS_IDENTITY_CHANGED')
        tick = int(raw.rsplit(')', 1)[1].split()[19])
        if tick <= 0: raise ValueError()
        self.require(self.port.link(f'/proc/{pid}/exe') == '/opt/mssql/bin/sqlservr', 'SQL_EXECUTABLE_MISMATCH')
        return tick

    def binding(self):
        self.require(self.prop('ActiveState') == 'active', 'SQL_NOT_ACTIVE')
        main = int(self.prop('MainPID'))
        self.require(main == self._main_pid, 'PROCESS_IDENTITY_CHANGED')
        tokens = {pid: self.token(pid) for pid in self._listener_pids | {main}}
        self.require(tokens[main] == self._main_ticks, 'PROCESS_IDENTITY_CHANGED')
        return main, tokens

    def verify(self):
        result = super().verify()
        self.stage = 'runtime_binding_before'; before = self.binding()
        self.stage = 'fresh_sql_query'
        answer = self.command_result(self.query()).strip()
        match = re.fullmatch(r'([1-9][0-9]{0,9})\|127\.0\.0\.1\|1433', answer)
        self.require(match is not None, 'FRESH_QUERY_BINDING_INVALID')
        sql_pid = int(match[1])
        self.require(sql_pid in self._listener_pids and sql_pid in before[1], 'FRESH_QUERY_WRONG_PROCESS')
        self.stage = 'memory_environment'
        projection = self.port.memory_projection(sql_pid)
        self.require(type(projection) is dict and set(projection) == {'Presence', 'ValueIsAllowed2048'}, 'MEMORY_PROJECTION_INVALID')
        self.require(projection['Presence'] == 'PRESENT', 'MEMORY_ENV_ABSENT_REQUIRES_REVIEW')
        self.require(projection['ValueIsAllowed2048'] is True, 'MEMORY_ENV_NOT_2048')
        self.stage = 'runtime_binding_after'
        self.require(self.binding() == before and self.port.mtime('/var/opt/mssql/mssql.conf') == self._config_time,
                     'PROCESS_IDENTITY_CHANGED')
        self.stage = 'complete'
        result.update(Status='RUNTIME_PRECHECK_INPUTS_BOUND', RuntimePrecheckSatisfied=True,
            InitialMemoryInputBoundToProcess=True, MemoryRuntimePrecedenceProven=False,
            CurrentQueryReadinessProven=True, StableProcessBinding=True,
            MemoryEnvironment={'Presence':'PRESENT','ValueIsAllowed2048':True},
            ProcessBinding={'MainPid':before[0], 'SqlPid':sql_pid, 'SqlStartTicks':before[1][sql_pid]},
            MemoryConsumptionMeasured=False, ConfigurationConsumptionProven=False, MemoryEvidenceKind='INITIAL_ENVIRONMENT_PROJECTION', RecoveryAcceptance=False)
        return result


def assess_runtime(port, query):
    verifier = RuntimeVerifier(port, query)
    try: return verifier.verify()
    except Exception as error: return failure(verifier.stage, error)


def require_runtime_precheck(report):
    """Runtime input/readiness precondition only, never complete recovery proof."""
    required = ('RuntimePrecheckSatisfied', 'InitialMemoryInputBoundToProcess',
                'CurrentQueryReadinessProven', 'StableProcessBinding')
    keys = frozenset(('Status','Stage','ExitCode','PersistedMemoryPlatformCapMb','Ipv4Loopback1433Only',
        'ListenerOwnedBySqlServiceProcessTree','SqlQueryReadyMarkerPresent','ConfigStartCorrelationToleranceSeconds',
        'MemoryRuntimePrecedenceProven','CurrentQueryReadinessProven','RecoveryAcceptance','RuntimePrecheckSatisfied',
        'InitialMemoryInputBoundToProcess','StableProcessBinding','MemoryEnvironment','ProcessBinding',
        'MemoryConsumptionMeasured','ConfigurationConsumptionProven','MemoryEvidenceKind'))
    if not isinstance(report, dict) or set(report) not in (keys, keys | {'HostBinding'}) or report.get('Status') != 'RUNTIME_PRECHECK_INPUTS_BOUND' or type(report.get('ExitCode')) is not int or report['ExitCode'] != 0 or report.get('Stage') != 'complete' or not all(report.get(k) is True for k in required):
        raise Problem('RUNTIME_PRECHECK_INCOMPLETE')
    binding = report.get('ProcessBinding', {})
    if type(binding) is not dict or set(binding) != {'MainPid','SqlPid','SqlStartTicks'} or any(type(value) is not int or value <= 1 for value in binding.values()):
        raise Problem('RUNTIME_PRECHECK_INCOMPLETE')
    projection = report.get('MemoryEnvironment')
    if type(projection) is not dict or set(projection) != {'Presence','ValueIsAllowed2048'} or projection['Presence'] != 'PRESENT' or projection['ValueIsAllowed2048'] is not True:
        raise Problem('RUNTIME_PRECHECK_INCOMPLETE')
    if type(report.get('PersistedMemoryPlatformCapMb')) is not int or report['PersistedMemoryPlatformCapMb'] != 2048 or any(report.get(k) is not True for k in ('Ipv4Loopback1433Only','ListenerOwnedBySqlServiceProcessTree','SqlQueryReadyMarkerPresent')) or type(report.get('ConfigStartCorrelationToleranceSeconds')) is not int or report['ConfigStartCorrelationToleranceSeconds'] != 1:
        raise Problem('RUNTIME_PRECHECK_INCOMPLETE')
    if report.get('MemoryRuntimePrecedenceProven') is not False or report.get('MemoryConsumptionMeasured') is not False or report.get('ConfigurationConsumptionProven') is not False or report.get('MemoryEvidenceKind') != 'INITIAL_ENVIRONMENT_PROJECTION' or report.get('RecoveryAcceptance') is not False:
        raise Problem('RUNTIME_PRECHECK_INCOMPLETE')
    return report


if __name__ == '__main__': raise SystemExit(main())
