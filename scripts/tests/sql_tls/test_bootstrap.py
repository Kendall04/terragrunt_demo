"""Deterministic shell-bootstrap regressions, not SQL/TLS handshake evidence.

Test-only PATH shims supply time/UID and stop at the dotnet boundary. They live
in a disposable directory, outside every Docker COPY. No clock override exists
in the deployable entrypoint or application. Real SQL uses run_local.py.
"""
import base64
import datetime as dt
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[3]
ENTRYPOINT = ROOT/'demo-api/deploy/sql-trust/entrypoint.sh'
CAP = '2026-12-04T20:09:56Z'


class Bootstrap(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix='sql-bootstrap-test-')
        cls.work = Path(cls.temp.name)
        cls.openssl = shutil.which('openssl')
        cls.date = shutil.which('date')
        if not cls.openssl or not cls.date or not shutil.which('jq'):
            raise RuntimeError('Linux/OpenSSL/jq required; no skipped security tests')
        cls.bin = cls.work/'bin'; cls.bin.mkdir()
        scripts = {
            'id': '#!/bin/sh\nprintf "1654\\n"\n',
            'date': '#!/bin/sh\nif [ "$*" = "-u +%s" ]; then printf "%s\\n" "$TEST_EPOCH"; else exec '+cls.date+' "$@"; fi\n',
            'openssl': '#!/bin/sh\nif [ "$1" = verify ]; then shift; exec '+cls.openssl+' verify -attime "$TEST_EPOCH" "$@"; else exec '+cls.openssl+' "$@"; fi\n',
            'dotnet': '#!/bin/sh\nprintf "TEST_DOTNET_BOUNDARY %s\\n" "$*"\n# Clean only the directory produced by this disposable test invocation.\ncase "$HOME" in /tmp/sql-trust.*/home) rm -rf -- "${HOME%/home}";; esac\n'
        }
        for name, text in scripts.items():
            p = cls.bin/name; p.write_text(text); p.chmod(0o755)
        cls.ca = cls.certificate('ca', 'Legitimate-root', 'CA:TRUE,pathlen:0', 'keyCertSign,cRLSign')
        cls.spoof = cls.certificate('spoof', 'CA:TRUE Certificate Sign', 'CA:FALSE', 'digitalSignature,keyEncipherment')
        cls.no_sign = cls.certificate('no-sign', 'Certificate Sign', 'CA:TRUE', 'digitalSignature')
        cls.no_constraints = cls.certificate('no-constraints', 'CA:TRUE Certificate Sign', None, 'keyCertSign')
        raw = subprocess.check_output([cls.openssl, 'x509', '-in', str(ROOT/'demo-api/deploy/trust/sql.demo.internal.crt'), '-outform', 'DER'])
        cls.leaf = cls.anchor(raw, 'dev-leaf-transition')

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    @staticmethod
    def anchor(raw, kind='ca'):
        return dict(kind=kind, sha256=hashlib.sha256(raw).hexdigest(), der_base64=base64.b64encode(raw).decode())

    @classmethod
    def certificate(cls, name, subject, constraints, usage):
        folder = cls.work/name; folder.mkdir()
        (folder/'index').write_text(''); (folder/'serial').write_text('01\n')
        config = '[ca]\ndefault_ca=issuer\n[issuer]\ndatabase='+str(folder/'index')+'\nserial='+str(folder/'serial')+'\nnew_certs_dir='+str(folder)+'\ndefault_md=sha256\npolicy=subject\nx509_extensions=extensions\n[subject]\ncommonName=supplied\n[extensions]\n'
        if constraints: config += 'basicConstraints=critical,'+constraints+'\n'
        if usage: config += 'keyUsage=critical,'+usage+'\n'
        (folder/'config').write_text(config)
        def command(*args):
            subprocess.run([cls.openssl,*args], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        command('req','-new','-newkey','rsa:2048','-nodes','-subj','/CN='+subject,'-keyout',str(folder/'key'),'-out',str(folder/'csr'))
        command('ca','-selfsign','-batch','-config',str(folder/'config'),'-keyfile',str(folder/'key'),'-in',str(folder/'csr'),'-out',str(folder/'crt'),'-startdate','261101000000Z','-enddate','271201000000Z')
        raw = subprocess.check_output([cls.openssl,'x509','-in',str(folder/'crt'),'-outform','DER'])
        return cls.anchor(raw)

    def invoke(self, *, anchor=None, env='prod', bridge=False, now=CAP, start='2026-12-03T20:09:56Z', end=CAP, leaf=None):
        trust = dict(schema='SQL_TLS_TRUST_V1',environment=env,hostname='sql.demo.internal',version='test-only',anchors=[anchor or self.ca])
        if bridge:
            trust['anchors'].append(leaf or self.leaf)
            trust['transition'] = dict(not_before=start,not_after=end)
        raw = json.dumps(trust).encode()
        settings = dict(PATH=str(self.bin)+':/usr/bin:/bin',HOME=str(self.work),
            TEST_EPOCH=str(int(dt.datetime.fromisoformat(now.replace('Z','+00:00')).timestamp())),
            APP_ENV=env,Database__SecurityProfile='validated-v2',Database__ExpectedCertificateHostName='sql.demo.internal',
            SQL_TRUST_MANIFEST_B64=base64.b64encode(raw).decode(),SQL_TRUST_MANIFEST_SHA256=hashlib.sha256(raw).hexdigest())
        return subprocess.run(['/bin/sh',str(ENTRYPOINT)],env=settings,text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)

    def assert_refused(self, result, code):
        self.assertEqual(result.returncode,78,result.stdout+result.stderr)
        self.assertIn(code,result.stderr)
        self.assertNotIn('SQL_TRUST_PREPARED',result.stdout)
        self.assertNotIn('TEST_DOTNET_BOUNDARY',result.stdout)

    def test_subject_cannot_impersonate_extensions(self):
        for cert in (self.spoof,self.no_sign,self.no_constraints,dict(self.leaf,kind='ca')):
            with self.subTest(anchor=cert['sha256']):
                self.assert_refused(self.invoke(anchor=cert),'SQL_TRUST_CA_REQUIRED')

    def test_real_ca_reaches_dotnet_boundary(self):
        result=self.invoke()
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertIn('TEST_DOTNET_BOUNDARY /app/terragrunt-demo.dll',result.stdout)

    def test_bridge_before_at_and_after_fixed_cap(self):
        result=self.invoke(env='dev',bridge=True,now='2026-12-04T20:09:55Z')
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertIn('TEST_DOTNET_BOUNDARY',result.stdout)
        for now in (CAP,'2026-12-04T20:09:57Z','2027-01-01T00:00:00Z'):
            with self.subTest(now=now):
                self.assert_refused(self.invoke(env='dev',bridge=True,now=now),'SQL_TRUST_TRANSITION_REFUSED')

    def test_bridge_requires_pin_environment_and_bounded_window(self):
        self.assert_refused(self.invoke(env='prod',bridge=True),'SQL_TRUST_SCHEMA_REFUSED')
        fake=dict(self.spoof,kind='dev-leaf-transition')
        self.assert_refused(self.invoke(env='dev',bridge=True,leaf=fake,now='2026-12-04T20:09:55Z'),'SQL_TRUST_LEAF_PIN_REFUSED')
        for start,end in (('2026-11-01T00:00:00Z',CAP),('2026-12-05T00:00:00Z',CAP),('2026-12-03T00:00:00Z','2026-12-05T00:00:00Z')):
            self.assert_refused(self.invoke(env='dev',bridge=True,now='2026-12-04T20:09:55Z',start=start,end=end),'SQL_TRUST_TRANSITION_REFUSED')

    def test_old_relative_window_exceeds_cap_even_just_before_expiry(self):
        # Reproduces the old harness's now+30 minutes without changing real time.
        self.assert_refused(self.invoke(env='dev',bridge=True,now='2026-12-04T20:09:55Z',
            start='2026-12-04T20:08:55Z',end='2026-12-04T20:39:55Z'),'SQL_TRUST_TRANSITION_REFUSED')

    def test_ordinary_c_survives_bridge_expiry(self):
        for env in ('dev','prod'):
            for now in ('2026-12-04T20:09:55Z',CAP,'2026-12-04T20:09:57Z'):
                with self.subTest(env=env,now=now):
                    result=self.invoke(env=env,now=now)
                    self.assertEqual(result.returncode,0,result.stderr)
                    self.assertIn('TEST_DOTNET_BOUNDARY',result.stdout)
