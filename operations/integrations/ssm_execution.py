"""Offline status-receipt gate. No AWS calls, permission simulation or retries.

Execution of the status script alone never proves backup observation or delivery.
Inputs are preserved SendCommand intent/acceptance and GetCommandInvocation data.
"""
import datetime as dt
import json

def require_status_execution(intent, accepted, result):
    def need(value, code):
        if not value: raise ValueError(code)
    need(all(isinstance(v, dict) for v in (intent, accepted, result)), 'SSM_RECEIPT_SHAPE')
    need(all(isinstance(intent.get(k), str) and intent[k] for k in ('instance','document','documentVersion','atUtc')), 'SSM_INTENT_BINDING')
    # A command ID, Online node or successful API read is not execution proof.
    need(result.get('Status') == 'Success' and result.get('StatusDetails') == 'Success'
         and type(result.get('ResponseCode')) is int and result['ResponseCode'] == 0,
         'SSM_STATUS_NOT_EXECUTED_SUCCESSFULLY')
    need(intent.get('action') == 'status', 'SSM_WRONG_ACTION')
    need(bool(accepted.get('commandId')) and result.get('CommandId') == accepted['commandId']
         and result.get('InstanceId') == intent.get('instance')
         and result.get('DocumentName') == intent.get('document')
         and result.get('DocumentVersion') == intent.get('documentVersion')
         and result.get('PluginName') == 'ObserverControl', 'SSM_RESULT_BINDING')
    def timestamp(value):
        v = dt.datetime.fromisoformat(value.replace('Z', '+00:00'))
        need(v.tzinfo is not None, 'SSM_TIMESTAMP_ZONE')
        return v
    try:
        sent, start, end = [timestamp(v) for v in (intent['atUtc'], result['ExecutionStartDateTime'], result['ExecutionEndDateTime'])]
        need(sent <= start <= end, 'SSM_EXECUTION_ORDER')
        value = json.loads(result['StandardOutputContent'])
    except (KeyError, TypeError, AttributeError, json.JSONDecodeError):
        raise ValueError('SSM_EXECUTION_EVIDENCE_MISSING') from None
    need(isinstance(value, dict) and value.get('status') == 'OBSERVED'
         and type(value.get('timerActive')) is bool
         and type(value.get('serviceActiveOrUncertain')) is bool
         and value.get('mode') in ('healthy','missing','stale','fail')
         and value.get('timerStartedByTerraform') is False, 'SSM_STATUS_PAYLOAD')
    return {'execution': 'CONFIRMED_STATUS_ONLY', 'timerActive': value['timerActive'],
            'mode': value['mode'], 'backupAcceptance': False}
