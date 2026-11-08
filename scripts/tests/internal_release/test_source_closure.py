"""Closed .NET export and unchanged demo-api-only image wire protocol."""
import base64
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import adapters as a
import exchange
import worker


class SourceClosure(unittest.TestCase):
    def nodes(self):
        files = {'demo-api/Dockerfile': b'FROM approved', 'demo-api/.dockerignore': b'**/bin',
            'demo-api/terragrunt-demo.sln': b'..\\operations\\sql-backup\\SqlBackup\\SqlBackup.csproj',
            'demo-api/terragrunt-demo/terragrunt-demo.csproj': b'project',
            '.gitignore': b'bin/', 'global.json': b'{"sdk":{"version":"10.0.402"}}'}
        for project in a.supervisor.SQL_PROJECTS:
            files.update({project+'/'+project.rsplit('/',1)[1]+'.csproj': b'project',
                          project+'/packages.lock.json': b'{}', project+'/Program.cs': b'source'})
        nodes={}
        for name, raw in files.items():
            for parent in reversed(Path(name).parents):
                if parent.as_posix()!='.': nodes[parent.as_posix()]=(parent.as_posix(),'directory',0,b'')
            nodes[name]=(name,'file',0o644,raw)
        return tuple(nodes[k] for k in sorted(nodes))

    def test_closed_source_codec_and_image_projection(self):
        nodes=self.nodes()
        with tempfile.TemporaryDirectory() as tmp, patch.object(os,'getcwd',wraps=os.getcwd):
            previous=os.getcwd()
            try:
                os.chdir(tmp);worker.decode_source(exchange.source_bytes(nodes))
                full=a.supervisor.source_tree(tmp)
                image=a.supervisor.image_source(full)
                self.assertTrue(all(n[0].startswith('demo-api') for n in image))
                self.assertLess(len(image),len(full))
                self.assertEqual(exchange.source_bytes(image),exchange.canonical([
                    [p,k,m,base64.b64encode(raw).decode()] for p,k,m,raw in image]))
                a.supervisor.verify_execution(nodes,tmp)
            finally: os.chdir(previous)

    def test_closed_source_git_blobs_and_closed_paths(self):
        nodes=self.nodes();files={n[0]:n[3] for n in nodes if n[1]=='file'}
        entries=[dict(path=p,type='blob',mode='100644',sha=hashlib.sha1(
            b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()) for p,raw in files.items()]
        def fetch(path):
            return {'sha':'a'*40,'tree':{'sha':'b'*40}} if path.startswith('git/commits/') else {
                'sha':'b'*40,'truncated':False,'tree':entries}
        with tempfile.TemporaryDirectory() as tmp:
            a.Source(fetch,lambda commit,name:files[name]).acquire('Kendall04/terragrunt_demo','a'*40,tmp)
            a.supervisor.verify_execution(nodes,tmp)
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(a.Rejected if hasattr(a,'Rejected') else ValueError):
                a.Source(fetch,lambda commit,name:b'changed').acquire('Kendall04/terragrunt_demo','a'*40,tmp)

    def test_closed_source_rejects_extra_paths_types_and_aliases(self):
        bad=('operations/elsewhere/a.cs','operations/sql-backup/SqlBackup/extra/a.cs',
             'operations/sql-backup/SqlBackup/README.md','scripts/a.py','.git/config',
             'demo-api/../escape','demo-api/bin/a.dll','demo-api/private.key','global.json/a')
        for name in bad:
            for check in (a.supervisor.source_path,worker.source_path):
                with self.subTest(name=name,check=check.__module__),self.assertRaises(ValueError):check(name)
        for node in [('global.json','directory',0,b''),('operations','file',0o644,b''),
                     ('demo-api/a','symlink',0,b'x')]:
            with self.assertRaises(ValueError):worker.decode_source(exchange.source_bytes((node,)))
        nodes=self.nodes();alias=(*nodes,('DEMO-API/Dockerfile','file',0o644,b'evil'))
        with self.assertRaises(ValueError):worker.decode_source(exchange.source_bytes(alias))

    def test_closed_source_requires_root_and_project_dependencies(self):
        nodes=self.nodes()
        for missing in ('.gitignore','global.json',*[p+'/'+p.rsplit('/',1)[1]+'.csproj' for p in a.supervisor.SQL_PROJECTS]):
            with tempfile.TemporaryDirectory() as tmp:
                a.supervisor.materialize_source(tuple(n for n in nodes if n[0]!=missing),Path(tmp)/'source')
                with self.assertRaises(a.supervisor.SourceIntegrity):a.supervisor.source_tree(Path(tmp)/'source')

    def test_closed_source_rejects_existing_link_and_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            previous=os.getcwd()
            try:
                os.chdir(tmp);Path('demo-api').mkdir();Path('demo-api/a').write_bytes(b'original')
                os.link('demo-api/a','demo-api/b')
                with self.assertRaises(FileExistsError):
                    worker.decode_source(exchange.source_bytes((('demo-api/b','file',0o644,b'evil'),)))
                with self.assertRaises(a.supervisor.SourceIntegrity):a.supervisor.source_node(tmp,'demo-api/a')
                self.assertEqual(Path('demo-api/a').read_bytes(),b'original')
            finally:os.chdir(previous)

    def test_closed_source_full_seal_detects_backup_mutation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'source';a.supervisor.materialize_source(self.nodes(),root)
            nodes=a.supervisor.source_tree(root)
            seal=a.supervisor.source_seal('Kendall04/terragrunt_demo','a'*40,nodes)
            image=a.supervisor.image_source(nodes)
            (root/'operations/sql-backup/SqlBackup/Program.cs').write_bytes(b'mutated')
            self.assertEqual(image,a.supervisor.image_source(a.supervisor.source_tree(root)))
            self.assertNotEqual(seal,a.supervisor.source_seal('Kendall04/terragrunt_demo','a'*40,a.supervisor.source_tree(root)))
            with self.assertRaises(a.supervisor.SourceIntegrity):a.supervisor.verify_execution(nodes,root)
