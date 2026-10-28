#!/usr/bin/env python3
"""Plan or explicitly provision lab-only SQL credentials on the selected EC2 host.

Never invokes systemctl, uploads credentials, or writes secret values to stdout.
The approval hash is an operator acknowledgement, not a substitute for owner consent.
"""
import argparse
import hashlib
import ipaddress
import urllib.request
import json
import os
from pathlib import Path
import re
import secrets
import stat
import subprocess

ACCOUNT='341936017254'
ROLE='demo-dev-data-sql-ec2-role'
SA='arn:aws:secretsmanager:us-east-1:341936017254:secret:demo/dev/db/sql-sa-password-30fCjc'
LOGINS=('td_backup_dev','td_verify_dev')

def require(ok,code):
    if not ok: raise ValueError(code)

def digest(body): return hashlib.sha256(body).hexdigest()

def no_links(path):
    require(path.is_absolute() and '..' not in path.parts,'ABSOLUTE_SAFE_ROOT_REQUIRED')
    require(not any(p.is_symlink() for p in (path,*path.parents)),'SYMLINK_DENIED')

def private_write(path,body,mode=0o600):
    no_links(path)
    descriptor=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,mode)
    with os.fdopen(descriptor,'wb') as stream: stream.write(body)
    path.chmod(mode)

def sql_batch(database,backup_password,verify_password):
    require(re.fullmatch('[A-Za-z][A-Za-z0-9_]{0,63}',database) is not None,'SAFE_DATABASE_REQUIRED')
    require(all(re.fullmatch('Synthetic![a-f0-9]{48}',p) for p in (backup_password,verify_password)),'GENERATED_PASSWORD_REQUIRED')
    return f"""SET NOCOUNT ON; SET XACT_ABORT ON;
USE master;
IF DB_ID(N'{database}') IS NULL THROW 51000, 'Database not ready', 1;
IF SUSER_ID(N'{LOGINS[0]}') IS NOT NULL OR SUSER_ID(N'{LOGINS[1]}') IS NOT NULL THROW 51000, 'Existing login requires review', 1;
BEGIN TRANSACTION;
CREATE LOGIN [{LOGINS[0]}] WITH PASSWORD=N'{backup_password}', CHECK_POLICY=ON;
CREATE LOGIN [{LOGINS[1]}] WITH PASSWORD=N'{verify_password}', CHECK_POLICY=ON;
CREATE USER [{LOGINS[1]}] FOR LOGIN [{LOGINS[1]}];
GRANT CREATE DATABASE TO [{LOGINS[1]}];
USE [{database}];
CREATE USER [{LOGINS[0]}] FOR LOGIN [{LOGINS[0]}];
ALTER ROLE db_backupoperator ADD MEMBER [{LOGINS[0]}];
COMMIT;
"""

def sql_endpoint(approval):
    value=approval['Runtime'].get('SqlEndpoint','127.0.0.1')
    if value=='127.0.0.1': return value
    try:
        address=ipaddress.ip_address(value)
        require(address.version==4 and str(address)==value and any(address in ipaddress.ip_network(cidr)
            for cidr in ('10.0.0.0/8','172.16.0.0/12','192.168.0.0/16')),'PRIVATE_SQL_ENDPOINT_REQUIRED')
    except (ValueError,TypeError): raise ValueError('PRIVATE_SQL_ENDPOINT_REQUIRED') from None
    require(re.fullmatch('i-[0-9a-f]{17}',approval['Runtime'].get('InstanceId','')) is not None,'EXACT_PRIVATE_HOST_REQUIRED')
    return value

class HostPort:
    def identity(self):
        opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
        token=opener.open(urllib.request.Request('http://169.254.169.254/latest/api/token',data=b'',method='PUT',
            headers={'X-aws-ec2-metadata-token-ttl-seconds':'60'}),timeout=3).read(4097).decode()
        require(0<len(token)<=4096,'IMDS_TOKEN_INVALID')
        raw=opener.open(urllib.request.Request('http://169.254.169.254/latest/dynamic/instance-identity/document',
            headers={'X-aws-ec2-metadata-token':token}),timeout=3).read(65537)
        require(len(raw)<=65536,'IMDS_IDENTITY_TOO_LARGE')
        return json.loads(raw)
    def environment(self):
        # Only IMDS can supply AWS auth: ignore profiles, files and ambient tokens.
        return {'PATH':'/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:/opt/mssql-tools18/bin',
                'HOME':'/nonexistent','AWS_CONFIG_FILE':'/dev/null','AWS_SHARED_CREDENTIALS_FILE':'/dev/null',
                'AWS_REGION':'us-east-1','AWS_DEFAULT_REGION':'us-east-1','AWS_EC2_METADATA_V1_DISABLED':'true',
                'AWS_MAX_ATTEMPTS':'1','AWS_PAGER':''}
    def aws(self,*args):
        # Ubuntu 22.04's existing awscli may be v1; AWS_PAGER also covers v2.
        run=subprocess.run(['aws','--region','us-east-1','--output','json',*args],env=self.environment(),text=True,capture_output=True,timeout=60)
        require(run.returncode==0 and len(run.stdout)<=65536,'INSTANCE_ROLE_READ_FAILED')
        return json.loads(run.stdout)
    def sql(self,password,batch,endpoint='127.0.0.1'):
        env=self.environment(); env['SQLCMDPASSWORD']=password
        run=subprocess.run(['/opt/mssql-tools18/bin/sqlcmd','-S',endpoint,'-C','-U','sa','-b','-l','10','-t','60'],input=batch,env=env,text=True,capture_output=True,timeout=75)
        # Do not return sqlcmd diagnostics: SQL input may contain passwords.
        require(run.returncode==0,'SQL_BOOTSTRAP_FAILED_OR_UNKNOWN')

def operate(approval_path,config_path,root,apply=False,confirmation=None,port=None):
    require(approval_path.stat().st_size<=65536 and config_path.stat().st_size<=65536,'PUBLIC_INPUT_BOUND_EXCEEDED')
    approval_bytes=approval_path.read_bytes(); approval=json.loads(approval_bytes)
    config=json.loads(config_path.read_bytes()); approval_sha=digest(approval_bytes)
    require(approval['Schema']=='SQL_BACKUP_EC2_REVIEW_V1' and approval['Account']==ACCOUNT and approval['Region']=='us-east-1','REVIEW_ACCOUNT_REQUIRED')
    require(approval['Runtime']['ExpectedRole']==f'arn:aws:iam::{ACCOUNT}:role/{ROLE}' and approval['Runtime']['ExistingSaSecret']==SA,'REVIEW_ROLE_AND_SECRET_REQUIRED')
    endpoint=sql_endpoint(approval)
    recovery=approval['Runtime'].get('RecoveryTrial')
    if recovery is not None:
        require(isinstance(recovery,str) and re.fullmatch('r[0-9]{8}[a-z0-9]{1,8}',recovery)
                and endpoint!='127.0.0.1','EXPLICIT_PRIVATE_RECOVERY_DATABASE_REQUIRED')
    database='demodb' if recovery is None else 'recoverydb_restore_'+recovery
    require(digest(config_path.read_bytes())==approval['PayloadSha256']['config.json']
            and config['Database']==database,'REVIEWED_CONFIG_REQUIRED')
    require(config['ExpectedEc2RoleName']==ROLE,'ROLE_CONFIG_MISMATCH')
    no_links(root)
    base=root/'etc/terragrunt-demo/sql-backup'; directory=base/'credentials'
    dropin=root/'etc/systemd/system/sql-backup.service.d'
    result={'Status':'CREDENTIAL_PLAN','ApprovalSha256':approval_sha,'SqlLogins':list(LOGINS),'NewSecretsManagerSecrets':0,
            'CredentialDirectory':str(directory),'CredentialMode':'root:root 0600; directory 0700; encrypted EBS',
            'SecretValuesPrinted':False,'SystemctlActions':[],'SqlEndpoint':endpoint}
    if not apply: return result
    require(confirmation==approval_sha,'EXACT_SECRET_BOOTSTRAP_CONFIRMATION_REQUIRED')
    require(os.geteuid()==0,'ROOT_REQUIRED')
    require(root==Path('/') or root.exists(),'EXISTING_FIXTURE_ROOT_REQUIRED')
    no_links(base); no_links(dropin)
    require(base.is_dir() and (base/'config.json').is_file() and (root/'opt/terragrunt-demo/sql-backup/install-receipt.json').is_file(),'PACKAGE_INSTALL_REQUIRED_FIRST')
    require((root/'etc/systemd/system/sql-backup.service').is_file(),'PACKAGE_UNITS_REQUIRED_FIRST')
    install_receipt=json.loads((root/'opt/terragrunt-demo/sql-backup/install-receipt.json').read_text())
    require(install_receipt['PackageSha256']==approval['Package']['Sha256'] and install_receipt['SourceCommit']==approval['SourceCommit'],'INSTALLED_PACKAGE_MISMATCH')
    require(digest((base/'config.json').read_bytes())==approval['PayloadSha256']['config.json'],'INSTALLED_CONFIG_DRIFT')
    require(not directory.exists(),'EXISTING_CREDENTIAL_BOOTSTRAP_REQUIRES_REVIEW')
    if dropin.exists():
        # Only the already hash-inventoried cohost integrity drop-in may precede us.
        import cohost
        require(install_receipt.get('ObserverPlacement')=='SQL_HOST','EXISTING_CREDENTIAL_BOOTSTRAP_REQUIRES_REVIEW')
        require({p.name for p in dropin.iterdir()}=={'sentinel-integrity.conf'},'FOREIGN_CREDENTIAL_DROPIN')
        cohost.verify(root)
    port=port or HostPort()
    identity=port.aws('sts','get-caller-identity')
    require(identity['Account']==ACCOUNT and identity['Arn'].startswith(f'arn:aws:sts::{ACCOUNT}:assumed-role/{ROLE}/'),'INSTANCE_ROLE_MISMATCH')
    if endpoint!='127.0.0.1':
        native=port.identity()
        require(native.get('accountId')==ACCOUNT and native.get('region')=='us-east-1'
            and native.get('instanceId')==approval['Runtime']['InstanceId'] and native.get('privateIp')==endpoint,
            'PRIVATE_ENDPOINT_HOST_MISMATCH')
    value=port.aws('secretsmanager','get-secret-value','--secret-id',SA)
    sa=value.get('SecretString','')
    require(isinstance(sa,str) and 1<=len(sa)<=4096 and '\n' not in sa and '\r' not in sa,'INVALID_SA_SECRET')
    backup_password='Synthetic!'+secrets.token_hex(24); verify_password='Synthetic!'+secrets.token_hex(24)
    directory.mkdir(mode=0o700); directory.chmod(0o700)
    receipt=directory/'bootstrap-receipt.json'
    proof={'SchemaVersion':1,'Status':'PREPARING_OR_UNKNOWN','ApprovalSha256':approval_sha,'Database':config['Database'],'Logins':list(LOGINS)}
    private_write(receipt,json.dumps(proof).encode())
    # A failure intentionally preserves the receipt and refuses blind retry.
    batch=sql_batch(config['Database'],backup_password,verify_password)
    if endpoint=='127.0.0.1': port.sql(sa,batch)
    else: port.sql(sa,batch,endpoint=endpoint)
    for name,user,password in [('backup-connection',LOGINS[0],backup_password),('verify-connection',LOGINS[1],verify_password)]:
        database=config['Database'] if name=='backup-connection' else 'master'
        connection=f'Server={endpoint},1433;Database={database};User ID={user};Password={password};Encrypt=True;TrustServerCertificate=True;Connect Timeout=10'
        private_write(directory/name,connection.encode())
    dropin.mkdir(mode=0o755,exist_ok=True)
    unit='[Service]\nLoadCredential=\nLoadCredential=backup-connection:/etc/terragrunt-demo/sql-backup/credentials/backup-connection\nLoadCredential=verify-connection:/etc/terragrunt-demo/sql-backup/credentials/verify-connection\n'
    private_write(dropin/'credentials.conf',unit.encode(),0o644)
    proof['Status']='PROVISIONED_NOT_STARTED'
    replacement=directory/'completed.json'; private_write(replacement,json.dumps(proof).encode()); os.replace(replacement,receipt)
    return dict(result,Status='PROVISIONED_NOT_STARTED')

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--approval',type=Path,required=True); parser.add_argument('--config',type=Path,required=True)
    parser.add_argument('--root',type=Path,default=Path('/')); parser.add_argument('--apply',action='store_true'); parser.add_argument('--confirm-secret-bootstrap')
    args=parser.parse_args()
    return operate(args.approval,args.config,args.root,args.apply,args.confirm_secret_bootstrap)

if __name__=='__main__':
    try: print(json.dumps(main(),separators=(',',':')))
    except Exception as error:
        print(json.dumps({'Status':'FAILED','Code':str(error) if isinstance(error,ValueError) else 'CREDENTIAL_BOOTSTRAP_FAILED_OR_UNKNOWN'}))
        raise SystemExit(1)
