#!/usr/bin/env python3
"""Build/inspect a verified Linux package; installation never starts services."""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import pwd
import re
import stat
import tarfile

REQUIRED={'SqlBackup','SqlBackup.runtimeconfig.json','SqlBackup.deps.json','libhostfxr.so','libcoreclr.so','System.Private.CoreLib.dll'}
CONFIG_KEYS=set('Database StagingDirectory RestoreDirectory Bucket Prefix BackupKeyArn TextKeyArn ExpectedEc2RoleName MaxBackupBytes FreeReserveBytes TimeoutSeconds ProposedIntervalHours ProposedRetentionDays ProposedMaxAgeHours RetainLocalVerifiedBackups'.split())

def digest(data): return hashlib.sha256(data).hexdigest()
def require(condition,code):
    if not condition: raise ValueError(code)
def no_links(path):
    require(path.is_absolute(),'ABSOLUTE_ROOT_REQUIRED')
    require('..' not in path.parts,'PARENT_PATH_DENIED')
    require(not any(item.is_symlink() for item in (path,*path.parents)),'SYMLINK_DENIED')

def build(publish,output,commit):
    require(re.fullmatch('[a-f0-9]{40}',commit) is not None,'SOURCE_COMMIT_REQUIRED')
    no_links(publish)
    require(REQUIRED.issubset({item.name for item in publish.iterdir()}),'SELF_CONTAINED_PUBLISH_REQUIRED')
    runtime=json.loads((publish/'SqlBackup.runtimeconfig.json').read_text())['runtimeOptions']
    require(any(item.get('name')=='Microsoft.NETCore.App' and item.get('version')=='10.0.13' for item in runtime.get('includedFrameworks',[])),'PINNED_SELF_CONTAINED_RUNTIME_REQUIRED')
    files={}
    for path in sorted(publish.rglob('*')):
        require(not path.is_symlink(),'PACKAGE_SYMLINK_DENIED')
        if path.is_file(): files['bin/'+path.relative_to(publish).as_posix()]=(path.read_bytes(),0o755 if path.name=='SqlBackup' or path.suffix=='.so' else 0o644)
    base=Path(__file__).resolve().parent
    for name in ('host.py','package.py','sql-backup.service.in','sql-backup.timer.in'):
        files[name]=((base/name).read_bytes(),0o755 if name.endswith('.py') else 0o644)
    manifest={'SchemaVersion':1,'SourceCommit':commit,'Runtime':'10.0.13','Target':'linux-x64','Files':{name:{'Sha256':digest(body),'Bytes':len(body),'Mode':mode} for name,(body,mode) in files.items()}}
    files['manifest.json']=(json.dumps(manifest,sort_keys=True,separators=(',',':')).encode(),0o644)
    require(not output.exists(),'PACKAGE_OUTPUT_EXISTS')
    # Uncompressed tar avoids gzip timestamps and makes byte-identical inputs reproducible.
    with tarfile.open(output,'w',format=tarfile.USTAR_FORMAT) as archive:
        for name,(body,mode) in sorted(files.items()):
            info=tarfile.TarInfo(name); info.size=len(body); info.mode=mode; info.mtime=0; info.uid=info.gid=0
            archive.addfile(info,io.BytesIO(body))
    return {'Status':'PACKAGED','Sha256':digest(output.read_bytes()),'SourceCommit':commit,'Files':len(manifest['Files'])}

def inspect(package,expected):
    require(re.fullmatch('[a-f0-9]{64}',expected) is not None and digest(package.read_bytes())==expected,'PACKAGE_HASH_MISMATCH')
    files={}; total=0
    with tarfile.open(package,'r:') as archive:
        for item in archive:
            name=PurePosixPath(item.name)
            require(item.isfile() and not name.is_absolute() and '..' not in name.parts and name.as_posix()==item.name and item.name not in files,'UNSAFE_PACKAGE_MEMBER')
            total+=item.size; require(total<=536870912 and len(files)<2000,'PACKAGE_BOUND_EXCEEDED')
            files[item.name]=archive.extractfile(item).read()
    manifest=json.loads(files.pop('manifest.json'))
    require(manifest['SchemaVersion']==1 and manifest['Runtime']=='10.0.13' and manifest['Target']=='linux-x64','PACKAGE_CONTRACT_MISMATCH')
    require(set(files)==set(manifest['Files']),'PACKAGE_INVENTORY_MISMATCH')
    for name,body in files.items():
        record=manifest['Files'][name]
        require(digest(body)==record['Sha256'] and len(body)==record['Bytes'] and record['Mode'] in (0o644,0o755),'PACKAGE_CONTENT_MISMATCH')
    return manifest,files

def install(package,expected,config,root,user,apply,confirmation):
    manifest,files=inspect(package,expected); no_links(root)
    require(config.stat().st_size<=65536,'CONFIG_TOO_LARGE')
    value=json.loads(config.read_text())
    require(set(value).issubset(CONFIG_KEYS),'UNKNOWN_OR_SECRET_CONFIG_FIELD')
    require(all(re.fullmatch('/[A-Za-z0-9/_-]+',value[key]) is not None and '..' not in Path(value[key]).parts for key in ('StagingDirectory','RestoreDirectory')),'SAFE_ABSOLUTE_DATA_PATH_REQUIRED')
    require(re.fullmatch('[A-Za-z][A-Za-z0-9_]{0,63}',value['Database']) is not None,'INVALID_DATABASE')
    require(re.fullmatch('[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]',value['Bucket']) is not None,'INVALID_BUCKET')
    require(re.fullmatch('[a-z0-9][a-z0-9/_-]{1,120}',value['Prefix']) is not None and '//' not in value['Prefix'],'INVALID_PREFIX')
    require(all(re.fullmatch('arn:aws:kms:us-east-1:341936017254:key/[a-f0-9-]{36}',value.get(key,'')) is not None for key in ('BackupKeyArn','TextKeyArn')),'EXACT_KEY_ARNS_REQUIRED')
    require(re.fullmatch('[A-Za-z0-9+=,.@_-]{1,64}',value.get('ExpectedEc2RoleName','')) is not None,'EXACT_ROLE_NAME_REQUIRED')
    require(10<=value.get('TimeoutSeconds',600)<=600 and value.get('ProposedIntervalHours',1)==1,'HOURLY_SERVICE_BOUND_REQUIRED')
    identity=pwd.getpwnam(user)
    destination=root/'opt/terragrunt-demo/sql-backup'
    configdir=root/'etc/terragrunt-demo/sql-backup'
    units=root/'etc/systemd/system'
    paths={str(destination):'root-owned 0755 executable package',str(configdir/'config.json'):'root:service-group 0640 public configuration',str(units/'sql-backup.service'):'0644 inert unit',str(units/'sql-backup.timer'):'0644 hourly timer; not enabled',value['StagingDirectory']:'service-owned 0700 staging'}
    result={'Status':'INSTALL_PLAN','PackageSha256':expected,'SourceCommit':manifest['SourceCommit'],'Paths':paths,'ServiceUser':user,'SystemctlActions':[],'CredentialFilesCreated':False}
    if not apply: return result
    if root==Path('/'):
        require(confirmation==expected and os.geteuid()==0,'HOST_INSTALL_CONFIRMATION_AND_ROOT_REQUIRED')
    else:
        require(root.exists() and root.is_dir() and root.parent!=root,'EXISTING_FIXTURE_ROOT_REQUIRED')
    receipt=destination/'install-receipt.json'
    if destination.exists():
        require(receipt.is_file() and not receipt.is_symlink(),'UNMANAGED_INSTALLATION_EXISTS')
        previous=json.loads(receipt.read_text())
        require(previous['PackageSha256']==expected and previous['ConfigSha256']==digest(config.read_bytes()) and previous['ServiceUser']==user,'REVIEWED_REPLACEMENT_REQUIRED')
        for relative,record in previous['InstalledFiles'].items():
            path=root/relative; no_links(path)
            require(path.is_file() and digest(path.read_bytes())==record['Sha256'] and stat.S_IMODE(path.stat().st_mode)==record['Mode'],'INSTALLED_FILE_DRIFT')
        staging=root/value['StagingDirectory'].lstrip('/')
        no_links(staging)
        require(staging.is_dir() and stat.S_IMODE(staging.stat().st_mode)==0o700 and staging.stat().st_uid==identity.pw_uid,'STAGING_PERMISSION_DRIFT')
        return dict(result,Status='ALREADY_INSTALLED')
    for path in (configdir,units/'sql-backup.service',units/'sql-backup.timer'):
        no_links(path); require(not path.exists(),'UNMANAGED_TARGET_EXISTS')
    staging=root/value['StagingDirectory'].lstrip('/')
    no_links(staging); require(not staging.exists(),'UNMANAGED_STAGING_EXISTS')
    installed={}
    def put(path,body,mode,gid=None):
        no_links(path)
        path.parent.mkdir(parents=True,exist_ok=True)
        descriptor=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,mode)
        with os.fdopen(descriptor,'wb') as stream: stream.write(body)
        path.chmod(mode)
        if os.geteuid()==0: os.chown(path,0,0 if gid is None else gid)
        installed[path.relative_to(root).as_posix()]={'Sha256':digest(body),'Mode':mode}
    destination.mkdir(parents=True,mode=0o755)
    for name,body in files.items():
        if name.endswith('.in'): continue
        put(destination/name,body,manifest['Files'][name]['Mode'])
    put(configdir/'config.json',config.read_bytes(),0o640,identity.pw_gid)
    for name in ('sql-backup.service','sql-backup.timer'):
        body=files[name+'.in'].decode().replace('@SERVICE_USER@',user).replace('@STAGING@',value['StagingDirectory'])
        put(units/name,body.encode(),0o644)
    staging.mkdir(parents=True,mode=0o700); staging.chmod(0o700)
    if os.geteuid()==0: os.chown(staging,identity.pw_uid,identity.pw_gid)
    put(receipt,json.dumps({'SchemaVersion':1,'PackageSha256':expected,'SourceCommit':manifest['SourceCommit'],'ConfigSha256':digest(config.read_bytes()),'ServiceUser':user,'InstalledFiles':installed},indent=2).encode(),0o644)
    return dict(result,Status='STAGED_NOT_ENABLED',StagingUid=identity.pw_uid)

def main():
    parser=argparse.ArgumentParser(description=__doc__); commands=parser.add_subparsers(dest='action',required=True)
    buildargs=commands.add_parser('build'); buildargs.add_argument('--publish-dir',type=Path,required=True); buildargs.add_argument('--out',type=Path,required=True); buildargs.add_argument('--source-commit',required=True)
    deploy=commands.add_parser('install'); deploy.add_argument('--package',type=Path,required=True); deploy.add_argument('--expected-sha256',required=True); deploy.add_argument('--config',type=Path,required=True); deploy.add_argument('--root',type=Path,default=Path('/')); deploy.add_argument('--service-user',default='mssql'); deploy.add_argument('--apply',action='store_true'); deploy.add_argument('--confirm-host-install')
    args=parser.parse_args()
    if args.action=='build': return build(args.publish_dir,args.out,args.source_commit)
    return install(args.package,args.expected_sha256,args.config,args.root,args.service_user,args.apply,args.confirm_host_install)

if __name__=='__main__':
    try: print(json.dumps(main(),separators=(',',':')))
    except Exception as error:
        print(json.dumps({'Status':'FAILED','Code':str(error) if isinstance(error,ValueError) else 'PACKAGE_OPERATION_FAILED'}))
        raise SystemExit(1)
