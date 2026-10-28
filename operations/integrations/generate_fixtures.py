#!/usr/bin/env python3
"""Fixtures come from the actual ECS observer transition, not a simulated Sentinel API."""
import argparse,importlib.util,json,sys,re
from datetime import datetime,timedelta,timezone
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--observer-root',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--anchor-utc',default='2026-10-23T17:00:00Z');p.add_argument('--subject',default='sql-backup-test');a=p.parse_args()
sys.path.insert(0,str(a.observer_root.resolve()));import observer
out=a.output;out.mkdir(parents=True,exist_ok=True)
subject=a.subject;scope='a'*64
if not re.fullmatch(r'[a-z0-9][a-z0-9._-]{0,63}',subject):p.error('invalid synthetic subject')
try:
 anchor=datetime.strptime(a.anchor_utc,'%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=timezone.utc)
except ValueError:p.error('anchor must be an explicit UTC second ending Z')
delta=anchor-datetime(2026,10,23,17,tzinfo=timezone.utc)
def shift(raw):
 return None if raw is None else (datetime.strptime(raw,'%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=timezone.utc)+delta).strftime('%Y-%m-%dT%H:%M:%SZ')
previous=None
for name,status,observed,last in [('failed','FAILED','2026-10-23T17:00:00Z',None),('failed-unchanged','FAILED','2026-10-23T17:00:10Z',None),('failed-reminder','FAILED','2026-10-23T17:00:20Z',None),('missing','MISSING','2026-10-23T17:01:00Z',None),('stale','STALE','2026-10-23T17:02:00Z','2026-10-23T12:00:00Z'),('unchanged','STALE','2026-10-23T17:02:30Z','2026-10-23T12:00:00Z'),('unknown','UNKNOWN','2026-10-23T17:03:00Z',None),('recovered','HEALTHY','2026-10-23T17:04:00Z','2026-10-23T17:03:30Z'),('baseline','HEALTHY','2026-10-23T17:05:00Z','2026-10-23T17:04:30Z'),('maintenance','MAINTENANCE','2026-10-23T17:06:00Z',None),('recurrence','FAILED','2026-10-23T17:07:00Z',None),('recovered2','HEALTHY','2026-10-23T17:08:00Z','2026-10-23T17:07:30Z'),('confirmed2','HEALTHY','2026-10-23T17:09:00Z','2026-10-23T17:08:30Z')]:
 observed,last=shift(observed),shift(last)
 current=observer.health({'Status':status,'Code':observer.signals.PAIRS[status],'LastSuccessUtc':last},observed,0 if status in ('HEALTHY','MAINTENANCE') else 1)
 previous,event=observer.transition(current,observed,previous,subject,scope,15 if name=='failed-reminder' else 0)
 event.update(Evaluation='EXPECTED_UP_FALSE' if status=='MAINTENANCE' else 'LOCAL_RECEIPT_REPLAY',CheckInvoked=False)
 (out/(name+'.json')).write_text(json.dumps(event,separators=(',',':'))+'\n',encoding='utf-8')
print('13 actual observer transition fixtures generated')
