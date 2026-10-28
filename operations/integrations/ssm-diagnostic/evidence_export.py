"""Bounded CloudWatch export of validated diagnostic records; no AWS client."""
import datetime as dt
import json
import re
from collector import validate, validate_record

MAX_EVENTS = 120
MAX_BYTES = 2 * 1024 * 1024
MAX_PAGES = 128


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':')).encode('utf-8')


def export_boot_events(fetch_page, config, instance_id, *,
                       max_events=MAX_EVENTS, max_bytes=MAX_BYTES, max_pages=MAX_PAGES):
    """Follow even empty pages. Never retry, export tokens or retain raw messages.

    Limits may only be reduced. Reserve 1024 bytes for the bounded envelope;
    SerializedBytes measures the complete returned UTF-8 JSON, including itself.
    Absence from any capture is not proof of non-delivery to the agent.
    """
    validate(config)
    if not re.fullmatch(r'i-[a-f0-9]{17}', instance_id):
        raise ValueError('EXPORT_INSTANCE')
    if not (1 <= max_events <= MAX_EVENTS and 1024 <= max_bytes <= MAX_BYTES
            and 1 <= max_pages <= MAX_PAGES):
        raise ValueError('EXPORT_LIMITS')
    safe, seen_events, seen_tokens = [], {}, set()
    pages, duplicates, event_bytes, token = 0, 0, 2, None
    reason = 'PAGE_LIMIT'
    while pages < max_pages:
        args = {'logGroupName': config['log_group'], 'logStreamNames': ['boot'],
                'limit': max_events - len(safe)}
        if token is not None:
            args['nextToken'] = token
        try:
            page = fetch_page(**args)
        except Exception:
            reason = 'FETCH_FAILED_NO_RETRY'
            break
        pages += 1
        events = page.get('events')
        if not isinstance(events, list) or len(events) > max_events:
            raise ValueError('EXPORT_PAGE_SHAPE')
        for event in events:
            message = event.get('message')
            if not isinstance(message, str) or len(message.encode('utf-8')) > 32768:
                raise ValueError('EXPORT_MESSAGE_BOUND')
            row = json.loads(message)
            validate_record(config, row)
            if row['instanceId'] != instance_id:
                raise ValueError('EXPORT_INSTANCE')
            event_id = event.get('eventId')
            if not isinstance(event_id, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,128}', event_id):
                raise ValueError('EXPORT_EVENT_ID')
            if any(type(event.get(k)) is not int or event[k] < 0
                   for k in ('timestamp', 'ingestionTime')):
                raise ValueError('EXPORT_EVENT_TIME')
            entry = {'EventId': event_id, 'Timestamp': event['timestamp'],
                     'IngestionTime': event['ingestionTime'], 'Record': row}
            encoded = canonical(entry)
            if event_id in seen_events:
                if seen_events[event_id] != encoded:
                    raise ValueError('EXPORT_EVENT_ID_CONFLICT')
                duplicates += 1
                continue
            if len(safe) == max_events:
                reason = 'EVENT_LIMIT'
                break
            if event_bytes + len(encoded) + 1 > max_bytes - 1024:
                reason = 'BYTE_LIMIT'
                break
            safe.append(entry)
            seen_events[event_id] = encoded
            event_bytes += len(encoded) + 1
        else:
            next_token = page.get('nextToken')
            if not next_token:
                reason = 'END_OF_PAGINATION'
                break
            if not isinstance(next_token, str) or len(next_token) > 4096:
                raise ValueError('EXPORT_TOKEN_SHAPE')
            if next_token in seen_tokens:
                reason = 'REPEATED_TOKEN'
                break
            if len(safe) == max_events:
                reason = 'EVENT_LIMIT'
                break
            seen_tokens.add(next_token)
            token = next_token
            continue
        break
    result = {'AtUtc': dt.datetime.now(dt.timezone.utc).isoformat(),
              'Run': config['run'], 'InstanceId': instance_id, 'Events': safe,
              'RawLogLinesExported': False,
              'TruncatedByApi': reason != 'END_OF_PAGINATION',
              'Capture': {'PaginationExhausted': reason == 'END_OF_PAGINATION',
                          'StopReason': reason, 'PagesRead': pages,
                          'DuplicateEventsSkipped': duplicates,
                          'EventLimit': max_events, 'ByteLimit': max_bytes,
                          'PageLimit': max_pages, 'SerializedBytes': 0}}
    # Reach the fixed point because this byte count is itself serialized.
    for _ in range(4):
        size = len(canonical(result))
        if result['Capture']['SerializedBytes'] == size:
            break
        result['Capture']['SerializedBytes'] = size
    if len(canonical(result)) != result['Capture']['SerializedBytes'] or size > max_bytes:
        raise ValueError('EXPORT_ENVELOPE_BOUND')
    return result
