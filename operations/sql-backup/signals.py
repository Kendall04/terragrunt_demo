#!/usr/bin/env python3
"""Render bounded existing backup receipts as local log JSON. No delivery/AWS."""
import argparse
import datetime as dt
import json
import math
from pathlib import Path
import re

class Refused(ValueError): pass

PAIRS = {'HEALTHY': 'RECENT_REMOTE_COMMIT', 'FAILED': 'LAST_ATTEMPT_FAILED',
         'MISSING': 'NO_REMOTE_COMMIT', 'STALE': 'REMOTE_BACKUP_TOO_OLD',
         'UNKNOWN': 'REMOTE_STORAGE_NOT_CHECKED', 'MAINTENANCE': 'NOT_EXPECTED_UP'}

def utc(value):
    if not isinstance(value, str): raise Refused('INVALID_UTC')
    match = re.fullmatch(r'(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})(?:\.(\d{1,7}))?(Z|\+00:00)', value)
    if not match: raise Refused('INVALID_UTC')
    try: return dt.datetime.fromisoformat(match[1] + ('.' + match[2][:6] if match[2] else '') + '+00:00')
    except ValueError: raise Refused('INVALID_UTC') from None

def read(path):
    path = Path(path)
    if not path.is_absolute() or any(p.is_symlink() for p in (path, *path.parents)): raise Refused('SAFE_FILE_REQUIRED')
    with path.open('rb') as stream: body = stream.read(65537)
    if len(body) > 65536: raise Refused('RECEIPT_TOO_LARGE')
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result: raise Refused('DUPLICATE_FIELD')
            result[key] = value
        return result
    try: value = json.loads(body, object_pairs_hook=unique)
    except (ValueError, UnicodeError): raise Refused('INVALID_RECEIPT_JSON') from None
    if not isinstance(value, dict): raise Refused('OBJECT_REQUIRED')
    return value

def render(kind, value, observed, exit_code=None):
    now = utc(observed)
    if kind == 'health':
        if set(value) - {'Status', 'Code', 'LastSuccessUtc'} or not {'Status','Code'} <= set(value): raise Refused('HEALTH_FIELDS')
        status, code = value['Status'], value['Code']
        if not isinstance(status, str) or PAIRS.get(status) != code: raise Refused('HEALTH_PAIR')
        if type(exit_code) is not int or exit_code != (0 if status in ('HEALTHY','MAINTENANCE') else 1): raise Refused('EXIT_STATUS_MISMATCH')
        latest = value.get('LastSuccessUtc')
        if status in ('HEALTHY','STALE') and latest is None: raise Refused('SUCCESS_TIME_REQUIRED')
        if latest is not None and utc(latest) > now: raise Refused('FUTURE_EVIDENCE')
        severity = 'OK' if status == 'HEALTHY' else 'MAINTENANCE' if status == 'MAINTENANCE' else 'UNKNOWN' if status == 'UNKNOWN' else 'ATTENTION'
    elif kind == 'job':
        if set(value) - {'Status','Utc','Code','PreviousOutcome'} or not {'Status','Utc'} <= set(value): raise Refused('JOB_FIELDS')
        status = value['Status']; stamp = value['Utc']
        if type(stamp) not in (int,float) or not math.isfinite(stamp) or stamp < 0 or stamp > now.timestamp(): raise Refused('INVALID_JOB_TIME')
        pairs = {'REMOTE_VERIFIED_CLEANUP_VERIFIED':('JOB_COMPLETED','OK'), 'FAILED_OR_UNCONFIRMED':('JOB_FAILED_OR_UNCONFIRMED','ATTENTION'), 'UNKNOWN':('JOB_OUTCOME_UNKNOWN','UNKNOWN'), 'STARTED':('JOB_IN_PROGRESS_NOT_SUCCESS','UNKNOWN'), 'OPERATOR_RESUMED':('OPERATOR_RESUMED_NOT_SUCCESS','UNKNOWN')}
        if not isinstance(status,str) or status not in pairs: raise Refused('JOB_STATUS')
        if value.get('Code') not in (None,'CLIENT_DEADLINE'): raise Refused('JOB_CODE')
        if value.get('PreviousOutcome') is not None and value['PreviousOutcome'] not in pairs: raise Refused('JOB_PREVIOUS_OUTCOME')
        code, severity = pairs[status]; latest = None
    else: raise Refused('SIGNAL_KIND')
    return {'SchemaVersion':1,'Evaluation':'LOCAL_RECEIPT_REPLAY','Source':'SqlBackup.'+kind,'Status':status,'Code':code,'Severity':severity,'ObservedUtc':observed,'LastSuccessUtc':latest,'Delivery':'NONE','SentinelIntegrated':False,'RemediationAllowed':False}

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('kind',choices=('health','job'));p.add_argument('--receipt',required=True,type=Path);p.add_argument('--observed-at',required=True);p.add_argument('--exit-code',type=int)
    a=p.parse_args();print(json.dumps(render(a.kind,read(a.receipt),a.observed_at,a.exit_code),separators=(',',':')))

if __name__=='__main__':
    try: main()
    except Exception as error:
        print(json.dumps({'Status':'REFUSED','Code':str(error) if isinstance(error,Refused) else 'LOCAL_SIGNAL_FAILED'}));raise SystemExit(1)
