"""Closed source-scope proofs, never evaluated IAM grants or Terraform execution.

Every declaration stays in discovery. A proof can only establish that a control
cannot affect a particular queried action/identity; unresolved inputs stay unknown.
"""
import json
import re
from evaluator import Unsupported, matches


def object_fields(text):
    from source import split_top
    text = text.strip()
    if not (text.startswith('{') and text.endswith('}')):
        raise Unsupported('expected closed object')
    result = {}
    for comma in split_top(text[1:-1]):
        for entry in split_top(comma, '\n'):
            m = re.fullmatch(r'\s*("(?:\\.|[^"\\])*"|[A-Za-z_]\w*)\s*=\s*([\s\S]+)', entry)
            if not m:
                raise Unsupported('unsupported object member')
            key = json.loads(m[1]) if m[1].startswith('"') else m[1]
            if key in result:
                raise Unsupported('duplicate object member')
            result[key] = m[2].strip()
    return result


def finite_keys(expression, local_values, directory, active=()):
    """Only finite literal sets/maps, unique local aliases and no evaluation."""
    expression = expression.strip()
    m = re.fullmatch(r'local\.(\w+)', expression)
    if m:
        key = (directory, m[1])
        if key in active or not isinstance(local_values.get(key), str):
            raise Unsupported('missing/ambiguous/cyclic finite set')
        return finite_keys(local_values[key], local_values, directory, active + (key,))
    if expression.startswith('toset(') and expression.endswith(')'):
        values = json.loads(expression[6:-1])
        if not isinstance(values, list) or not values or len(set(values)) != len(values):
            raise Unsupported('nonunique or empty finite set')
    elif expression.startswith('{'):
        fields = object_fields(expression)
        # Maps used here must have literal values, not unexamined computations.
        for v in fields.values():
            if not isinstance(json.loads(v), (str, int, bool)):
                raise Unsupported('nonliteral finite map')
        values = list(fields)
    else:
        raise Unsupported('unsupported finite expansion')
    if len(values) > 64 or not all(isinstance(v, str) and re.fullmatch(r'[A-Za-z0-9_+=,.@-]{1,128}', v) for v in values):
        raise Unsupported('unsafe finite key')
    return tuple(sorted(values))


def scalar_expression(text):
    """Recognize references/literals, not their values or arbitrary function calls."""
    text = text.strip()
    if text.startswith('"'):
        value = json.loads(text)
        if not isinstance(value, str) or '%{' in value or '$${' in value:
            raise Unsupported('unsupported scalar template')
        rest = re.sub(r'\$\{[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)+(?:\[(?:"[A-Za-z0-9_-]+"|each\.key|[0-9]+)\])?(?:\.[A-Za-z_]\w*)*\}', '', value)
        if '${' in rest:
            raise Unsupported('unsupported scalar interpolation')
        return
    if not re.fullmatch(r'[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)+(?:\[(?:"[A-Za-z0-9_-]+"|each\.key|[0-9]+)\])?(?:\.[A-Za-z_]\w*)*', text):
        raise Unsupported('unsupported scalar expression')


def list_expression(text):
    from source import split_top
    text = text.strip()
    if text.startswith('concat(') and text.endswith(')'):
        for arg in split_top(text[7:-1]):
            list_expression(arg)
    elif text.startswith('[') and text.endswith(']'):
        inside = text[1:-1].strip()
        m = re.fullmatch(r'for\s+(\w+)\s+in\s+([A-Za-z_]\w*(?:\.\w+)+)\s*:\s*(\w+)\.(\w+)', inside)
        if m:
            if m[1] != m[3]:
                raise Unsupported('unbound list comprehension')
        else:
            for value in split_top(inside):
                scalar_expression(value)
    else:
        # Resource splats have a fixed syntactic relationship, no arbitrary code.
        if not re.fullmatch(r'aws_\w+\.\w+\[\*\]\.\w+', text):
            raise Unsupported('unsupported list expression')


def scalar_or_list(text):
    if text.startswith(('[', 'concat(')) or '[*]' in text:
        list_expression(text)
    else:
        scalar_expression(text)


def resource_policy_scope(body, typ):
    """Validate a small complete source grammar before deriving action domains.

    Principal/Condition are checked structurally but not claimed to grant. For
    matching actions, the policy remains UNKNOWN until resource/context binding.
    """
    from source import attributes, blocks, split_top
    children, rest = blocks(body)
    if children:
        raise Unsupported('policy resource has execution/nested hook')
    attrs = attributes(rest)
    target = {'aws_sns_topic_policy': 'arn', 'aws_s3_bucket_policy': 'bucket', 'aws_sqs_queue_policy': 'queue_url'}[typ]
    if set(attrs) - {target, 'policy', 'count', 'for_each'} or not {target, 'policy'} <= set(attrs):
        raise Unsupported('unmodeled policy resource field')
    scalar_expression(attrs[target])
    expr = attrs['policy']
    if not (expr.startswith('jsonencode(') and expr.endswith(')')):
        raise Unsupported('unmodeled resource policy source')
    doc = object_fields(expr[11:-1])
    if set(doc) - {'Version', 'Id', 'Statement'} or not {'Version', 'Statement'} <= set(doc) or doc['Version'] != '"2012-10-17"':
        raise Unsupported('unmodeled policy envelope')
    if 'Id' in doc:
        scalar_expression(doc['Id'])
    statements = doc['Statement'].strip()
    conditional = re.fullmatch(r'length\(([A-Za-z_]\w*(?:\.\w+)+)\)\s*>\s*0\s*\?\s*(\[[\s\S]*\])\s*:\s*\[\s*\]', statements)
    if conditional:
        statements = conditional[2]  # union of both possible branches, never assume the condition
    if not (statements.startswith('[') and statements.endswith(']')):
        raise Unsupported('unmodeled policy statement construction')
    actions = []
    for raw in split_top(statements[1:-1]):
        st = object_fields(raw)
        if set(st) - {'Sid', 'Effect', 'Principal', 'Action', 'Resource', 'Condition'} or not {'Effect', 'Principal', 'Action', 'Resource'} <= set(st):
            raise Unsupported('unmodeled policy statement fields')
        if st['Effect'] not in ('"Allow"', '"Deny"'):
            raise Unsupported('unmodeled effect')
        aa = json.loads(st['Action']); aa = aa if isinstance(aa, list) else [aa]
        if not aa or not all(isinstance(a, str) and (a == '*' or re.fullmatch(r'[A-Za-z0-9*-]+:[A-Za-z0-9*?]+', a)) for a in aa):
            raise Unsupported('unmodeled action set')
        actions.extend(aa)
        scalar_or_list(st['Resource'])
        if st['Principal'] != '"*"':
            principal = object_fields(st['Principal'])
            if not principal or set(principal) - {'Service', 'AWS'}:
                raise Unsupported('unmodeled principal')
            for v in principal.values():
                scalar_or_list(v)
        if 'Sid' in st:
            scalar_expression(st['Sid'])
        if 'Condition' in st:
            for op, fields in object_fields(st['Condition']).items():
                if op not in ('Bool', 'Null', 'StringEquals', 'StringNotEquals', 'ArnEquals', 'ArnLike'):
                    raise Unsupported('unmodeled resource condition operator')
                tests = object_fields(fields)
                if not tests:
                    raise Unsupported('empty condition')
                for key, val in tests.items():
                    if not key or '${' in key:
                        raise Unsupported('invalid context key')
                    scalar_or_list(val)
                    if op in ('Bool', 'Null') and val not in ('"true"', '"false"'):
                        raise Unsupported('unmodeled Boolean condition')
    if not actions:
        raise Unsupported('empty policy needs no positive admission')
    return tuple(sorted(set(actions)))


# Only inspected attributes/children get a mechanism scope. This is not a type
# allowlist: unknown attributes, nested hooks and control destinations fail closed.
SCHEMAS = {
 'aws_dynamodb_table': ('dynamodb', 'name billing_mode hash_key range_key deletion_protection_enabled tags', {
   'attribute': ('name type', {}),
   'global_secondary_index': ('name hash_key range_key projection_type', {}),
   'dynamic': None, 'point_in_time_recovery': ('enabled recovery_period_in_days', {}),
   'server_side_encryption': ('enabled', {}), 'lifecycle': ('', {'precondition': ('condition error_message', {})})}),
 'aws_s3_bucket_logging': ('s3', 'bucket expected_bucket_owner target_bucket target_prefix depends_on', {}),
 'aws_sqs_queue': ('sqs', 'for_each name message_retention_seconds sqs_managed_sse_enabled visibility_timeout_seconds redrive_policy', {}),
 'aws_cloudwatch_event_bus': ('events', 'name', {}),
 'aws_lambda_alias': ('lambda', 'for_each name function_name function_version', {}),
 'aws_lambda_event_source_mapping': ('lambda', 'event_source_arn function_name batch_size function_response_types enabled', {}),
 'aws_lambda_function_event_invoke_config': ('lambda', 'for_each function_name qualifier maximum_event_age_in_seconds maximum_retry_attempts', {
   'destination_config': ('', {'on_failure': ('destination', {})})}),
 'aws_cloudwatch_log_metric_filter': ('logs', 'name log_group_name pattern', {
   'metric_transformation': ('name namespace value', {})}),
}


def schema_scope(typ, body):
    from source import attributes, blocks
    service, fields, children = SCHEMAS[typ]
    def inspect(raw, allowed, nested):
        bb, rest = blocks(raw)
        aa = attributes(rest)
        if set(aa) - set(allowed.split()):
            raise Unsupported('uninspected mechanism attributes')
        if 'depends_on' in aa:
            # Explicit ordering only; no module, call, dynamic dependency or hook.
            dependencies = aa['depends_on'].strip()
            if not re.fullmatch(r'\[\s*aws_s3_bucket_(?:policy|ownership_controls|server_side_encryption_configuration|public_access_block)\.\w+(?:\s*,\s*aws_s3_bucket_(?:policy|ownership_controls|server_side_encryption_configuration|public_access_block)\.\w+)*\s*\]', dependencies):
                raise Unsupported('uninspected logging dependency')
        for kind, label, name, content in bb:
            if kind not in nested or name is not None:
                raise Unsupported('uninspected mechanism child')
            if kind == 'dynamic':
                shapes = {'attribute': ('name type', {}), 'global_secondary_index': ('name hash_key range_key projection_type', {})}
                if label not in shapes:
                    raise Unsupported('uninspected dynamic mechanism child')
                inner, rr = blocks(content)
                if set(attributes(rr)) != {'for_each'} or len(inner) != 1 or inner[0][:3] != ('content', None, None):
                    raise Unsupported('uninspected dynamic shape')
                inspect(inner[0][3], *shapes[label])
            else:
                if label is not None:
                    raise Unsupported('unexpected child label')
                inspect(content, *nested[kind])
        return aa
    return service, inspect(body, fields, children)


def disjoint_function(patterns, resource):
    """A name-only superset: ignoring account/region cannot prove false disjointness."""
    m = re.fullmatch(r'arn:aws:lambda:[a-z][a-z0-9-]+:[0-9]{12}:function:([A-Za-z0-9_-]+)(?::[A-Za-z0-9_-]+)?', resource or '')
    return bool(m and patterns and not any(matches(p, m[1], insensitive=True) for p in patterns))


def symbolic_string(expression, local_values, directory, active=()):
    """Superset of possible strings; literals remain, unresolved values become '*'."""
    expression = expression.strip()
    lowered = re.fullmatch(r'lower\(((?:var|local)\.\w+(?:\.\w+)*)\)', expression)
    if lowered:
        return symbolic_string(lowered[1], local_values, directory, active).lower()
    ref = re.fullmatch(r'local\.(\w+)', expression)
    if ref:
        key = (directory, ref[1])
        value = local_values.get(key)
        return '*' if key in active or not isinstance(value, str) else symbolic_string(value, local_values, directory, active + (key,))
    try:
        value = json.loads(expression)
    except (ValueError, TypeError):
        return '*'
    if not isinstance(value, str) or '%{' in value or '$${' in value:
        return '*'
    matcher = re.compile(r'\$\{([^{}]+)\}')
    residual = matcher.sub('', value)
    if '${' in residual:
        return '*'
    for m in matcher.finditer(value):
        if not re.fullmatch(r'(?:var|local)\.\w+(?:\.\w+)*|lower\((?:var|local)\.\w+(?:\.\w+)*\)', m[1]):
            return '*'
    return matcher.sub(lambda m: symbolic_string(m[1], local_values, directory, active), value)


def s3_bucket_identity(expression, directory, resources):
    """Resolve only a declared same-module bucket with inspected identity/hooks."""
    from source import attributes, blocks
    ref = re.fullmatch(r'aws_s3_bucket\.(\w+)\.id', expression)
    if not ref:
        raise Unsupported('unbound S3 policy bucket')
    target = resources.get((directory, 'aws_s3_bucket', ref[1]))
    if target is None:
        raise Unsupported('missing or ambiguous S3 bucket')
    children, rest = blocks(target);bucket = attributes(rest)
    if set(bucket) - {'bucket', 'force_destroy', 'tags'} or 'bucket' not in bucket:
        raise Unsupported('uninspected S3 bucket identity attributes')
    for kind, label, name, content in children:
        if (kind, label, name) != ('lifecycle', None, None):
            raise Unsupported('uninspected S3 bucket hook')
        guards, remainder = blocks(content)
        if remainder.strip():raise Unsupported('uninspected S3 lifecycle attributes')
        for k, t, n, b in guards:
            if (k, t, n) != ('precondition', None, None) or set(attributes(b)) != {'condition', 'error_message'}:
                raise Unsupported('uninspected S3 lifecycle hook')
    return ref[1], bucket


def s3_logging_targets(body, directory, resources, local_values):
    """Both source and destination stay relevant; only disjoint buckets excluded."""
    _, attrs = schema_scope('aws_s3_bucket_logging', body)
    targets = [s3_bucket_identity(attrs[key], directory, resources) for key in ('bucket', 'target_bucket')]
    return dict(bucketDeclarations=['aws_s3_bucket.'+name for name, _ in targets],
                patterns=[symbolic_string(bucket['bucket'],local_values,directory) for _, bucket in targets],
                meaning='SOURCE_AND_DESTINATION_SCOPE_ONLY; matching permission remains UNKNOWN')


def s3_policy_target(body, directory, resources, local_values):
    """Bind every policy Resource to its single same-module bucket declaration.

    Only target disjointness is proved; an overlapping request remains UNKNOWN
    regardless of principal/transport assumptions. No resource name is allowlisted.
    """
    from source import attributes, blocks, split_top
    resource_policy_scope(body, 'aws_s3_bucket_policy')
    nested, rest = blocks(body);attrs = attributes(rest)
    if nested or 'count' in attrs or 'for_each' in attrs:
        raise Unsupported('expanded S3 policy identity')
    name, bucket = s3_bucket_identity(attrs['bucket'], directory, resources)
    expr=attrs['policy'];doc=object_fields(expr[11:-1]);statements=doc['Statement']
    if not (statements.startswith('[') and statements.endswith(']')):
        raise Unsupported('unbound S3 statement construction')
    arn='aws_s3_bucket.'+name+'.arn';allowed={arn, json.dumps('${'+arn+'}/*')}
    count=0
    for raw in split_top(statements[1:-1]):
        st=object_fields(raw);actions=json.loads(st['Action']);actions=actions if isinstance(actions,list) else [actions]
        if not all(a.lower().startswith('s3:') for a in actions):
            raise Unsupported('cross-service S3 policy action')
        rr=st['Resource'];refs=split_top(rr[1:-1]) if rr.startswith('[') and rr.endswith(']') else [rr]
        def own_object_prefix(value):
            # An already-bound bucket ARN followed by '/' cannot change bucket
            # identity, even when the object suffix itself is unresolved.
            if not value.startswith('"${'+arn+'}/'):
                return False
            scalar_expression(value)
            return True
        if not refs or any(x not in allowed and not own_object_prefix(x) for x in refs):
            raise Unsupported('policy Resource not bound to its bucket ARN')
        count+=len(refs)
    if not count:raise Unsupported('empty S3 policy target')
    return dict(bucketDeclaration='aws_s3_bucket.'+name, arnReference=arn,
                resourceReferencesChecked=count, patterns=[symbolic_string(bucket['bucket'],local_values,directory)],
                meaning='TARGET_SCOPE_ONLY; matching identity/context permission remains UNKNOWN')


def disjoint_s3(binding, resource):
    m=re.fullmatch(r'arn:aws:s3:::([a-z0-9][a-z0-9.-]{1,61}[a-z0-9])(?:/.*)?', resource or '')
    return bool(binding and m and binding.get('patterns') and not any(matches(p,m[1]) for p in binding['patterns']))
