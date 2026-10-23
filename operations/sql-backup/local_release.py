#!/usr/bin/env python3
"""Versioned component inventory only. Caller pins manifest hash + source commit."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import tarfile

class Refused(ValueError): pass
def sha(path):
    digest=hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda:stream.read(1048576),b''): digest.update(chunk)
    return digest.hexdigest()

def inventory(directory):
    if not directory.is_absolute() or not directory.is_dir() or any(p.is_symlink() for p in (directory,*directory.parents)): raise Refused('SAFE_DIRECTORY_REQUIRED')
    files={}
    for path in sorted(directory.rglob('*')):
        if path.is_symlink(): raise Refused('SYMLINK_DENIED')
        if path.is_file() and path != directory/'local-component-manifest.json': files[path.relative_to(directory).as_posix()]={'Bytes':path.stat().st_size,'Sha256':sha(path)}
    return files

def create(directory, identity, commit):
    if not re.fullmatch('[a-f0-9]{40}',commit) or set(identity)!={'Component','SourceCommit','InformationalVersion'} or identity.get('SourceCommit')!=commit or identity.get('Component')!='SqlBackup' or not identity['InformationalVersion'].endswith('+'+commit): raise Refused('COMPONENT_REVISION_MISMATCH')
    runtime=json.loads((directory/'SqlBackup.runtimeconfig.json').read_text())['runtimeOptions']
    if not any(x.get('name')=='Microsoft.NETCore.App' and x.get('version')=='10.0.13' for x in runtime.get('includedFrameworks',[])): raise Refused('SELF_CONTAINED_RUNTIME_REQUIRED')
    header=(directory/'SqlBackup').read_bytes()[:20]
    if header[:5]!=b'\x7fELF\x02' or header[18:20]!=b'\x3e\x00': raise Refused('LINUX_X64_REQUIRED')
    return {'SchemaVersion':1,'Component':'SqlBackup','SourceCommit':commit,'Runtime':'10.0.13','Rid':'linux-x64','SelfContained':True,'BuildIdentity':identity,'Files':inventory(directory),'DeploymentAuthorized':False,'Uploaded':False}

def verify(directory, expected_manifest_sha, expected_commit):
    path=directory/'local-component-manifest.json'
    if sha(path)!=expected_manifest_sha: raise Refused('MANIFEST_HASH_MISMATCH')
    value=json.loads(path.read_text())
    if value.get('SourceCommit')!=expected_commit or value.get('BuildIdentity',{}).get('SourceCommit')!=expected_commit: raise Refused('COMPONENT_REVISION_MISMATCH')
    if value.get('Files')!=inventory(directory): raise Refused('COMPONENT_CONTENT_CHANGED')
    if value.get('DeploymentAuthorized') is not False or value.get('Uploaded') is not False: raise Refused('LOCAL_COMPONENT_ONLY')
    return value

def verify_bundle(archive, archive_sha, component):
    if sha(archive)!=archive_sha: raise Refused('ARCHIVE_HASH_MISMATCH')
    with tarfile.open(archive,'r:') as stream:
        entry=stream.getmember('bundle-manifest.json')
        if not entry.isfile() or entry.size>1048576: raise Refused('BUNDLE_MANIFEST_REQUIRED')
        value=json.loads(stream.extractfile(entry).read())
        bound={name.removeprefix('backup/'):{'Bytes':row['Bytes'],'Sha256':row['Sha256']} for name,row in value['Files'].items() if name.startswith('backup/')}
        if value.get('SourceCommit')!=component['SourceCommit'] or bound!=component['Files']: raise Refused('BUNDLE_COMPONENT_MISMATCH')
        for name,row in bound.items():
            entries=[item for item in stream.getmembers() if item.name=='backup/'+name]
            if len(entries)!=1 or not entries[0].isfile() or entries[0].size!=row['Bytes']: raise Refused('BUNDLE_COMPONENT_MISMATCH')
            digest=hashlib.sha256()
            with stream.extractfile(entries[0]) as body:
                for chunk in iter(lambda:body.read(1048576),b''):digest.update(chunk)
            if digest.hexdigest()!=row['Sha256']: raise Refused('BUNDLE_COMPONENT_MISMATCH')
    return component

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=('create','verify','verify-bundle'));p.add_argument('--directory',required=True,type=Path);p.add_argument('--commit',required=True);p.add_argument('--identity',type=Path);p.add_argument('--manifest-sha256');p.add_argument('--archive',type=Path);p.add_argument('--archive-sha256');a=p.parse_args()
    if a.action=='create':
        target=a.directory/'local-component-manifest.json'
        if target.exists(): raise Refused('MANIFEST_EXISTS')
        value=create(a.directory,json.loads(a.identity.read_text()),a.commit);target.write_text(json.dumps(value,sort_keys=True,indent=2)+'\n');digest=sha(target)
    else:
        value=verify(a.directory,a.manifest_sha256,a.commit);digest=a.manifest_sha256
        if a.action=='verify-bundle':verify_bundle(a.archive,a.archive_sha256,value)
    print(json.dumps({'Status':'LOCAL_COMPONENT_BOUND','SourceCommit':value['SourceCommit'],'ManifestSha256':digest,'Files':len(value['Files']),'DeploymentAuthorized':False}))

if __name__=='__main__':
    try: main()
    except Exception as error:
        print(json.dumps({'Status':'REFUSED','Code':str(error) if isinstance(error,Refused) else 'LOCAL_COMPONENT_FAILED'}));raise SystemExit(1)
