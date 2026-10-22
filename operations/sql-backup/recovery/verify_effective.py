"""Read-only Linux observations; no AWS/SQL calls or recovery acceptance claim.

Imports are inert. Tests supply metadata-only ports, not live authority/evidence.
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
    'socket_ownership', 'listeners', 'stability', 'complete', 'verification_internal'))
CODES = frozenset(('ENVIRONMENT_UNSUPPORTED', 'SQL_READY_MARKER_MISSING',
    'SQL_NOT_ACTIVE', 'UNEXPECTED_UNIT_OVERRIDE', 'INVALID_MAIN_PID',
    'MEMORY_CAP_NOT_2048', 'IP_NOT_LOOPBACK', 'SELECTED_GET_FORMAT_UNSUPPORTED', 'SELECTED_GET_VALUE_MISMATCH',
    'CONFIG_AFTER_CURRENT_START', 'NON_LOOPBACK_LISTENER', 'LISTENER_NOT_SQL_SERVICE',
    'NO_SQL_LISTENER', 'SERVICE_CHANGED_DURING_OBSERVATION', 'COMMAND_EXIT_NONZERO',
    'INVALID_COMMAND_EXIT_CODE', 'COMMAND_OUTPUT_INVALID', 'COMMAND_OUTPUT_TOO_LARGE',
    'CONFIG_SECTION_MISSING', 'CONFIG_OPTION_MISSING', 'CONFIG_PARSE_ERROR',
    'METADATA_INVALID', 'READ_FAILED', 'TEXT_INVALID', 'READ_COMMAND_TIMEOUT',
    'UNEXPECTED_ERROR', 'INVALID_DIAGNOSTIC_CODE', 'INVALID_DIAGNOSTIC_STAGE', 'FILE_TOO_LARGE'))


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
    def run(self, args):
        # Read-only commands only; timeout never stops/restarts/kills SQL.
        return subprocess.run(args, capture_output=True, text=True, check=False, timeout=10)


class Verifier:
    def __init__(self, port): self.port, self.stage = port, 'environment'
    def require(self, condition, code):
        if not condition: raise Problem(code)
    def command(self, args):
        result = self.port.run(args)
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
        self.stage = 'service_pid'; pid = int(self.prop('MainPID')); self.require(pid > 1, 'INVALID_MAIN_PID')
        self.stage = 'config_file'
        before = p.mtime('/var/opt/mssql/mssql.conf')
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
        started = btime + ticks / hz
        self.stage = 'config_time'; self.require(before / 1e9 <= started + 1, 'CONFIG_AFTER_CURRENT_START')
        self.stage = 'process_tree'; pids, pending = {pid}, [pid]
        while pending:
            parent = pending.pop()
            for value in p.text(f'/proc/{parent}/task/{parent}/children').split():
                child = int(value)
                if child <= 1: raise ValueError()
                if child not in pids: pids.add(child); pending.append(child)
        self.stage = 'socket_ownership'; inodes = set()
        for value in pids:
            for fd in p.children(f'/proc/{value}/fd'):
                try: target = p.link(fd)
                except FileNotFoundError: continue  # Descriptor closed during observation.
                match = re.fullmatch(r'socket:\[(\d+)\]', target)
                if match: inodes.add(match[1])
        self.stage = 'listeners'; listeners = []
        for family in ('tcp', 'tcp6'):
            for row in p.text('/proc/net/' + family).splitlines()[1:]:
                fields = row.split()
                if len(fields) < 10: raise ValueError()
                address, port = fields[1].split(':')
                if fields[3] == '0A' and int(port, 16) == 1433:
                    self.require(family == 'tcp' and address == '0100007F', 'NON_LOOPBACK_LISTENER')
                    self.require(fields[9] in inodes, 'LISTENER_NOT_SQL_SERVICE')
                    listeners.append(fields[9])
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


if __name__ == '__main__': raise SystemExit(main())
