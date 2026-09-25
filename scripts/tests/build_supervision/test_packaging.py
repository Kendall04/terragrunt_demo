"""Execute extracted package bytes with offline ports; enforce bounded source API."""
import ast
import base64
import copy
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile
import types
import unittest
from unittest.mock import patch
import test_supervisor as a
import bundles


def bounded_source(text):
    tree=ast.parse(text)
    forbidden={'Qualifications','Finalizer','validate_eligibility','qualification','qualifications',
               'write_eligibility','publish_qualification','start_build','invoke','deploy','pass_role'}
    names={n.id for n in ast.walk(tree) if isinstance(n,ast.Name)}
    names|={n.attr for n in ast.walk(tree) if isinstance(n,ast.Attribute)}
    names|={n.name for n in ast.walk(tree) if isinstance(n,(ast.FunctionDef,ast.ClassDef))}
    return not names & forbidden


class Packaging(unittest.TestCase):
    def test_supervisor_has_no_qualification_or_runtime_grants(self):
        source=Path(a.s.__file__).read_text(encoding='utf-8')
        self.assertTrue(bounded_source(source))
        self.assertFalse(bounded_source(source+'\ndef publish_qualification(): pass\n'))
        from test_sensitivity import EVIDENCE
        EVIDENCE['qualification_writer_admission']={'status':'DETECTED','category':'SOURCE_ADMISSION','executed':1,'errors':0}
    def test_package_code_mutation_changes_digest(self):
        d=json.loads((a.ROOT/'terraform/infra/security/authority.json').read_text())
        with tempfile.TemporaryDirectory(prefix='wp3b-package-') as tmp:
            root=Path(tmp)
            paths=set(p for group in bundles.EXECUTABLE_SOURCES.values() for p in group)|{bundles.SOURCE,'terraform/infra/security/authority.json'}
            for name in paths:
                path=root/name;path.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(a.ROOT/name,path)
            for name,target in [('build','scripts/build_supervision/supervisor.py'),('qualification-finalizer','scripts/qualification/finalizer.py')]:
                before=bundles.artifact(root,d['control_bundles'],name)
                with (root/target).open('a',encoding='utf-8') as stream:stream.write('\n# disposable package mutation\n')
                after=bundles.artifact(root,d['control_bundles'],name)
                self.assertNotEqual(bundles.digest(before),bundles.digest(after))
                with self.assertRaises(ValueError):bundles.verify_artifact(root,d['control_bundles'],name,after)
    def test_accepted_wp3a_bytes_unchanged(self):
        expected={'scripts/qualification/finalizer.py':'229fa9a394169538f9158b4f1d3e8d5d4e15a0c21819ed90ac33a85eba4c7098',
                  'ci/schemas/e1-qualification.schema.json':'79ba84dfa4bd8ca5ce4955bc4a97a888cc79a28a06c8eee43063319508a8d8d0'}
        for name,digest in expected.items():self.assertEqual(hashlib.sha256((a.ROOT/name).read_bytes().replace(b'\r\n',b'\n')).hexdigest(),digest)
    def test_extracted_build_entrypoint_executes(self):
        d=json.loads((a.ROOT/'terraform/infra/security/authority.json').read_text())
        raw=bundles.artifact(a.ROOT,d['control_bundles'],'build');package=json.loads(raw)
        with tempfile.TemporaryDirectory(prefix='wp3b-executable-') as tmp:
            root=Path(tmp)
            for name,encoded in package['files'].items():
                p=root/name
                self.assertTrue(p.resolve().is_relative_to(root.resolve()))
                p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(base64.b64decode(encoded,validate=True))
            def load(name,path):
                m=types.ModuleType(name);m.__file__=str(root/path)
                exec(compile((root/path).read_text(encoding='utf-8'),str(root/path),'exec'),m.__dict__)
                return m
            original_path=sys.path.copy()
            try:
                finalizer=load('packaged_finalizer','scripts/qualification/finalizer.py')
                with patch.dict(sys.modules,{'finalizer':finalizer}):
                    supervisor=load('packaged_supervisor','scripts/build_supervision/supervisor.py')
                    with patch.dict(sys.modules,{'supervisor':supervisor}):
                        entry=load('packaged_entrypoint','scripts/build_supervision/entrypoint.py')
                        ports=a.fixture(supervisor)
                        r=entry.build(*ports,{'operation_id':a.OP})
                        self.assertEqual(r['state'],'SUCCEEDED')
                        self.assertEqual(finalizer.validate('result',r),r)
            finally:sys.path[:]=original_path
    def test_terminal_acceptance_mutant_is_detected_by_compatibility_case(self):
        # Mutation is in a disposable finalizer only; repository WP3A is untouched.
        text=Path(a.f.__file__).read_text(encoding='utf-8')
        old="validate('wakeup', wakeup)";self.assertEqual(text.count(old),1)
        m=types.ModuleType('bad_finalizer');m.__file__=a.f.__file__
        exec(compile(text.replace(old,"return {'qualified': True}"),'<terminal-bypass>','exec'),m.__dict__)
        case=a.Tests('test_terminal_not_qualification_evidence')
        result=unittest.TestResult()
        with patch.object(a,'f',m):case.run(result)
        self.assertEqual(len(result.errors),0)
        self.assertEqual(len(result.failures),1)
        self.assertIn('Non-qualifying record produced qualification',result.failures[0][1])
        from test_sensitivity import EVIDENCE
        EVIDENCE['terminal_qualification_bypass']={'status':'DETECTED','category':'SECURITY','executed':1,'errors':0,'failures':1,'outcomes':['test_terminal_not_qualification_evidence']}
