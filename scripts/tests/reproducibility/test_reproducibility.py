"""Offline E14-B identity and enforcement fixtures, never downloads or AWS."""
import base64
import copy
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import re
import tarfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[3]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


INSTALL = load('install_tools', '.github/scripts/ci/install-tools.py')
SELECT = load('select_checks', '.github/scripts/ci/select-checks.py')
DOC = json.loads(INSTALL.MANIFEST.read_text())
LAYERS = ('shared', 'secrets', 'global', 'data', 'platform', 'apps', 'edge')
AWS_ONLY_DEV = ('shared', 'global', 'data', 'platform', 'apps', 'edge')


RUNTIME_WINDOWS_LAYERS = ('global','data','platform','apps','edge')
WINDOWS_H1 = 'h1:H3mU/7URhP0uCRGK8jeQRKxx2XFzEqLiOq/L2Bbiaxs='
ORIGIN_RECEIPT = 'operations/sql-backup/recovery/provider-origin-verification.json'
ORIGIN_RECEIPT_SHA256 = 'c1f2da389f1954de8cb2e9b06a9c456055bba7653b89a14f3383aecf164ad3e4'
SENTINEL_LOCK = 'terraform/infra/sentinel-backup/.terraform.lock.hcl'
SENTINEL_LOCK_SHA256 = 'be1182b2f765f01c210a0d1327471dd5cd3cc316acd9f11edb8c959888b5fe3d'


def reviewed_windows_origin(raw):
    if hashlib.sha256(raw.replace(b'\r\n',b'\n')).hexdigest()!=ORIGIN_RECEIPT_SHA256:
        raise ValueError('Reviewed Windows origin receipt drift')
    # This exact receipt records independent official signature/ZIP/h1 verification.
    # Reading a mutable cache or generating a checksum here cannot replace it.
    return WINDOWS_H1


def aws_lock_identity(dev, prod, layer, origin):
    if layer in RUNTIME_WINDOWS_LAYERS:
        value=reviewed_windows_origin(origin)
        line='    "'+value+'",\n'
        if dev.count(line)!=1 or value in prod:
            raise ValueError('Exact reviewed DEV-only platform delta required')
        dev=dev.replace(line,'',1)
    if dev!=prod:raise ValueError('Unreviewed AWS lock content/version/hash drift')


def reviewed_sentinel_lock(raw):
    # Separate6.27 root: exact reviewed source, not inherited5.100/Linux qualification.
    if hashlib.sha256(raw.replace(b'\r\n',b'\n')).hexdigest()!=SENTINEL_LOCK_SHA256:
        raise ValueError('Separate Sentinel lock drift')


def references(text):
    return re.findall(r'(?:uses:|"uses":)\s*["\']?([^\s"\',]+)', text)


class ReproducibilityTests(unittest.TestCase):
    def test_manifest_exact_versions_and_provenance(self):
        INSTALL.validate(DOC)

    def test_floating_version_rejected(self):
        for value in ('latest', 'stable', '0.x', '>=1.0.0'):
            bad = copy.deepcopy(DOC)
            bad['tools']['terragrunt']['version'] = value
            with self.assertRaises(ValueError): INSTALL.validate(bad)

    def test_unverified_checksum_rejected(self):
        for field, value in (('sha256', '0' * 64), ('sha256', 'invented'), ('verification', 'UNVERIFIED')):
            bad = copy.deepcopy(DOC); bad['tools']['terraform'][field] = value
            with self.assertRaises(ValueError): INSTALL.validate(bad)

    def test_wrong_upstream_or_version_rejected(self):
        for url in ('https://evil.example/1.13.4', 'https://releases.hashicorp.com/terraform/1.13.3/file',
                    'https://github.com/evil/terraform/1.13.4', 'https://github.com/gruntwork-io/terragrunt/releases/latest/1.13.4'):
            bad = copy.deepcopy(DOC); bad['tools']['terraform']['url'] = url
            with self.assertRaises(ValueError): INSTALL.validate(bad)

    def test_deferred_action_cannot_be_certified(self):
        bad = copy.deepcopy(DOC)
        bad['deferred_actions']['dorny/paths-filter@v4']['status'] = 'VERIFIED'
        with self.assertRaises(ValueError): INSTALL.validate(bad)

    def test_action_tag_cannot_be_installed_as_verified(self):
        bad = copy.deepcopy(DOC); bad['actions']['actions/checkout@v6'] = 'v6'
        with self.assertRaises(ValueError): INSTALL.validate(bad)

    def test_wrong_platform_member_or_checksum_source_rejected(self):
        for field, value in (('url', DOC['tools']['terraform']['url'].replace('linux_amd64', 'windows_amd64')),
                             ('member', 'unrelated'), ('verification', 'UPSTREAM_RELEASE_ASSET_DIGEST'),
                             ('evidence_url', DOC['tools']['terraform']['evidence_url'] + '.unrelated')):
            bad = copy.deepcopy(DOC); bad['tools']['terraform'][field] = value
            with self.assertRaises(ValueError): INSTALL.validate(bad)

    def test_updates_can_select_reviewed_exact_versions(self):
        changed = copy.deepcopy(DOC)
        item = changed['tools']['terraform']; item['version'] = '1.13.5'
        for key in ('url', 'evidence_url'): item[key] = item[key].replace('1.13.4', '1.13.5')
        # This is only a grammar fixture, never a claim the retained hash verifies
        # the new upstream release. Real updates require upstream evidence.
        INSTALL.validate(changed)

    def test_checksum_before_archive_interpretation(self):
        with self.assertRaisesRegex(ValueError, 'checksum mismatch'):
            INSTALL.verified_binary(b'not a zip', DOC['tools']['terraform'])

    def test_exact_zip_member_and_ignored_traversal(self):
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, 'w') as archive:
            archive.writestr('terraform', b'fixture')
            archive.writestr('../untrusted', b'unused')
        raw = stream.getvalue()
        item = dict(DOC['tools']['terraform'], sha256=hashlib.sha256(raw).hexdigest())
        self.assertEqual(INSTALL.verified_binary(raw, item), b'fixture')
        item['member'] = 'missing'
        with self.assertRaises(ValueError): INSTALL.verified_binary(raw, item)

    def test_tar_link_rejected(self):
        stream = io.BytesIO()
        with tarfile.open(fileobj=stream, mode='w:gz') as archive:
            member = tarfile.TarInfo('tfsec'); member.type = tarfile.SYMTYPE; member.linkname = '/etc/passwd'
            archive.addfile(member)
        raw = stream.getvalue()
        item = dict(DOC['tools']['tfsec'], sha256=hashlib.sha256(raw).hexdigest())
        with self.assertRaisesRegex(ValueError, 'regular file'): INSTALL.verified_binary(raw, item)

    def test_all_active_actions_recorded_or_explicitly_deferred(self):
        found = set()
        authority=json.loads((ROOT/'terraform/infra/security/authority.json').read_text())
        # These immutable same-repository entries are governed by WP6 source
        # approval, not by an invented third-party release tag in toolchain.json.
        entries={'release':'e1-release','deploy-dev':'e1-dev-deploy'}
        approved={f"Kendall04/terragrunt_demo/.github/workflows/{entries[k]}.yml@{v['workflow_commit']}"
                  for k,v in authority['wp6']['approvals'].items() if k in entries}
        for path in (ROOT / '.github/workflows').glob('*.yml'):
            for reference in references(path.read_text()):
                if reference.startswith('./'): continue
                if reference.startswith('Kendall04/terragrunt_demo/.github/workflows/'):
                    self.assertIn(reference,approved);continue
                found.add(reference)
                self.assertTrue(reference in DOC['actions'] or reference in DOC['deferred_actions'], reference)
        self.assertEqual(found, set(DOC['actions']) | set(DOC['deferred_actions']))

    def test_active_ci_downloads_use_verifying_installer(self):
        for name, tools in {'ci-terragrunt.yml': 'terraform terragrunt tflint tfsec',
                            'ci-repo-hygiene.yml': 'actionlint shellcheck terraform terragrunt'}.items():
            text = (ROOT / '.github/workflows' / name).read_text()
            self.assertIn('install-tools.py ' + tools, text)
            self.assertNotRegex(text, r'releases/latest|go-version: stable|apt-get|curl -L|setup-tflint@')
        workflow = json.loads((ROOT / '.github/workflows/ci.yml').read_text())
        self.assertIn('install-tools.py terraform', workflow['jobs']['e1-acceptance']['steps'][1]['run'])
        app = (ROOT / '.github/workflows/ci-dotnet.yml').read_text()
        self.assertRegex(app, r'Set up Docker Buildx\n\s+uses: [^\n]+\n\s+with:\n\s+version: v\d+\.\d+\.\d+\n')

    def test_authoritative_lock_presence_platform_hashes_and_versions(self):
        expected = {f'terraform/modules/target/{env}/{layer}/.terraform.lock.hcl'
                    for env in ('dev', 'prod') for layer in LAYERS}
        expected.add('terraform/infra/security/.terraform.lock.hcl')
        expected.add(SENTINEL_LOCK)
        actual = {path.relative_to(ROOT).as_posix() for path in (ROOT / 'terraform').rglob('.terraform.lock.hcl')}
        self.assertEqual(actual, expected)
        for name in sorted(expected):
            if name==SENTINEL_LOCK:
                reviewed_sentinel_lock((ROOT/name).read_bytes())
                continue # Exact separate root; its Windows/schema proof is not Linux init.
            text = (ROOT / name).read_text()
            blocks = re.findall(r'provider "registry.terraform.io/hashicorp/(\w+)" \{([^}]+)\}', text)
            aws_only = name == 'terraform/infra/security/.terraform.lock.hcl' or name in {
                f'terraform/modules/target/dev/{layer}/.terraform.lock.hcl' for layer in AWS_ONLY_DEV}
            self.assertEqual({provider for provider, _ in blocks}, {'aws'} if aws_only else {'aws', 'tls'})
            for provider, block in blocks:
                evidence = DOC['provider_platforms'][provider]
                self.assertEqual(re.search(r'version\s*=\s*"([^"]+)"', block)[1], evidence['version'])
                self.assertIn('/' + evidence['version'] + '/', evidence['evidence_url'])
                for platform in ('linux_amd64', 'windows_amd64'):
                    self.assertIn('"zh:' + evidence[platform] + '"', block)
                for value in re.findall(r'"h1:([^"]+)"', block):
                    self.assertEqual(len(base64.b64decode(value, validate=True)), 32)
                for value in re.findall(r'"zh:([^"]+)"', block):
                    self.assertRegex(value, r'^[0-9a-f]{64}$')

    def test_dev_prod_aws_lock_identity_and_explicit_dev_provider_selection(self):
        for layer in LAYERS:
            paths = [ROOT / f'terraform/modules/target/{env}/{layer}' for env in ('dev', 'prod')]
            locks = [dict(re.findall(r'provider "registry.terraform.io/hashicorp/(\w+)" \{([^}]+)\}',
                                    (path / '.terraform.lock.hcl').read_text())) for path in paths]
            # Preserve byte equality except the one independently authenticated Windows h1.
            aws_lock_identity(locks[0]['aws'],locks[1]['aws'],layer,(ROOT/ORIGIN_RECEIPT).read_bytes())
            if layer in AWS_ONLY_DEV:
                self.assertEqual(set(locks[0]), {'aws'})
                self.assertEqual(set(locks[1]), {'aws', 'tls'})
                declaration = (paths[0] / 'ordinary-versions.tf').read_text()
                self.assertIn('required_providers {', declaration)
                providers = set(re.findall(r'(\w+)\s*=\s*\{\s*source\s*=', declaration))
                for config in paths[0].glob('*.tf.json'):
                    providers.update(json.loads(config.read_text()).get('terraform', {}).get('required_providers', {}))
                self.assertEqual(providers, {'aws'})
            else:
                self.assertEqual(locks[0], locks[1])

    def aws_blocks(self):
        result=[]
        for env in ('dev','prod'):
            text=(ROOT/f'terraform/modules/target/{env}/global/.terraform.lock.hcl').read_text()
            result.append(dict(re.findall(r'provider "registry.terraform.io/hashicorp/(\w+)" \{([^}]+)\}',text))['aws'])
        return result

    def test_platform_delta_cannot_hide_other_hash_version_or_constraint_changes(self):
        dev,prod=self.aws_blocks();origin=(ROOT/ORIGIN_RECEIPT).read_bytes()
        for mutated in (dev.replace('5.100.0','5.100.1'),dev.replace('~> 5.50','~> 6.0'),
                        dev.replace('zh:054b8d','zh:154b8d'),dev+'    "h1:'+('A'*43)+'=",\n'):
            with self.subTest(content=mutated[:24]),self.assertRaises(ValueError):
                aws_lock_identity(mutated,prod,'global',origin)

    def test_platform_delta_requires_exact_unchanged_authenticated_receipt(self):
        dev,prod=self.aws_blocks();origin=(ROOT/ORIGIN_RECEIPT).read_bytes()
        for raw in (b'{}',origin+b' ',origin.replace(b'OFFICIAL_SIGNED_ZIP_AND_H1_VERIFIED',b'CACHE_MATCH_ONLY')):
            with self.assertRaisesRegex(ValueError,'receipt drift'):aws_lock_identity(dev,prod,'global',raw)
        with self.assertRaises(ValueError):aws_lock_identity(dev,prod,'shared',origin)
        with self.assertRaises(ValueError):aws_lock_identity(prod,prod,'global',origin)
        with self.assertRaises(ValueError):aws_lock_identity(dev,dev,'global',origin)

    def test_separate_sentinel_lock_never_admits_a_provider_upgrade_or_extra_hash(self):
        raw=(ROOT/SENTINEL_LOCK).read_bytes()
        reviewed_sentinel_lock(raw)
        for modified in (raw.replace(b'6.27.0',b'6.28.0'),raw+b'\n# unreviewed\n'):
            with self.assertRaisesRegex(ValueError,'Sentinel lock drift'):reviewed_sentinel_lock(modified)

    def test_new_toolchain_inputs_select_all_e11_gates(self):
        for path in ('.github/scripts/ci/install-tools.py', '.github/scripts/ci/toolchain.json', 'global.json'):
            result = SELECT.classify([path])
            self.assertTrue(all(result[gate] for gate in SELECT.GATES), path)
        for path in ('scripts/tests/reproducibility/test_reproducibility.py', 'terraform/infra/security/.terraform.lock.hcl'):
            result = SELECT.classify([path]); self.assertTrue(result['acceptance'] and result['hygiene'])
        self.assertIn('scripts/tests/reproducibility', (ROOT / '.github/workflows/ci-repo-hygiene.yml').read_text())
        inventory = json.loads((ROOT / 'ci/authority/source-inventory.json').read_text())['sources']
        for name in ('global.json', '.github/scripts/ci/install-tools.py', '.github/scripts/ci/toolchain.json'):
            self.assertIn(name, inventory)

    def test_required_e11_and_e1_execution_preserved(self):
        workflow = json.loads((ROOT / '.github/workflows/ci.yml').read_text())
        jobs = workflow['jobs']
        self.assertEqual(workflow['permissions'], {'contents': 'read'})
        for name in ('e1-acceptance', 'repo-hygiene', 'app-ci', 'infra-static'):
            self.assertIn("needs.detect-changes.result != 'success'", jobs[name]['if'])
            self.assertIn("!= 'false'", jobs[name]['if'])
        self.assertIn('final_acceptance/gate.py', str(jobs['e1-acceptance']))
        self.assertIn('--verify', str(jobs))
        static = (ROOT / '.github/workflows/ci-terragrunt.yml').read_text()
        self.assertIn('default: true', static); self.assertIn('if: inputs.run_acceptance', static)
        for name in ('ci-terragrunt.yml', 'ci-repo-hygiene.yml', 'ci-dotnet.yml', 'ci-cd-safety.yml'):
            self.assertNotIn('id-token:', (ROOT / '.github/workflows' / name).read_text())

    def test_supported_host_sdk_matches_e14a(self):
        sdk = json.loads((ROOT / 'global.json').read_text())['sdk']
        images = json.loads((ROOT / 'demo-api/container-base-images.json').read_text())
        self.assertEqual(sdk['version'], images['bases']['build']['sdkVersion'])
        self.assertEqual(sdk['rollForward'], 'disable'); self.assertIs(sdk['allowPrerelease'], False)
        self.assertIn('default: "' + sdk['version'] + '"', (ROOT / '.github/workflows/ci-dotnet.yml').read_text())
        docker = (ROOT / 'demo-api/Dockerfile').read_text()
        for name in ('base', 'build'):
            self.assertIn(images['bases'][name]['tag'] + '@' + images['bases'][name]['manifestDigest'], docker)
        self.assertEqual(docker.count('USER $APP_UID'), 2)

    def test_protected_packages_and_image_gates_remain_inactive(self):
        authority = json.loads((ROOT / 'terraform/infra/security/authority.json').read_text())
        import sys
        sys.path[:0]=[str(ROOT),str(ROOT/'scripts/tests/security_root'),str(ROOT/'scripts/tests/authority')]
        import wp6
        self.assertEqual(authority['wp6']['approvals'], wp6.dev_trial_approvals(authority))
        for name in ('wp4d', 'wp5', 'internal_release'):
            self.assertEqual(authority[name]['installations'], {})
            self.assertEqual(authority[name]['runtime_approvals'], {})
        for name in ('Controller.Dockerfile', 'Worker.Dockerfile'):
            text = (ROOT / 'scripts/internal_release' / name).read_text()
            self.assertIn('ARG BASE', text); self.assertIn('FROM ${BASE}', text)
            self.assertNotRegex(text, r'pip install|curl|wget|apt-get')
        runtime = (ROOT / 'scripts/lifecycle/runtime.py').read_text()
        self.assertIn("'-lockfile=readonly'", runtime)
        self.assertIn('/opt/e1/provider-mirror', runtime)
        readback = (ROOT / 'scripts/lifecycle/packages.py').read_text()
        self.assertIn("VersionId=version", readback); self.assertIn("c.digest(raw) == reference['sha256']", readback)


if __name__ == '__main__': unittest.main()
