"""Synthetic bridge fixtures for real upstream in-process tests. No native health proof."""
from pathlib import Path
import argparse,json,sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from test_bridge import configs,example,T
import bridge
p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args();assert not a.output.exists();a.output.mkdir(parents=True)
c,m=configs();(a.output/'sentinel.json').write_text(json.dumps(m,indent=2)+'\n',encoding='utf-8')
for status in ['HEALTHY','STALE','FAILED','MISSING','UNKNOWN','MAINTENANCE']:
 entries=bridge.project(json.dumps(example(status)),c,m,T,'local-replay');(a.output/(status.lower()+'.json')).write_text(json.dumps(entries,indent=2)+'\n',encoding='utf-8')
(a.output/'PROVENANCE.json').write_text(json.dumps({'input':'SYNTHETIC_LOCAL_RECEIPT_REPLAY','healthChecksActuallyRun':False,'awsCalls':0,'sqlConnections':0,'nativeAcceptance':False},indent=2)+'\n',encoding='utf-8')
print(json.dumps({'fixtures':6,'mode':'SYNTHETIC_LOCAL_RECEIPT_REPLAY','awsCalls':0}))
