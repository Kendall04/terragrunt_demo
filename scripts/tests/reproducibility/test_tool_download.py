"""Only curl is replaced; exercise URL selection and checksum-before-use."""
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from test_reproducibility import INSTALL, DOC


class ToolDownload(unittest.TestCase):
    def transport(self, item, release, raw=b'fixture', status='504', failure=None):
        calls=[]
        def run(argv, **kwargs):
            calls.append(argv)
            url=argv[-3];path=Path(argv[-1])
            if len(calls)==1:
                raise subprocess.CalledProcessError(22,argv,output=status)
            if failure and len(calls)==failure:
                raise subprocess.CalledProcessError(22,argv,output='403')
            path.write_bytes(json.dumps(release).encode() if '/tags/' in url else raw)
            return subprocess.CompletedProcess(argv,0,stdout='200')
        return calls,run

    def release(self, item):
        api='https://api.github.com/repos/rhysd/actionlint'
        return dict(tag_name='v'+item['version'],draft=False,assets=[dict(
            name=item['url'].rsplit('/',1)[1],id=123,url=api+'/releases/assets/123',
            browser_download_url=item['url'],state='uploaded')])

    def test_504_uses_same_official_asset_and_keeps_pinned_checksum(self):
        item=dict(DOC['tools']['actionlint'],format='binary',sha256=hashlib.sha256(b'fixture').hexdigest())
        calls,run=self.transport(item,self.release(item))
        with tempfile.TemporaryDirectory() as tmp,patch.object(INSTALL.subprocess,'run',side_effect=run):
            artifact=Path(tmp)/'artifact';INSTALL.download('actionlint',item,artifact)
            self.assertEqual(INSTALL.verified_binary(artifact.read_bytes(),item),b'fixture')
        self.assertEqual([c[-3] for c in calls],[item['url'],
            'https://api.github.com/repos/rhysd/actionlint/releases/tags/v'+item['version'],
            'https://api.github.com/repos/rhysd/actionlint/releases/assets/123'])
        for command in calls:
            self.assertIn('=https',command)
            self.assertFalse(any('Authorization' in arg for arg in command))
        self.assertIn('Accept: application/octet-stream',calls[-1])

    def test_successful_browser_download_does_not_consult_API(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(INSTALL.subprocess,'run') as run:
            INSTALL.download('actionlint',DOC['tools']['actionlint'],Path(tmp)/'artifact')
        self.assertEqual(run.call_count,1)

    def test_changed_bytes_fail_before_archive_interpretation(self):
        item=DOC['tools']['actionlint'];calls,run=self.transport(item,self.release(item),raw=b'altered')
        with tempfile.TemporaryDirectory() as tmp,patch.object(INSTALL.subprocess,'run',side_effect=run),\
             patch.object(INSTALL.tarfile,'open') as unpack:
            artifact=Path(tmp)/'artifact';INSTALL.download('actionlint',item,artifact)
            with self.assertRaisesRegex(ValueError,'checksum mismatch'):
                INSTALL.verified_binary(artifact.read_bytes(),item)
            unpack.assert_not_called()

    def test_wrong_or_ambiguous_release_asset_is_not_downloaded(self):
        item=DOC['tools']['actionlint']
        for fault in ('tag','draft','name','missing','duplicate','id','url','browser','state'):
            with self.subTest(fault=fault):
                release=self.release(item);asset=release['assets'][0]
                if fault=='tag':release['tag_name']='v0.0.0'
                if fault=='draft':release['draft']=True
                if fault=='name':asset['name']='other'
                if fault=='missing':release['assets']=[]
                if fault=='duplicate':release['assets'].append(copy.deepcopy(asset))
                if fault=='id':asset['id']=True
                if fault=='url':asset['url']='https://example.invalid/asset'
                if fault=='browser':asset['browser_download_url']=item['url']+'-other'
                if fault=='state':asset['state']='starter'
                calls,run=self.transport(item,release)
                with tempfile.TemporaryDirectory() as tmp,patch.object(INSTALL.subprocess,'run',side_effect=run):
                    with self.assertRaises(ValueError):INSTALL.download('actionlint',item,Path(tmp)/'artifact')
                self.assertEqual(len(calls),2)

    def test_non_504_non_GitHub_and_API_failures_remain_failures(self):
        for name,status,failure,expected in (('actionlint','403',None,1),('actionlint','429',None,1),
                ('terraform','504',None,1),('actionlint','504',2,2),('actionlint','504',3,3)):
            with self.subTest(name=name,status=status,failure=failure):
                item=DOC['tools'][name];calls,run=self.transport(item,self.release(item),status=status,failure=failure)
                with tempfile.TemporaryDirectory() as tmp,patch.object(INSTALL.subprocess,'run',side_effect=run):
                    with self.assertRaises(subprocess.CalledProcessError):INSTALL.download(name,item,Path(tmp)/'artifact')
                self.assertEqual(len(calls),expected)


if __name__=='__main__':unittest.main()
