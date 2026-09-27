"""Fixed invocation of accepted E3, through an installed bounded process port.

No default process runner or SDK. WP4D supplies the protected runtime. The runner
must execute argv directly (never a shell string), enforce the wall-clock budget,
kill descendants and return bounded stdout. It cannot load caller programs.
"""
from abc import ABC, abstractmethod
from scripts.normal_delivery import authorization as a


class Process(ABC):
    @abstractmethod
    def execute(self, argv, timeout): raise NotImplementedError


class Gate:
    def __init__(self, process):
        a.require(isinstance(process, Process))
        self.process = process

    def run(self, context, now):
        remaining = context['deadline'] - now
        a.require(0 < remaining <= 1800)
        values = {
            'region': context['region'], 'cluster': context['cluster'],
            'service': context['service'], 'task-definition-arn': context['revision'],
            'image-uri': context['image'], 'app-container': context['app'],
            'probe-container': context['probe'], 'target-group-arn': context['target'],
            'listener-arn': context['listener'], 'candidate-rule-arn': context['rule'],
            'active-target-group-arn': context['active_target'],
            'desired-count': context['replicas'], 'attempt-start-epoch': context['started'],
            'deadline-epoch': context['deadline'], 'poll-interval': 5, 'stable-observations': 2}
        identity = a.sha(a.canonical(context))
        argv = ['python3', str(a.ROOT/'scripts/bounded-process.py'), str(remaining),
                'bash', str(a.ROOT/'scripts/normal_delivery/e3-evidence.sh'), identity]
        for key, value in values.items(): argv.extend(['--' + key, str(value)])
        argv.append('--use-instance-role')
        result = self.process.execute(argv, remaining)
        a.keys(result, ('exit_code', 'stdout'))
        a.require(type(result['exit_code']) is int and result['exit_code'] == 0)
        a.require(type(result['stdout']) is bytes and len(result['stdout']) <= 1048576)
        lines = result['stdout'].splitlines()
        a.require(bool(lines))
        evidence = a.decode(lines[-1])
        a.keys(evidence, ('schema', 'context_sha256', 'cohort', 'fingerprint'))
        a.require(evidence['schema'] == 'E1_E3_OBSERVATION_V1')
        a.exact(evidence['context_sha256'], identity, 'e3.context')
        a.exact(evidence['cohort'], context['cohort'], 'e3.cohort')
        a.match(r'[0-9a-f]{64}', evidence['fingerprint'])
        return dict(context=context, observation=evidence,
                    transcript_sha256=a.sha(result['stdout']))
