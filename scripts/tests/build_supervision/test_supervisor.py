"""Offline protected ports; payload doubles receive no control/store capability."""
import base64
import copy
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT / 'scripts/build_supervision'), str(ROOT / 'scripts/qualification'),
               str(ROOT / 'scripts/tests/security_root')]
import supervisor as s
import finalizer as f
import bundles

OP = '11111111-1111-1111-1111-111111111111'
BUILD = 'e1-controller-release:22222222-2222-2222-2222-222222222222'
CANARY = 'WP3B_SECRET_CANARY_NOT_FOR_PAYLOAD'
SECRETS = ('AWS_ACCESS_KEY_ID', 'AWS_SECRET_ACCESS_KEY', 'AWS_SESSION_TOKEN', 'AWS_PROFILE',
           'AWS_WEB_IDENTITY_TOKEN_FILE', 'AWS_ROLE_ARN', 'GITHUB_TOKEN', 'ACTIONS_ID_TOKEN_REQUEST_TOKEN',
           'SUPERVISOR_PUBLICATION_SECRET', 'CONTROLLER_PRIVATE_SECRET')


def fixture(module):
    context = dict(operation_id=OP, project='e1-controller-release', build_id=BUILD,
                   source_commit='a' * 40, account='111122223333', region='us-east-1',
                   repository='Kendall04/terragrunt_demo', github_run_id='42', github_run_attempt='1',
                   created_at='2026-09-25T00:00:00Z', controller_image={
                       'owner': 'SECURITY_ROOT_OWNED', 'binding': 'build/release', 'approval': 'ADMIN_VERIFIED',
                       'uri': '111122223333.dkr.ecr.us-east-1.amazonaws.com/e1-controller-build@sha256:' + 'c' * 64})
    class Control(module.Control):
        def __init__(self):
            self.op = {k: context[k] for k in module.CONTEXT_KEYS}
            self.op.update(schema='E1_RELEASE_OPERATION_V1', writer='RELEASE_GATEWAY')
        def operation(self, identity):
            assert identity == OP
            return copy.deepcopy(self.op)
    class Payload(module.Payload):
        def __init__(self):
            self.calls = []; self.states = {}; self.source_change = {}; self.error = None
            self.environments = []; self.artifacts = []; self.claim = 'PASS qualified=true sha256:' + 'd' * 64
            self.mutate = lambda stage, root: None
            self.image_files = None
            self.files = {'Dockerfile': b'COPY terragrunt-demo/ terragrunt-demo/\n',
                '.dockerignore': b'**/bin\n**/obj\n', 'terragrunt-demo.sln': b'approved solution',
                'terragrunt-demo/terragrunt-demo.csproj': b'approved project',
                'terragrunt-demo/Program.cs': b'approved application',
                'terragrunt-demo/ReadinessProbe.cs': b'approved probe'}
        def acquire(self, repository, commit, workspace):
            self.calls.append(('source', repository, commit, workspace))
            if self.error == 'source': raise OSError(CANARY)
            for name, raw in self.files.items():
                path = Path(workspace) / 'demo-api' / name
                path.parent.mkdir(parents=True, exist_ok=True);path.write_bytes(raw)
            self.mutate('source', Path(workspace))
            return dict(repository=repository, commit=commit, workspace=workspace, **{}) | self.source_change
        def outcome(self, stage):
            if self.error == stage: raise OSError(CANARY)
            return self.states.get(stage, {'stage': stage, 'state': 'COMPLETED',
                'exit_code': 1 if stage == 'probe_no_server' else 0, 'capability': True}).copy()
        def inspect_environment(self, env):
            # Hostile process double enumerates, reads names, echoes and persists
            # the entire supplied environment. It never receives supervisor os.environ.
            self.environments.append(dict(env))
            self.artifacts.append(json.dumps(dict(env)) + ''.join(env.get(k, '') for k in SECRETS))
        def execute(self, stage, argv, workspace, env, image):
            self.calls.append((stage, argv, workspace, image));self.inspect_environment(env)
            self.mutate(stage, Path(workspace))
            return self.outcome(stage)
        def image_build(self, workspace, context, dockerfile, env):
            self.calls.append(('image_build', workspace, context, dockerfile));self.inspect_environment(env)
            self.image_files = {p.relative_to(Path(context)).as_posix(): p.read_bytes()
                                for p in Path(context).rglob('*') if p.is_file()}
            return {'outcome': self.outcome('image_build'), 'handle': 'sealed-build-image'}
    class Images(module.Images):
        def __init__(self): self.calls = [];self.change = {};self.error = False
        def publish(self, attempt, handle, registry, repository):
            self.calls.append((attempt, handle, registry, repository))
            if self.error: raise OSError(CANARY)
            return dict(attempt=attempt, handle=handle, registry=registry, repository=repository,
                        digest='sha256:' + 'b' * 64) | self.change
    class Manifests(module.Manifests):
        def __init__(self):
            self.raw = None;self.receipt = None;self.change = {};self.read_change = {};self.error = None;self.calls = []
        def create(self, attempt, bucket, key, raw):
            self.calls.append(('create', attempt, bucket, key))
            if self.error == 'write': raise OSError(CANARY)
            if self.raw is not None and self.raw != raw: raise FileExistsError()
            self.raw = raw
            self.receipt = dict(bucket=bucket, key=key, version_id='fixture-returned-version-A') | self.change
            return self.receipt.copy()
        def read_exact(self, bucket, key, version_id):
            self.calls.append(('read', bucket, key, version_id))
            if self.error == 'read': raise OSError(CANARY)
            return dict(self.receipt, bytes=self.raw, sha256=f.checksum(self.raw)) | self.read_change
    class Records(module.Records):
        def __init__(self): self.values = {};self.fail_result = False;self.fail_terminal = False;self.noop = False;self.ambiguous = False;self.calls = []
        def create(self, attempt, raw):
            self.calls.append(('create', attempt, raw))
            record = json.loads(raw)
            terminal = record['schema'] == 'E1_BUILD_ATTEMPT_TERMINAL_V1'
            if (terminal and self.fail_terminal) or (not terminal and self.fail_result): raise OSError(CANARY)
            if attempt in self.values: raise FileExistsError()
            if not self.noop: self.values[attempt] = raw
            if self.ambiguous: raise OSError(CANARY)
        def read(self, attempt): return self.values.get(attempt)
    return context, Control(), Payload(), Images(), Manifests(), Records()


class Behavior(AssertionError):
    pass


class Tests(unittest.TestCase):
    module = s
    def setUp(self):
        self.context, self.control, self.payload, self.images, self.manifests, self.records = fixture(self.module)
        self.core = self.module.Supervisor(self.context, self.control, self.payload, self.images, self.manifests, self.records)
        self.invoked = 0
    def run_core(self, wakeup=None):
        self.invoked += 1
        return self.core.run({'operation_id': OP} if wakeup is None else wakeup)
    def expect(self, condition):
        if not condition: raise Behavior('Reached WP3B behavioral invariant failed')
    def rejected(self, wakeup):
        try: self.run_core(wakeup)
        except (self.module.Rejected, f.Rejected): return
        raise Behavior('Expected boundary rejection')
    def terminal(self, stage):
        record = self.run_core()
        self.expect(record['schema'] == 'E1_BUILD_ATTEMPT_TERMINAL_V1' and record['terminal_stage'] == stage)
        self.expect(not set(record) & {'image_digest', 'manifest', 'release_id', 'qualified'})
        self.module.validate_terminal(record)
        self.expect(set(record['checks']) == set(f.REQUIRED_CHECKS))
        with self.assertRaises(f.Rejected): f.validate('result', record)
        return record
    def test_positive_fixed_pipeline(self):
        try:r = self.run_core()
        except (self.module.Rejected,f.Rejected):raise Behavior('Valid fixed pipeline rejected') from None
        self.expect(r['state'] == 'SUCCEEDED')
        self.expect(r['checks'] == dict.fromkeys(f.REQUIRED_CHECKS, 'PASS'))
        self.expect([c[0] for c in self.payload.calls] == ['source', 'dotnet_restore', 'dotnet_build', 'dotnet_test', 'image_build', 'probe_capability', 'probe_no_server'])
        expected = (
            ('dotnet', 'restore', './demo-api/terragrunt-demo.sln'),
            ('dotnet', 'build', './demo-api/terragrunt-demo.sln', '--configuration', 'Release', '--no-restore'),
            ('dotnet', 'test', './demo-api/terragrunt-demo.sln', '--configuration', 'Release', '--no-build', '--verbosity', 'normal'))
        self.expect(tuple(c[1] for c in self.payload.calls[1:4]) == expected)
        self.expect(f.validate('result', r) == r)
    def test_closed_environment(self):
        with patch.dict(os.environ, {k: CANARY for k in SECRETS} | {'ARBITRARY_NEW_SECRET': CANARY}):
            r = self.run_core()
        self.expect(all(not set(e) & set(SECRETS) for e in self.payload.environments))
        self.expect(CANARY not in json.dumps(self.payload.artifacts) + json.dumps(r))
        self.expect(all(set(e) <= {'PATH','HOME','DOTNET_CLI_HOME','NUGET_PACKAGES','DOTNET_NOLOGO','DOTNET_CLI_TELEMETRY_OPTOUT','AWS_EC2_METADATA_DISABLED','READINESS_PROBE_TIMEOUT_SECONDS','READINESS_PROBE_REQUEST_TIMEOUT_SECONDS','READINESS_PROBE_INTERVAL_SECONDS'} for e in self.payload.environments))
    def test_source_failure(self):
        self.payload.error = 'source';r = self.terminal('source')
        self.expect(r['observed_source_commit'] is None and r['source_commit'] == 'a' * 40)
        self.expect(set(r['checks'].values()) == {'NOT_RUN'})
    def test_source_mismatch(self):
        self.payload.source_change['commit'] = 'd' * 40
        try:r = self.run_core()
        except (self.module.Rejected, f.Rejected):
            self.expect([c[0] for c in self.payload.calls] == ['source'])
            return
        self.expect(r['schema'] == 'E1_BUILD_ATTEMPT_TERMINAL_V1' and r['terminal_stage'] == 'source')
        self.expect(r['observed_source_commit'] is None and [c[0] for c in self.payload.calls] == ['source'])
    def test_source_repository(self):
        self.payload.source_change['repository'] = 'attacker/repo';self.terminal('source')
    def test_workspace_outside(self):
        self.payload.source_change['workspace'] = '/outside';self.terminal('source')
    def test_restore_failure(self):
        self.payload.states['dotnet_restore'] = dict(stage='dotnet_restore',state='COMPLETED',exit_code=1,capability=False)
        r = self.terminal('dotnet_restore')
        self.expect(r['checks']['dotnet_restore'] == 'FAIL' and all(r['checks'][k] == 'NOT_RUN' for k in f.REQUIRED_CHECKS[1:]))
        self.expect(self.images.calls == [] and self.manifests.raw is None)
    def test_image_context(self):
        self.run_core();c = next(x for x in self.payload.calls if x[0] == 'image_build')
        w = self.payload.calls[1][2];protected = (Path(w).parent / 'image').as_posix()
        self.expect(c[1:] == (protected, protected + '/demo-api', protected + '/demo-api/Dockerfile'))
        self.expect(self.payload.calls[0][3] != w != protected)
    def test_publisher_destination(self):
        self.run_core();self.expect(self.images.calls[0][2:] == ('111122223333.dkr.ecr.us-east-1.amazonaws.com','demo-shared-demo-ms'))
    def test_digest_from_trusted_publisher(self):
        self.payload.claim = 'sha256:' + 'd' * 64
        r = self.run_core();self.expect(r['image_digest'] == 'sha256:' + 'b' * 64)
    def test_tag_only(self):
        self.images.change['digest'] = 'latest';self.terminal('image_publish')
    def test_image_repository(self):
        self.images.change['repository'] = 'attacker';self.terminal('image_publish')
    def test_image_publish_failure(self):
        self.images.error = True;self.terminal('image_publish')
    def test_exact_probe_image(self):
        r = self.run_core();uri = '111122223333.dkr.ecr.us-east-1.amazonaws.com/demo-shared-demo-ms@' + r['image_digest']
        self.expect(all(c[3] == uri for c in self.payload.calls if c[0].startswith('probe_')))
    def test_manifest_generated(self):
        self.payload.claim = '{"gitSha":"attacker","quality":{"dotnetTests":"passed"}}'
        self.run_core();r = json.loads(self.manifests.raw)
        self.expect(r['gitSha'] == 'a' * 40 and r['image']['digest'] == 'sha256:' + 'b' * 64)
        self.expect('attacker' not in self.manifests.raw.decode())
    def test_manifest_exact_receipt(self):
        r = self.run_core();self.expect(r['manifest']['version_id'] == 'fixture-returned-version-A')
        self.expect(self.manifests.calls[-1] == ('read',r['manifest']['bucket'],r['manifest']['key'],r['manifest']['version_id']))
        self.expect(r['manifest']['sha256'] == f.checksum(self.manifests.raw))
    def test_manifest_write_failure(self):
        self.manifests.error = 'write';self.terminal('manifest_publish')
    def test_manifest_read_failure(self):
        self.manifests.error = 'read';self.terminal('manifest_readback')
    def test_manifest_changed_bytes(self):
        self.manifests.read_change['bytes'] = b'wrong';self.terminal('manifest_readback')
    def test_manifest_checksum(self):
        self.manifests.read_change['sha256'] = '0' * 64;self.terminal('manifest_readback')
    def test_manifest_wrong_version(self):
        self.manifests.read_change['version_id'] = 'other';self.terminal('manifest_readback')
    def test_manifest_null_version(self):
        self.manifests.change['version_id'] = None;self.terminal('manifest_publish')
    def test_late_probe_failure(self):
        self.payload.states['probe_capability'] = dict(stage='probe_capability',state='COMPLETED',exit_code=1,capability=False)
        r = self.run_core();self.expect(r['schema'] == 'E1_SUPERVISED_RESULT_V1' and r['state'] == 'FAILED')
        self.expect(r['checks']['probe_capability'] == 'FAIL' and r['checks']['probe_no_server'] == 'NOT_RUN')
        self.expect(f.validate('result',r) == r)
        self.finalize(r, False)
    def test_result_publication_failure(self):
        self.records.fail_result = True;r = self.terminal('result_publish')
        self.expect(r['state'] == 'FAILED')
    def test_terminal_publication_failure(self):
        self.payload.error = 'source';self.records.fail_terminal = True
        self.rejected({'operation_id': OP});self.expect(self.records.values == {})
    def test_noop_publication(self):
        self.records.noop = True;self.rejected({'operation_id': OP})
    def test_exact_retry(self):
        first = self.run_core();calls = len(self.payload.calls)
        self.expect(self.run_core() == first and len(self.payload.calls) == calls and len(self.records.values) == 1)
    def test_terminal_retry(self):
        self.payload.error = 'source';first = self.run_core();self.payload.error = None
        self.expect(self.run_core() == first and len(self.payload.calls) == 1)
    def test_conflict(self):
        self.records.values[OP + '/' + BUILD] = b'conflict';self.rejected({'operation_id':OP})
    def test_terminal_conflicting_create(self):
        self.payload.error = 'source';r = self.run_core();other = dict(r,terminal_stage='image_build')
        self.invoked += 1
        with self.assertRaises(self.module.Rejected):self.core.persist(OP + '/' + BUILD, other)
    def test_ambiguous_result_acknowledgement(self):
        self.records.ambiguous = True;r = self.run_core();self.expect(r['state'] == 'SUCCEEDED' and len(self.records.values) == 1)
    def test_application_writer(self):
        self.payload.claim = json.dumps({'writer':'BUILD_SUPERVISOR','schema':'E1_BUILD_ATTEMPT_TERMINAL_V1'})
        self.run_core();self.expect(len(self.records.values) == 1 and all(c[0] == 'create' for c in self.records.calls))
        self.expect(not hasattr(self.payload, 'records') and not hasattr(self.payload, 'create'))
        invalid = dict(self.control.op,schema='E1_BUILD_ATTEMPT_TERMINAL_V1',writer='APPLICATION',observed_source_commit=None,state='FAILED',terminal_stage='source',checks=dict.fromkeys(f.REQUIRED_CHECKS,'NOT_RUN'),classification='EXECUTION_OR_PUBLICATION_FAILED')
        try:self.module.validate_terminal(invalid)
        except (self.module.Rejected,f.Rejected):return
        raise Behavior('Application writer accepted')
    def test_terminal_not_qualification_evidence(self):
        self.payload.error = 'source';r = self.terminal('source');self.finalize(r,False)
    def test_success_compatibility(self):
        r = self.run_core();self.finalize(r,True)
    def finalize(self,r,success):
        control=self.control;manifests=self.manifests
        class Evidence(f.Evidence):
            def operation(self,_):return copy.deepcopy(control.op)
            def build(self,_):
                # Separate authoritative fixture, not copied from result checks.
                common={k:control.op[k] for k in s.CONTEXT_KEYS}
                return dict(common,schema='E1_BUILD_OBSERVATION_V1',state='SUCCEEDED',checks=dict.fromkeys(f.REQUIRED_CHECKS,'PASS'))
            def result(self,*_):return copy.deepcopy(r)
            def manifest(self,*_):return dict(manifests.receipt,bytes=manifests.raw)
        class Store(f.Qualifications):
            def __init__(self):self.values={}
            def create(self,k,v):self.values[k]=v
            def read(self,k):return self.values[k]
        store=Store();core=f.Finalizer('111122223333','us-east-1',Evidence(),store)
        if success:
            core.finalize({'operation_id':OP});self.expect(len(store.values)==1)
        else:
            try:core.finalize({'operation_id':OP})
            except f.Rejected:pass
            else:raise Behavior('Non-qualifying record produced qualification')
            self.expect(store.values=={})
    def test_controller_image_separate(self):
        self.run_core()
        for uri in ('latest','111122223333.dkr.ecr.us-east-1.amazonaws.com/demo-shared-demo-ms@sha256:'+'b'*64):
            value=dict(self.context['controller_image'],uri=uri)
            with self.assertRaises(self.module.Rejected):self.module.runtime_image(value,'111122223333','us-east-1')
    def test_diagnostic_redaction(self):
        self.payload.error='source';self.records.fail_terminal=True
        try:self.run_core()
        except self.module.Rejected as exc:self.expect(CANARY not in str(exc))
        else:raise Behavior('Expected publication rejection')
    def test_no_server_launch_failure_is_not_pass(self):
        self.payload.states['probe_no_server']=dict(stage='probe_no_server',state='COMPLETED',exit_code=2,capability=False)
        r=self.run_core();self.expect(r['checks']['probe_no_server']=='FAIL');self.finalize(r,False)
    def test_probe_outer_timeout_is_unknown(self):
        self.payload.error='probe_capability';r=self.run_core()
        self.expect(r['checks']['probe_capability']=='UNKNOWN' and r['checks']['probe_no_server']=='NOT_RUN')
    def test_source_branch_and_short_sha_rejected(self):
        for identity in ('develop','v1','a'*7):
            self.payload.source_change['commit']=identity;self.records.values.clear()
            self.terminal('source')
    def test_manifest_latest_receipt_rejected(self):
        self.manifests.change['version_id']='latest';self.terminal('manifest_publish')
    def test_manifest_wrong_path_rejected(self):
        self.manifests.change['key']='other/path';self.terminal('manifest_publish')
    def test_publication_receipt_wrong_attempt_rejected(self):
        self.images.change['attempt']='other';self.terminal('image_publish')
    def test_stage_output_cannot_report_another_stage(self):
        self.payload.states['dotnet_restore']=dict(stage='dotnet_test',state='COMPLETED',exit_code=0,capability=True)
        r=self.terminal('dotnet_restore');self.expect(r['checks']['dotnet_restore']=='UNKNOWN')
    def test_raw_output_is_not_an_observation(self):
        self.payload.states['dotnet_restore']={'stdout':'PASS qualified=true','stderr':CANARY}
        r=self.terminal('dotnet_restore');self.expect(r['checks']['dotnet_restore']=='UNKNOWN')
    def test_missing_check_terminal_rejected(self):
        self.payload.error='source';r=self.run_core();del r['checks']['dotnet_test']
        with self.assertRaises(f.Rejected):self.module.validate_terminal(r)
    def test_unverified_controller_image_rejected(self):
        self.run_core();value=dict(self.context['controller_image'],approval='UNVERIFIED')
        with self.assertRaises(self.module.Rejected):self.module.runtime_image(value,'111122223333','us-east-1')
    def test_package_determinism(self):
        authority=json.loads((ROOT/'terraform/infra/security/authority.json').read_text())
        for name in ('build','qualification-finalizer'):
            raw=bundles.artifact(ROOT,authority['control_bundles'],name)
            self.assertEqual(raw,bundles.artifact(ROOT,authority['control_bundles'],name))
            package=json.loads(raw);self.assertFalse(package['operational'])
            self.assertEqual(bundles.digest(raw),authority['control_bundles']['classes'][name]['sha256'])
            for path in bundles.EXECUTABLE_SOURCES[name]:
                self.assertEqual(base64.b64decode(package['files'][path]),(ROOT/path).read_bytes().replace(b'\r\n',b'\n'))
            self.assertNotIn(str(ROOT),raw.decode());self.assertNotIn(CANARY,raw.decode())
    def test_inactivity(self):
        d=json.loads((ROOT/'terraform/infra/security/authority.json').read_text());c=d['controller_compute']
        self.assertEqual(len(c['nodes']),18);self.assertFalse(c['operational']);self.assertFalse(c['creation_supported'])
        self.assertEqual(len(d['request_identities']),11)
        for p in [d['policies']['inert_trust'],d['policies']['inert_permissions'],*c['role_trust'].values()]:self.assertTrue(all(x['Effect']=='Deny' for x in p['Statement']))
        recovery=d['ownership_closure']['recovery'];self.assertEqual(len(recovery),8)
        self.assertTrue(all(not r['operational'] and not r['invocation_enabled'] for r in recovery.values()))

    def integrity_failure(self, stage):
        r = self.terminal(stage)
        self.expect(r['classification'] == 'SOURCE_INTEGRITY_VIOLATION')
        self.expect(not any(c[0] == 'image_build' for c in self.payload.calls))
        self.expect(not self.images.calls and self.manifests.raw is None)
        self.finalize(r, False)
        return r

    def test_generated_output_stays_out_of_image(self):
        def mutate(stage, root):
            if stage in ('dotnet_restore', 'dotnet_build', 'dotnet_test'):
                for name in ('terragrunt-demo/bin/generated.dll', 'terragrunt-demo/obj/cache',
                             'terragrunt-demo/malicious-extra-file', 'fake-manifest.json',
                             'fake-probe-helper', 'generated/Dockerfile'):
                    p = root / 'demo-api' / name
                    p.parent.mkdir(parents=True, exist_ok=True);p.write_bytes(b'unapproved')
        self.payload.mutate = mutate
        r = self.run_core()
        self.expect(r['state'] == 'SUCCEEDED' and self.payload.image_files == self.payload.files)
        self.expect(self.payload.calls[1][2] != next(c[1] for c in self.payload.calls if c[0] == 'image_build'))
        self.finalize(r, True)

    def test_protected_context_corruption(self):
        original = self.module.materialize_source
        def corrupt(nodes, destination):
            original(nodes, destination)
            if Path(destination).name == 'image':
                (Path(destination) / 'demo-api/Dockerfile').write_bytes(b'unapproved')
        with patch.object(self.module, 'materialize_source', corrupt):
            self.integrity_failure('image_context')

    def test_extra_image_context_input(self):
        original = self.module.materialize_source
        def corrupt(nodes, destination):
            original(nodes, destination)
            if Path(destination).name == 'image':
                (Path(destination) / 'demo-api/terragrunt-demo/extra.cs').write_bytes(b'unapproved')
        with patch.object(self.module, 'materialize_source', corrupt):
            self.integrity_failure('image_context')

    def test_symlink_initial_source(self):
        with tempfile.TemporaryDirectory(prefix='wp3b-outside-') as tmp:
            outside = Path(tmp) / 'outside';outside.write_bytes(b'unapproved')
            def mutate(stage, root):
                if stage == 'source':
                    p = root / 'demo-api/Dockerfile';p.unlink();p.symlink_to(outside)
            self.payload.mutate = mutate
            self.integrity_failure('source')

    def test_symlink_after_test(self):
        with tempfile.TemporaryDirectory(prefix='wp3b-outside-') as tmp:
            outside = Path(tmp) / 'outside';outside.write_bytes(b'unapproved')
            def mutate(stage, root):
                if stage == 'dotnet_test':
                    p = root / 'demo-api/Dockerfile';p.unlink();p.symlink_to(outside)
            self.payload.mutate = mutate
            self.integrity_failure('dotnet_test')

    def test_hardlink_after_test(self):
        with tempfile.TemporaryDirectory(prefix='wp3b-outside-') as tmp:
            outside = Path(tmp) / 'outside';outside.write_bytes(b'approved application')
            def mutate(stage, root):
                if stage == 'dotnet_test':
                    p = root / 'demo-api/terragrunt-demo/Program.cs';p.unlink();os.link(outside, p)
            self.payload.mutate = mutate
            self.integrity_failure('dotnet_test')

    def test_generated_initial_export_rejected(self):
        self.payload.files['terragrunt-demo/bin/generated.dll'] = b'unapproved'
        self.integrity_failure('source')

    def test_image_builder_mutation_stops_publication(self):
        original = self.payload.image_build
        def mutate(workspace, context, dockerfile, env):
            result = original(workspace, context, dockerfile, env)
            Path(dockerfile).write_bytes(b'unapproved')
            return result
        self.payload.image_build = mutate
        r = self.terminal('image_build')
        self.expect(r['classification'] == 'SOURCE_INTEGRITY_VIOLATION' and not self.images.calls)
        self.finalize(r, False)

    def test_deleted_source(self):
        def mutate(stage, root):
            if stage == 'dotnet_test':(root / 'demo-api/terragrunt-demo/Program.cs').unlink()
        self.payload.mutate = mutate
        self.integrity_failure('dotnet_test')

    def test_changed_source_node_type(self):
        def mutate(stage, root):
            if stage == 'dotnet_test':
                p = root / 'demo-api/terragrunt-demo/Program.cs';p.unlink();p.mkdir()
        self.payload.mutate = mutate
        self.integrity_failure('dotnet_test')

    def test_safe_path_grammar(self):
        self.invoked += 1
        for path in ('/demo-api/x', 'demo-api/../outside', 'demo-api/C:/outside',
                     'demo-api/a\\b', 'demo-api//x', 'demo-api/CON', 'demo-api/a.'):
            try:self.module.source_path(path)
            except self.module.SourceIntegrity:continue
            raise Behavior('Unsafe source path admitted')

    def test_snapshot_determinism(self):
        with tempfile.TemporaryDirectory(prefix='wp3b-seal-') as tmp:
            root = Path(tmp);acquired = root / 'acquired';acquired.mkdir()
            self.payload.acquire(self.context['repository'], self.context['source_commit'], str(acquired))
            nodes = self.module.source_tree(acquired)
            identity = self.module.source_seal(self.context['repository'], self.context['source_commit'], nodes)
            self.module.materialize_source(nodes, root / 'fresh')
            self.expect(self.module.source_seal(self.context['repository'], self.context['source_commit'],
                        self.module.source_tree(root / 'fresh')) == identity)
            self.expect(identity != self.module.source_seal(self.context['repository'], 'b'*40, nodes))

    def test_terminal_result_publication_after_probe_failure(self):
        self.payload.states['probe_capability'] = dict(stage='probe_capability', state='COMPLETED', exit_code=3, capability=False)
        self.records.fail_result = True
        r = self.terminal('result_publish')
        self.expect(r['checks']['probe_capability'] == 'FAIL' and r['checks']['probe_no_server'] == 'NOT_RUN')

    def test_terminal_contradictions(self):
        for stage, corrupt in [('source', 'dotnet_build'), ('dotnet_restore', 'dotnet_test'),
                               ('dotnet_build', 'image_build'), ('image_build', 'image_publish'),
                               ('image_publish', 'probe_capability'), ('manifest_publish', 'probe_capability'),
                               ('manifest_readback', 'probe_no_server'), ('image_context', 'image_build')]:
            self.setUp()
            if stage in ('source', 'dotnet_restore', 'dotnet_build', 'image_build'):self.payload.error = stage
            elif stage == 'image_publish':self.images.error = True
            elif stage == 'manifest_publish':self.manifests.error = 'write'
            elif stage == 'manifest_readback':self.manifests.error = 'read'
            else:
                with patch.object(self.module, 'materialize_source', side_effect=self.module.SourceIntegrity('bounded')):
                    r = self.run_core()
                # Construct the valid context-failure prefix from protected facts.
                r['observed_source_commit'] = r['source_commit'];r['terminal_stage'] = stage
                for k in ('dotnet_restore','dotnet_build','dotnet_test'):r['checks'][k] = 'PASS'
            if stage != 'image_context':r = self.run_core()
            self.module.validate_terminal(r)
            r['checks'][corrupt] = 'PASS'
            try:self.module.validate_terminal(r)
            except (self.module.Rejected, f.Rejected):continue
            raise Behavior('Contradictory terminal check prefix accepted')


def override(key):
    def test(self):self.rejected({'operation_id':OP,key:CANARY})
    return test
for key in ('repository','source_ref','source_commit','project','buildspec','commands','Dockerfile','context','image_repository','digest','probes','manifest','version_id','role','environment','output_path','writer'):
    setattr(Tests,'test_override_'+key.lower(),override(key))


def failure(stage,state):
    def test(self):
        self.payload.states[stage]=dict(stage=stage,state=state,exit_code=1 if state=='COMPLETED' else None,capability=False)
        if stage=='probe_no_server' and state=='COMPLETED':self.payload.states[stage]['exit_code']=0
        r=self.run_core()
        self.expect(r['checks'][stage]==('FAIL' if state=='COMPLETED' else state))
        index=list(f.REQUIRED_CHECKS).index(stage)
        self.expect(all(r['checks'][k]=='NOT_RUN' for k in f.REQUIRED_CHECKS[index+1:]))
        self.expect(r['schema']==('E1_SUPERVISED_RESULT_V1' if stage.startswith('probe_') else 'E1_BUILD_ATTEMPT_TERMINAL_V1'))
    return test
for stage in ('dotnet_restore','dotnet_build','dotnet_test','image_build','probe_capability','probe_no_server'):
    for state in ('COMPLETED','SKIPPED','NOT_RUN','UNKNOWN'):
        setattr(Tests,'test_failure_'+stage+'_'+state.lower(),failure(stage,state))


def source_mutation(stage, name):
    def test(self):
        def mutate(current, root):
            if current == stage:(root / 'demo-api' / name).write_bytes(b'unapproved mutation')
        self.payload.mutate = mutate
        self.integrity_failure(stage)
    return test
for stage in ('dotnet_restore', 'dotnet_build', 'dotnet_test'):
    for label, name in [('application', 'terragrunt-demo/Program.cs'), ('dockerfile', 'Dockerfile'),
                        ('project', 'terragrunt-demo/terragrunt-demo.csproj'),
                        ('probe', 'terragrunt-demo/ReadinessProbe.cs')]:
        setattr(Tests, 'test_integrity_' + stage + '_' + label, source_mutation(stage, name))
