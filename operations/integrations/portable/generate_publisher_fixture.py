"""Real publisher/journal with collector and CLI doubles, for upstream ingress replay."""
import argparse,datetime as dt,json,subprocess,sys,tempfile
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0,str(Path(__file__).resolve().parent))
import publisher
from test_bridge import configs,example,T
p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args();assert not a.output.exists()
c,m=configs();now=dt.datetime.fromisoformat(T.replace('Z','+00:00'));calls=[];accepted=[]
with tempfile.TemporaryDirectory() as temp:
 root=Path(temp).resolve();backup=root/'backup.json';backup.write_text('{"Database":"synthetic"}')
 args=SimpleNamespace(action='run',aws=True,ec2_role=True,portable=True,account=m['account'],region=m['region'],subject=c['subject'],expires_at=(now+dt.timedelta(hours=23)).isoformat(),state_directory=root/'state',config=backup,aws_cli=Path(sys.executable).resolve())
 def collector():e=example();e.update(Evaluation='CHECK_COMMAND_RESULT',CheckInvoked=True);return e
 def transport(command,**options):
  entries=json.loads(command[command.index('--entries')+1]);calls.append(entries)
  if len(calls)==1:accepted.append(entries[0]);return subprocess.CompletedProcess(command,0,b'{"FailedEntryCount":1,"Entries":[{"EventId":"local-backup"},{"ErrorCode":"ThrottlingException"}]}',b'')
  assert entries==[calls[0][1]];accepted.append(entries[0]);return subprocess.CompletedProcess(command,0,b'{"FailedEntryCount":0,"Entries":[{"EventId":"local-heartbeat"}]}',b'')
 first=publisher.run(args,c,m,transport,lambda:now,collector);second=publisher.run(args,c,m,transport,lambda:now,collector)
 assert first['Status']=='PENDING' and second['Status']=='ACCEPTED' and second['Attempts']==3
 # Network delivery may reverse order or duplicate already accepted entries.
 a.output.write_text(json.dumps([accepted[1],accepted[0],accepted[0]],indent=2)+'\n',encoding='utf-8')
print(json.dumps({'status':'PASS','transportAttemptsPerEntry':3,'requests':2,'replayedEntries':3,'collectorAndCli':'SYNTHETIC_DOUBLES','awsCalls':0}))
