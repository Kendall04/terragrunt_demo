#!/usr/bin/env python3
"""Prepare a hash-checked offline Docker context, never builds/publishes/installs."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil

SOURCES = {'Dockerfile':'scripts/wp4d/Delivery.CodeBuild.Dockerfile',
           'requirements.lock':'scripts/wp4d/requirements-codebuild.lock',
           'scripts/wp4d/runtime.py':'scripts/wp4d/runtime.py',
           'scripts/wp4d/installed.py':'scripts/wp4d/installed.py'}


def require(value):
    if not value: raise ValueError('WP4_IMAGE_CONTEXT_REFUSED')


def sha(raw): return hashlib.sha256(raw).hexdigest()


def prepare(root, cache, jq, output):
    root,cache,jq,output = map(lambda p:Path(p).resolve(), (root,cache,jq,output))
    require(not output.exists() and not output.is_relative_to(root))
    lock=json.loads((root/'scripts/wp4d/codebuild-image.lock.json').read_text(encoding='utf-8'))
    require(lock['Platform']=='linux/amd64' and type(lock['SourceDateEpoch']) is int
            and lock['SourceDateEpoch']>0 and set(lock['SourcesSha256'])==set(SOURCES.values()))
    sources={}
    for dest,name in SOURCES.items():
        path=root/name;require(path.is_file() and not path.is_symlink())
        raw=path.read_bytes().replace(b'\r\n',b'\n')
        require(sha(raw)==lock['SourcesSha256'][name]);sources[dest]=raw
    require(('FROM '+lock['BaseRef']+'\n').encode() in sources['Dockerfile'])
    require(jq.is_file() and not jq.is_symlink() and sha(jq.read_bytes())==lock['Jq']['Sha256'])
    require(type(lock['Wheels']) is list and bool(lock['Wheels']))
    wheels={}
    for row in lock['Wheels']:
        name=row['File'];require(type(name) is str and name.endswith('.whl')
            and '/' not in name and '\\' not in name and ':' not in name and name not in wheels)
        path=cache/name;require(path.is_file() and not path.is_symlink())
        require(path.stat().st_size==row['Bytes'] and sha(path.read_bytes())==row['Sha256'])
        wheels[name]=path
    # Validate every input before creating output; no cache mutation or overwrite.
    output.mkdir(parents=True)
    for name,raw in sources.items():
        target=output/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(raw)
        os.utime(target,(lock['SourceDateEpoch'],lock['SourceDateEpoch']))
    target=output/'jq';shutil.copyfile(jq,target);os.utime(target,(lock['SourceDateEpoch'],lock['SourceDateEpoch']))
    (output/'wheels').mkdir()
    for name,path in wheels.items():
        try:os.link(path,output/'wheels'/name)
        except OSError:shutil.copyfile(path,output/'wheels'/name)
    result={'Status':'LOCAL_CONTEXT_PREPARED_NOT_BUILT_OR_INSTALLED','BaseRef':lock['BaseRef'],
      'SourceDateEpoch':lock['SourceDateEpoch'],'ExpectedLocalManifestDigest':lock['ExpectedLocalManifestDigest'],
      'FilesSha256':{p.relative_to(output).as_posix():sha(p.read_bytes()) for p in output.rglob('*') if p.is_file()},
      'CloudOperations':0}
    (output/'context-manifest.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--wheels',type=Path,required=True)
    parser.add_argument('--jq',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    print(json.dumps(prepare(Path(__file__).resolve().parents[2],args.wheels,args.jq,args.output),sort_keys=True))


if __name__=='__main__':
    try:main()
    except Exception:raise SystemExit('WP4_IMAGE_CONTEXT_REFUSED_NO_BUILD_OR_CLOUD_ACTION') from None
