#!/usr/bin/python3
"""Read-only strict SQL TLS check; password enters only child environment."""
import json,os,resource,subprocess,sys
SA='arn:aws:secretsmanager:us-east-1:341936017254:secret:demo/dev/db/sql-sa-password-30fCjc'
def check():
 resource.setrlimit(resource.RLIMIT_CORE,(0,0))
 from botocore.session import Session
 from botocore.config import Config
 s=Session();cfg=Config(retries={'total_max_attempts':1},connect_timeout=8,read_timeout=20)
 identity=s.create_client('sts',region_name='us-east-1',config=cfg).get_caller_identity()['Arn']
 if not identity.startswith('arn:aws:sts::341936017254:assumed-role/demo-dev-data-sql-ec2-role/'):raise ValueError('role')
 secret=s.create_client('secretsmanager',region_name='us-east-1',config=cfg).get_secret_value(SecretId=SA)
 env={**os.environ,'SQLCMDPASSWORD':secret['SecretString']};secret=None
 q="SET NOCOUNT ON; SELECT CASE WHEN encrypt_option=N'TRUE' THEN 1 ELSE 0 END FROM sys.dm_exec_connections WHERE session_id=@@SPID; SELECT is_disabled FROM sys.sql_logins WHERE name=N'recovery_app'; SELECT COUNT(*) FROM sys.sql_logins WHERE name IN (N'recovery_app',N'recovery_migrator'); SELECT SERVERPROPERTY('Edition'); SELECT SERVERPROPERTY('ProductMajorVersion');"
 cmd=['/opt/mssql-tools18/bin/sqlcmd','-S','tcp:127.0.0.1,1433','-U','sa','-N','-F','sql.demo.internal','-b','-h','-1','-W','-l','15','-Q',q]
 r=subprocess.run(cmd,env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=40)
 if r.returncode:raise RuntimeError('Strict SQL login or TLS rejected')
 rows=[x.strip() for x in r.stdout.decode().splitlines() if x.strip()]
 if len(rows)!=5 or rows[:3]!=['1','1','2'] or 'Express' not in rows[3] or rows[4]!='16':raise RuntimeError('Runtime separation, edition or encryption evidence failed')
 wrong=cmd.copy();wrong[wrong.index('sql.demo.internal')]='wrong.demo.internal'
 n=subprocess.run(wrong,env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=40);env.pop('SQLCMDPASSWORD',None)
 text=(n.stdout+n.stderr).decode(errors='replace').lower()
 if n.returncode==0 or not any(x in text for x in ['certificate','hostname','target principal','ssl provider']):raise RuntimeError('Wrong hostname was not demonstrably rejected')
 print(json.dumps({'strictTDSHandshake':'PASS','Encrypt':True,'TrustServerCertificate':False,'HostNameInCertificate':'sql.demo.internal','encryptedConnectionObserved':True,'wrongHostnameRejected':True,'runtimeDisabled':True,'distinctRuntimeAndMigrator':True,'SQLServerEdition':rows[3],'ProductMajorVersion':rows[4],'migrationsExecuted':False}))
if __name__=='__main__':
 try:check()
 except Exception:print('STRICT_SQL_TLS_PROBE_FAILED; sensitive diagnostics suppressed',file=sys.stderr);sys.exit(1)
