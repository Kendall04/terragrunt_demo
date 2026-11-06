#!/usr/bin/python3
"""One-host DEV TLS installation. No secret material in arguments or output."""
import argparse, hashlib, json, os, pathlib, pwd, resource, subprocess, sys
PIN='206095fa0ba9e17a84c80eff5021db93d05e2dc377e982a64d517696ed21a1e7'
REGION='us-east-1'
ROLE='arn:aws:sts::341936017254:assumed-role/demo-dev-data-sql-ec2-role/'
PREFIX='arn:aws:secretsmanager:us-east-1:341936017254:secret:demo/dev/db/sql-tls-material-'
BASE=pathlib.Path('/var/opt/mssql/sslcert')

def run(args, data=None, env=None):
    p=subprocess.run(args,input=data,stdout=subprocess.PIPE,stderr=subprocess.PIPE,env=env,timeout=60,check=False)
    if p.returncode: raise RuntimeError('Local validation or command failed')
    return p.stdout

def validate_material(payload):
    if set(payload)!={'schema','certificate_pem','private_key_pem'} or payload['schema']!='ECS_DEV_SQL_TLS_V1':
        raise ValueError('Unexpected TLS payload')
    cert=payload['certificate_pem'].encode('ascii');key=payload['private_key_pem'].encode('ascii')
    if len(cert)>16000 or len(key)>32000 or b'PRIVATE KEY' in cert: raise ValueError('Invalid material')
    der=run(['openssl','x509','-outform','DER'],cert)
    if hashlib.sha256(der).hexdigest()!=PIN: raise ValueError('Certificate pin mismatch')
    run(['openssl','x509','-noout','-checkend','14400'],cert)
    pub=run(['openssl','x509','-pubkey','-noout'],cert)
    certpub=run(['openssl','pkey','-pubin','-outform','DER'],pub)
    keypub=run(['openssl','pkey','-pubout','-outform','DER'],key)
    if certpub!=keypub: raise ValueError('Certificate/key mismatch')
    # Only public certificate files are needed for chain, purpose, and hostname checks.
    import tempfile
    with tempfile.NamedTemporaryFile(prefix='sql-public-',suffix='.crt') as f:
        f.write(cert);f.flush()
        run(['openssl','verify','-CAfile',f.name,'-purpose','sslserver','-verify_hostname','sql.demo.internal',f.name])
    return cert,key

def get_material(secret,version):
    if not secret.startswith(PREFIX) or '/' in secret[len(PREFIX):] or not 32<=len(version)<=64:
        raise ValueError('Unexpected secret reference')
    from botocore.session import Session
    from botocore.config import Config
    s=Session();cfg=Config(retries={'total_max_attempts':1},connect_timeout=8,read_timeout=20)
    if not s.create_client('sts',region_name=REGION,config=cfg).get_caller_identity()['Arn'].startswith(ROLE):
        raise ValueError('Wrong recipient role')
    r=s.create_client('secretsmanager',region_name=REGION,config=cfg).get_secret_value(SecretId=secret,VersionId=version)
    if r['ARN']!=secret or r['VersionId']!=version: raise ValueError('Secret readback mismatch')
    return validate_material(json.loads(r['SecretString']))

def install(secret,version):
    if os.geteuid()!=0: raise ValueError('Root required')
    resource.setrlimit(resource.RLIMIT_CORE,(0,0));os.umask(0o077)
    if BASE.exists(): raise ValueError('Existing TLS directory; manual reconciliation required')
    run(['systemctl','is-active','--quiet','mssql-server'])
    who=pwd.getpwnam('mssql');cert,key=get_material(secret,version)
    BASE.mkdir(mode=0o700);os.chown(BASE,who.pw_uid,who.pw_gid)
    for name,data in [('sql.demo.internal.crt',cert),('sql.demo.internal.key',key)]:
        fd=os.open(BASE/name,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
        with os.fdopen(fd,'wb') as f:
            os.fchown(f.fileno(),who.pw_uid,who.pw_gid);f.write(data);f.flush();os.fsync(f.fileno())
    key=None;cert=None
    for name,value in [('network.tlscert',str(BASE/'sql.demo.internal.crt')),('network.tlskey',str(BASE/'sql.demo.internal.key')),('network.tlsprotocols','1.2'),('network.forceencryption','1')]:
        run(['/opt/mssql/bin/mssql-conf','set',name,value])
    run(['systemctl','restart','mssql-server']);run(['systemctl','is-active','--quiet','mssql-server'])
    # Public trust insertion on this SQL test host only; client image update is separate.
    trust=pathlib.Path('/usr/local/share/ca-certificates/ecs-sql-demo-20261104.crt')
    fd=os.open(trust,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o644)
    with os.fdopen(fd,'wb') as f:f.write((BASE/'sql.demo.internal.crt').read_bytes())
    run(['update-ca-certificates'])
    print(json.dumps({'installation':'PASS','certificateDER_SHA256':PIN,'forceEncryption':True,'keyMode':'0600','directoryMode':'0700','keyOwner':'mssql','secretVersion':version}))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--secret-arn',required=True);p.add_argument('--version-id',required=True);a=p.parse_args()
    try:install(a.secret_arn,a.version_id)
    except Exception:
        print('SQL_TLS_INSTALL_FAILED; details suppressed; no automatic retry',file=sys.stderr);sys.exit(1)
