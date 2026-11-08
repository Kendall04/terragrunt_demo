"""Pure observer-to-portable Report projection. No AWS, credentials or state writes."""
from pathlib import Path
import datetime as dt
import hashlib,json,re,sys
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'sql-backup'))
import signals

FIELDS=set('SchemaVersion Source Subject ObservedUtc Status Code Severity LastSuccessUtc ProducerFailureCoverage Emit Reason Delivery SentinelIntegrated RemediationAllowed Evaluation CheckInvoked'.split())
def require(ok,code):
 if not ok:raise ValueError(code)
def stable(*parts):return hashlib.sha256(json.dumps(parts,separators=(',',':'),ensure_ascii=True,sort_keys=True).encode()).hexdigest()
def stamp(at):return at.isoformat().replace('+00:00','Z')
def read_unique(raw):
 require(isinstance(raw,str) and len(raw.encode())<=65536,'BOUNDED_JSON_REQUIRED')
 def unique(pairs):
  result={}
  for k,v in pairs:
   require(k not in result,'DUPLICATE_FIELD');result[k]=v
  return result
 value=json.loads(raw,object_pairs_hook=unique);require(isinstance(value,dict),'OBJECT_REQUIRED');return value
def binding(config,manifest):
 require(set(config)==set('schemaVersion subject producer backupMonitor telemetryMonitor includeCopyOnly backupPolicy executionAuthorized'.split()),'EXACT_BRIDGE_CONFIG_REQUIRED')
 require(type(config['schemaVersion']) is int and config['schemaVersion']==1 and config['executionAuthorized'] is False,'LOCAL_PROJECTION_NOT_EXECUTION_AUTHORITY')
 require(config['includeCopyOnly'] is True and config['backupPolicy']=='FULL_COPY_ONLY_CHECKSUM','EXPLICIT_COPY_ONLY_POLICY_REQUIRED')
 require(re.fullmatch('[a-z0-9][a-z0-9._-]{0,63}',config['subject']) is not None,'SUBJECT_REQUIRED')
 require(manifest['account']=='341936017254' and manifest['region']=='us-east-1','EXACT_ACCOUNT_REGION_REQUIRED')
 require(len(manifest['monitors'])==2,'TWO_EXPECTATIONS_REQUIRED')
 monitors={m['id']:m for m in manifest['monitors']};require(len(monitors)==2 and config['backupMonitor']!=config['telemetryMonitor'],'DISTINCT_MONITORS_REQUIRED')
 for key,kind,assurance in [('backupMonitor','sql-backup','Artifact'),('telemetryMonitor','report','Reported')]:
  m=monitors[config[key]]
  require(m['kind']==kind and m['model']=='Freshness' and m['sources']==[config['producer']] and m['requiredAssurance']==assurance,'EXACT_MONITOR_PROFILE_REQUIRED')
  require(isinstance(m['generation'],str) and bool(m['generation']) and isinstance(m['resource'],str) and bool(m['resource']),'RESOURCE_GENERATION_REQUIRED')
 require(monitors[config['backupMonitor']]['selector']=='full','FULL_BACKUP_REQUIRED')
 return monitors
def project(raw,config,manifest,received_at,mode):
 """Return two stable EventBridge entries; upstream CLR still validates the full manifest."""
 monitors=binding(config,manifest);event=read_unique(raw);require(set(event)==FIELDS,'EXACT_OBSERVER_FIELDS_REQUIRED')
 require(type(event['SchemaVersion']) is int and event['SchemaVersion']==1 and event['Source']=='SqlBackup.Observer' and event['Subject']==config['subject'],'EXACT_OBSERVER_IDENTITY_REQUIRED')
 require(event['Delivery']=='NONE' and event['SentinelIntegrated'] is False and event['RemediationAllowed'] is False,'NO_FALSE_DELIVERY_OR_REMEDIATION')
 observed=signals.utc(event['ObservedUtc']);received=signals.utc(received_at);require(observed<=received and observed>=dt.datetime(1970,1,1,tzinfo=dt.timezone.utc),'OBSERVATION_TIME_REQUIRED')
 status=event['Status'];health=signals.render('health',{k:event[k] for k in ('Status','Code','LastSuccessUtc')},event['ObservedUtc'],0 if status in ('HEALTHY','MAINTENANCE') else 1)
 require(health['Severity']==event['Severity'],'EXACT_SEVERITY_REQUIRED')
 require(type(event['Emit']) is bool and type(event['CheckInvoked']) is bool,'BOOLEAN_FIELDS_REQUIRED')
 require(event['ProducerFailureCoverage'] in ('LOCAL_RECEIPT_ONLY','NOT_PROVIDED'),'PRODUCER_COVERAGE_REQUIRED')
 reason=event['Reason']
 require((reason=='MAINTENANCE')==(status=='MAINTENANCE'),'MAINTENANCE_PAIR_REQUIRED')
 require((event['Emit'] and (reason=='RECOVERED' if status=='HEALTHY' else status!='MAINTENANCE' and reason in ('INITIAL_ATTENTION','CONDITION_CHANGED','REMINDER_DUE'))) or (not event['Emit'] and reason in ('UNCHANGED','BASELINE_HEALTHY','MAINTENANCE')),'REASON_PAIR_REQUIRED')
 require(reason!='BASELINE_HEALTHY' or status=='HEALTHY','BASELINE_PAIR_REQUIRED')
 evaluation=event['Evaluation'];require(mode in ('local-replay','check-result'),'EXPLICIT_EVALUATION_MODE_REQUIRED')
 expected='LOCAL_RECEIPT_REPLAY' if mode=='local-replay' else 'CHECK_COMMAND_RESULT'
 require((status=='MAINTENANCE' and evaluation=='EXPECTED_UP_FALSE' and not event['CheckInvoked']) or (evaluation==expected and event['CheckInvoked']==(mode=='check-result')),'EVALUATION_MODE_MISMATCH')
 if status=='MAINTENANCE':return [] # Caller must separately disable the external expectation; no fabricated success.
 backup=monitors[config['backupMonitor']];telemetry=monitors[config['telemetryMonitor']]
 valid=event['ProducerFailureCoverage']=='LOCAL_RECEIPT_ONLY' and status in ('HEALTHY','STALE')
 latest=event['LastSuccessUtc'];data=latest if latest is not None else event['ObservedUtc']
 # FAILED is intentionally ambiguous in the existing FAILED_OR_UNCONFIRMED producer receipt.
 # It must alert as unverifiable, not become a newly invented confirmed failure.
 verdict='Pass' if valid else 'Unknown'
 detail='Full COPY_ONLY checksum policy; '+('remote commit observed' if valid else 'backup success not established')+'. '+event['Code']
 identity=stable('ecs-portable-observation-v1',manifest['deployment'],manifest['consumer'],config['subject'],event)
 reports=[]
 for m,v,at,assurance,run,why in [(backup,verdict,data,'Artifact' if valid else 'Reported',stable('backup-data',config['subject'],latest) if latest else identity,detail),(telemetry,'Pass',event['ObservedUtc'],'Reported',identity,'Observer heartbeat only; not SQL or backup health.')]:
  report={'schemaVersion':1,'monitor':m['id'],'producer':config['producer'],'id':stable(identity,m['id']),'resource':m['resource'],'generation':m['generation'],'observedAt':stamp(observed),'dataAt':stamp(signals.utc(at)),'verdict':v,'assurance':assurance,'runId':run,'detail':why,'backupType':'full' if m['kind']=='sql-backup' else None}
  reports.append({'EventBusName':manifest['deployment'],'Source':'sentinel.report.'+config['producer'],'DetailType':'Sentinel Observation v1','Detail':json.dumps(report,separators=(',',':'))})
 return reports
