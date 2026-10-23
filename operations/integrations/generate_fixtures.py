#!/usr/bin/env python3
"""Fixtures come from the actual ECS observer transition, not a simulated Sentinel API."""
import argparse,importlib.util,json,sys
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--observer-root',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
sys.path.insert(0,str(a.observer_root.resolve()));import observer
out=a.output;out.mkdir(parents=True,exist_ok=True)
subject='sql-backup-test';scope='a'*64
previous=None
for name,status,observed,last in [('failed','FAILED','2026-10-23T17:00:00Z',None),('missing','MISSING','2026-10-23T17:01:00Z',None),('stale','STALE','2026-10-23T17:02:00Z','2026-10-23T12:00:00Z'),('unchanged','STALE','2026-10-23T17:02:30Z','2026-10-23T12:00:00Z'),('unknown','UNKNOWN','2026-10-23T17:03:00Z',None),('recovered','HEALTHY','2026-10-23T17:04:00Z','2026-10-23T17:03:30Z'),('baseline','HEALTHY','2026-10-23T17:05:00Z','2026-10-23T17:04:30Z'),('maintenance','MAINTENANCE','2026-10-23T17:06:00Z',None)]:
 current=observer.health({'Status':status,'Code':observer.signals.PAIRS[status],'LastSuccessUtc':last},observed,0 if status in ('HEALTHY','MAINTENANCE') else 1)
 previous,event=observer.transition(current,observed,previous,subject,scope,0)
 event.update(Evaluation='EXPECTED_UP_FALSE' if status=='MAINTENANCE' else 'LOCAL_RECEIPT_REPLAY',CheckInvoked=False)
 (out/(name+'.json')).write_text(json.dumps(event,separators=(',',':'))+'\n',encoding='utf-8')
print('8 actual observer transition fixtures generated')
