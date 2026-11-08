#!/usr/bin/env python3
"""Installed portable observer entrypoint. Explicit contract binding; EC2 role only."""
import datetime as dt,hashlib,json,sys
from pathlib import Path
from types import SimpleNamespace
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
SQL=HERE.parent if (HERE.parent/'cohost.py').is_file() else HERE.parents[1]/'sql-backup'
sys.path.insert(0,str(SQL))
import bridge,publisher,signals

def validate(value,backup,contract_path=None):
 p=value.get('Portable');bridge.require(isinstance(p,dict) and set(p)=={'SchemaVersion','ContractSha256'} and type(p['SchemaVersion']) is int and p['SchemaVersion']==1,'PORTABLE_OPT_IN_REQUIRED')
 path=contract_path or HERE/'cohost-contract.json';raw=path.read_bytes();bridge.require(len(raw)<=65536 and hashlib.sha256(raw).hexdigest()==p['ContractSha256'],'PORTABLE_CONTRACT_HASH_MISMATCH')
 c=bridge.read_unique(raw.decode('utf-8'));bridge.require(set(c)=={'SchemaVersion','LambdaPackage','Bridge','Installation'} and c['SchemaVersion']==1,'EXACT_PORTABLE_CONTRACT_REQUIRED')
 b,m=c['Bridge'],c['Installation'];bridge.binding(b,m)
 bridge.require(value['Account']==m['account'] and value['Region']==m['region'] and value['Subject']==b['subject'] and m['deployment']==value['RunId'].replace('ecs-sentinel-','ecs-portable-',1),'COHOST_PORTABLE_BINDING_MISMATCH')
 bridge.require(value['PublishAttempts']==3 and value['ExpectedUp'] is True and value['WatchdogSeconds']==1200 and 60<=value['CadenceSeconds']<=300,'PORTABLE_CADENCE_AND_EXPECTATION_REQUIRED')
 bridge.require(backup['ProposedMaxAgeHours']==2 and next(x for x in m['monitors'] if x['id']==b['backupMonitor'])['maxAge']=='02:00:00','BACKUP_FRESHNESS_CONTRACT_REQUIRED')
 r=c['LambdaPackage'];bridge.require(r['configSha256']==hashlib.sha256((json.dumps(m,indent=2)+'\n').encode()).hexdigest() and r['syntheticTrial'] is True and r['executionAuthorized'] is False,'LAMBDA_CONFIG_BINDING_REQUIRED')
 return c

def arguments(value,backup,root=Path('/')):
 config=root/'etc/terragrunt-demo/sql-backup/config.json';base=root/'opt/terragrunt-demo/sql-backup'
 return SimpleNamespace(action='run',portable=True,aws=True,ec2_role=True,account=value['Account'],region=value['Region'],subject=value['Subject'],expires_at=value['ExpiresAt'],state_directory=root/'var/lib/terragrunt-demo-backup-observer',config=config,aws_cli=root/'usr/bin/aws',executable=base/'bin/SqlBackup',expected_up='true',repeat_after_seconds=value['ReminderSeconds'],observed_at=None,producer_job_receipt=root/backup['StagingDirectory'].lstrip('/')/'.service/last-job.json')

def run(value,backup,root=Path('/'),runner=None,clock=lambda:dt.datetime.now(dt.timezone.utc)):
 c=validate(value,backup);args=arguments(value,backup,root)
 options={'clock':clock}
 if runner is not None:options['runner']=runner # Test port only; CLI never selects it.
 return publisher.run(args,c['Bridge'],c['Installation'],**options)

def integration(value,backup):
 c=validate(value,backup);m=c['Installation'];window={'DateGreaterThanEquals':{'aws:CurrentTime':value['StartsAt']},'DateLessThan':{'aws:CurrentTime':value['ExpiresAt']}}
 policy={'Version':'2012-10-17','Statement':[{'Sid':'SqlCohostPortableReportOnly','Effect':'Allow','Action':'events:PutEvents','Resource':'arn:aws:events:'+m['region']+':'+m['account']+':event-bus/'+m['deployment'],'Condition':window|{'StringEquals':{'aws:RequestedRegion':m['region'],'events:source':'sentinel.report.'+c['Bridge']['producer'],'events:detail-type':'Sentinel Observation v1'}}}]}
 return {'SqlRoleArn':'arn:aws:iam::'+m['account']+':role/'+backup['ExpectedEc2RoleName'],'SqlRoleEventBridgeDelta':policy,'LegacySqsSendRequired':False,'RemoveOnlyOwnAdmittedLegacySqsDelta':True,'AdditionalObserverCloudResources':0,'ExternalSentinelRequired':True,'LambdaPackage':c['LambdaPackage'],'ExecutionAuthorized':False,'Installed':False}

def main():
 import cohost
 bridge.require(sys.argv[1:]==['run'],'EXACT_INSTALLED_ENTRYPOINT_REQUIRED');cohost.verify()
 value=signals.read(cohost.SETTINGS);backup=signals.read(cohost.CONFIG);print(json.dumps(run(value,backup),separators=(',',':')))
if __name__=='__main__':
 try:main()
 except Exception as e:
  print(json.dumps({'Status':'REFUSED','Code':str(e) if isinstance(e,(ValueError,signals.Refused)) else 'PORTABLE_COHOST_REFUSED'}));raise SystemExit(2)
