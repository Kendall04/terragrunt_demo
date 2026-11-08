"""Offline context creation and rejection; fixtures contain no executable wheels."""
import importlib.util,json,sys,tempfile,unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[3]
spec=importlib.util.spec_from_file_location('image_context',ROOT/'scripts/wp4d/prepare_image_context.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)


def fixture(directory):
    root=directory/'repo';cache=directory/'cache';cache.mkdir();jq=directory/'jq';jq.write_bytes(b'synthetic-jq')
    base='docker.io/library/python@sha256:'+'a'*64
    for name in module.SOURCES.values():
        path=root/name;path.parent.mkdir(parents=True,exist_ok=True)
        path.write_bytes(('FROM '+base+'\n').encode() if name.endswith('Dockerfile') else b'synthetic-source\n')
    wheel=cache/'synthetic-1-py3-none-any.whl';wheel.write_bytes(b'not-executed')
    lock={'Platform':'linux/amd64','SourceDateEpoch':1000,'BaseRef':base,
      'SourcesSha256':{name:module.sha((root/name).read_bytes()) for name in module.SOURCES.values()},
      'Jq':{'Sha256':module.sha(jq.read_bytes())},'ExpectedLocalManifestDigest':'sha256:'+'b'*64,
      'Wheels':[{'File':wheel.name,'Bytes':wheel.stat().st_size,'Sha256':module.sha(wheel.read_bytes())}]}
    lockpath=root/'scripts/wp4d/codebuild-image.lock.json';lockpath.write_text(json.dumps(lock),encoding='utf-8')
    return root,cache,jq,directory/'out',lockpath,lock


class ImageContext(unittest.TestCase):
    def test_verified_context_preserves_sources_cache_and_has_no_execution(self):
        with tempfile.TemporaryDirectory() as tmp:
            root,cache,jq,out,_,_=fixture(Path(tmp))
            before={p:p.read_bytes() for p in list(root.rglob('*'))+list(cache.rglob('*')) if p.is_file()}
            result=module.prepare(root,cache,jq,out)
            self.assertEqual(result['Status'],'LOCAL_CONTEXT_PREPARED_NOT_BUILT_OR_INSTALLED')
            self.assertEqual(result['CloudOperations'],0)
            self.assertTrue((out/'context-manifest.json').is_file())
            self.assertTrue(all(p.read_bytes()==raw for p,raw in before.items()))
            self.assertEqual(result['FilesSha256']['Dockerfile'],module.sha((out/'Dockerfile').read_bytes()))

    def test_tampered_source_jq_or_wheel_fails_before_output(self):
        for kind in ('source','jq','wheel'):
            with tempfile.TemporaryDirectory() as tmp:
                root,cache,jq,out,_,_=fixture(Path(tmp))
                path=jq if kind=='jq' else next(cache.iterdir()) if kind=='wheel' else root/'scripts/wp4d/runtime.py'
                path.write_bytes(b'tampered')
                with self.subTest(kind=kind),self.assertRaises(ValueError):module.prepare(root,cache,jq,out)
                self.assertFalse(out.exists())

    def test_traversal_wheel_and_foreign_base_are_rejected(self):
        for change in ('traversal','base'):
            with tempfile.TemporaryDirectory() as tmp:
                root,cache,jq,out,path,lock=fixture(Path(tmp))
                if change=='traversal':lock['Wheels'][0]['File']='../foreign.whl'
                else:lock['BaseRef']='docker.io/unapproved@sha256:'+'c'*64
                path.write_text(json.dumps(lock),encoding='utf-8')
                with self.subTest(change=change),self.assertRaises(ValueError):module.prepare(root,cache,jq,out)
                self.assertFalse(out.exists())

    def test_existing_output_and_repository_output_are_never_replaced(self):
        with tempfile.TemporaryDirectory() as tmp:
            root,cache,jq,out,_,_=fixture(Path(tmp));out.mkdir();sentinel=out/'unique';sentinel.write_bytes(b'preserve')
            for target in (out,root/'new-context'):
                with self.assertRaises(ValueError):module.prepare(root,cache,jq,target)
            self.assertEqual(sentinel.read_bytes(),b'preserve')
            self.assertFalse((root/'new-context').exists())
