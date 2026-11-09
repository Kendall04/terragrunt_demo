"""Durable GitHub attestations. Slots locate; Fulcio/Sigstore authenticate.

No ZIP is an authority. The only signature verifier is gh's Sigstore verifier;
predicates and REST metadata alone cannot authenticate a workflow. All checks
remain enabled under python -O. No private key or AWS credential is involved.
"""
import base64
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import uuid
import urllib.request
import urllib.parse
from . import model as m

POLICY = json.loads(Path(__file__).with_name('receipt-policy.json').read_bytes())
EXECUTE = 'Build once in DEV or deploy approved digest in PROD'
SIGN = 'Publish durable receipt'


class PublisherIncomplete(ValueError):
    pass


def slot(kind, run, environment=None, attempt=None):
    m.require(kind in ('deployment', 'promotion') and type(run) is int and run > 0, 'receipt slot identity')
    value = dict(schema='API_RECEIPT_SLOT_V1', repository=m.REPOSITORY, kind=kind, run=run)
    if kind == 'deployment':
        m.require(environment in ('dev', 'prod') and attempt is None, 'deployment slot')
        value['environment'] = environment
    else:
        m.require(type(attempt) is int and attempt > 0 and environment is None, 'promotion slot')
        value['attempt'] = attempt
    return value


def publisher():
    return dict(run=int(os.environ['GITHUB_RUN_ID']), attempt=int(os.environ['GITHUB_RUN_ATTEMPT']),
                workflow_sha=os.environ['GITHUB_WORKFLOW_SHA'], source_sha=os.environ['GITHUB_SHA'],
                event=os.environ['GITHUB_EVENT_NAME'], ref=os.environ['GITHUB_REF'])


def public_record(value):
    """Closed public metadata, not task definitions, configs, logs or secrets."""
    fields = {'schema','repository','environment','status','source','application','image','profile','compatibility',
              'operation','binding_sha256','event_source','previous','configuration_ref','approval','color',
              'revision','per_task_ready','client_ready','run_id','run_attempt','manifest_ref','producer','request_sha256'}
    m.require(type(value) is dict and set(value) <= fields, 'non-public release fields')
    m.release(value)
    for name in ('manifest_ref', 'configuration_ref'):
        m.manifest_reference(value[name])
    previous = value.get('previous')
    if previous is not None:
        m.require(set(previous) <= {'schema','kind','environment','source','application','image','compatibility',
                                   'profile','revision','color','evidence','configuration_ref'}, 'non-public recovery fields')
        m.recovery_target(previous, value['environment'], value['compatibility'])
        m.manifest_reference(previous['configuration_ref'])
        evidence = previous['evidence']
        if previous['kind'] == 'automatic': m.manifest_reference(evidence)
        else: m.require(set(evidence) == {'binding_sha256'} and hexstr(evidence['binding_sha256'],64), 'native evidence')
    if value.get('approval') is not None:
        locator({k:v for k,v in value['approval'].items() if k != 'check_id'})
    operation = str(uuid.uuid5(uuid.NAMESPACE_URL,f'{m.REPOSITORY}/{value["environment"]}/{value["run_id"]}'))
    m.require(value['operation'] == operation and value['manifest_ref']['key'] ==
              f'api-delivery/{value["environment"]}/operations/{operation}/release.json', 'deployment operation/key mismatch')
    origin = value['producer']
    authority(origin, 'deployment', value['environment'])
    m.require((origin['run'],origin['attempt'],origin['source_sha']) ==
              (value['run_id'],value['run_attempt'],value['event_source']) and
              hexstr(value['request_sha256'],64), 'release original producer')
    return value


def hexstr(value, size):
    return type(value) is str and re.fullmatch('[0-9a-f]{'+str(size)+'}', value) is not None


def authority(value, kind, environment):
    rule = POLICY[kind]
    m.require(type(value) is dict and set(value) == {'run','attempt','workflow_sha','source_sha','event','ref'} and
              all(type(value[k]) is int and value[k] > 0 for k in ('run','attempt')) and
              hexstr(value['workflow_sha'],40) and hexstr(value['source_sha'],40) and
              value['workflow_sha'] == value['source_sha'] and value['event'] in rule['events'] and
              value['ref'] == rule['refs'][environment], 'publisher outside repository policy')
    return rule


def locator(value):
    m.require(type(value) is dict and set(value) == {'v','s','h','r','a','w'} and value['v'] == 1 and
              all(type(value[k]) is int and value[k] > 0 for k in ('r','a')) and
              hexstr(value['s'],64) and hexstr(value['h'],64) and hexstr(value['w'],40) and
              len(json.dumps(value,separators=(',',':')).encode()) <= 255, 'compact receipt locator')
    return value


def compact(descriptor, bundle, pub):
    return locator(dict(v=1,s=m.sha(m.canonical(descriptor)),h=m.sha(payload(bundle)),
                        r=pub['run'],a=pub['attempt'],w=pub['workflow_sha']))


def payload(bundle):
    raw = base64.b64decode(bundle['dsseEnvelope']['payload'], validate=True)
    m.require(len(raw) <= 262144, 'oversized attestation statement')
    return raw


def fetch_bundle(row):
    if 'bundle' in row: return row['bundle']
    # A GitHub-issued signed blob URL, never forward GH_TOKEN or follow redirects.
    url = urllib.parse.urlsplit(row['bundle_url'])
    m.require(url.scheme == 'https' and url.hostname and url.hostname.endswith('.blob.core.windows.net') and
              not url.username and not url.fragment, 'untrusted attestation storage URL')
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *args, **kwargs): return None
    with urllib.request.build_opener(NoRedirect()).open(row['bundle_url'],timeout=30) as response:
        raw = response.read(1048577)
    m.require(len(raw) <= 1048576, 'oversized attestation bundle')
    return json.loads(raw)


def bundles(gh, descriptor):
    # Repo endpoint uses cursor pagination. A full page fails closed rather than
    # silently ignoring a conflicting attestation outside the bounded slot.
    try:
        response = gh.get(f'repos/{m.REPOSITORY}/attestations/sha256:{m.sha(m.canonical(descriptor))}?per_page=100')
    except subprocess.CalledProcessError as error:
        # GitHub returns 404 for an empty subject. This is NEVER deployment
        # success: discovery must separately prove every attempt did no work.
        try: missing = json.loads(error.output or b'{}').get('status') == '404'
        except (ValueError,TypeError): missing = False
        if missing: return []
        raise
    rows = response['attestations']
    m.require(len(rows) < 100, 'receipt slot pagination bound; reconciliation required')
    return [fetch_bundle(row) for row in rows]


def cryptographic_verify(gh, bundle, descriptor, pub):
    kind = descriptor['kind']; env = descriptor.get('environment','prod')
    rule = authority(pub,kind,env)
    with tempfile.TemporaryDirectory() as directory:
        subject, signed = Path(directory)/'slot.json', Path(directory)/'bundle.json'
        subject.write_bytes(m.canonical(descriptor)); signed.write_bytes(m.canonical(bundle))
        command = ['gh','attestation','verify',str(subject),'--bundle',str(signed),'--repo',m.REPOSITORY,
                   '--predicate-type',POLICY['predicate_type'],'--signer-workflow',m.REPOSITORY+'/'+rule['signer'],
                   '--signer-digest',pub['workflow_sha'],'--source-digest',pub['source_sha'],
                   '--source-ref',pub['ref'],'--deny-self-hosted-runners','--format','json']
        result = json.loads(gh.verify_signature(command))
    m.require(len(result) == 1, 'one verified signature required')
    verified = result[0]['verificationResult']; cert = verified['signature']['certificate']
    expected = dict(buildConfigURI=f'https://github.com/{m.REPOSITORY}/{rule["caller"]}@{pub["ref"]}',
        buildConfigDigest=pub['workflow_sha'],buildSignerURI=f'https://github.com/{m.REPOSITORY}/{rule["signer"]}@{pub["ref"]}',
        buildSignerDigest=pub['workflow_sha'],buildTrigger=pub['event'],
        runInvocationURI=f'https://github.com/{m.REPOSITORY}/actions/runs/{pub["run"]}/attempts/{pub["attempt"]}',
        sourceRepositoryIdentifier=POLICY['repository_id'],sourceRepositoryOwnerIdentifier=POLICY['owner_id'],
        sourceRepositoryDigest=pub['source_sha'],sourceRepositoryRef=pub['ref'],
        sourceRepositoryURI='https://github.com/'+m.REPOSITORY,issuer='https://token.actions.githubusercontent.com',
        runnerEnvironment='github-hosted')
    m.require(all(cert.get(k) == v for k,v in expected.items()), 'signed workflow identity differs')
    statement = json.loads(payload(bundle))
    m.require(verified['statement'] == statement and statement['predicateType'] == POLICY['predicate_type'] and
              len(statement['subject']) == 1 and statement['subject'][0]['digest'] == {'sha256':m.sha(m.canonical(descriptor))},
              'signed subject/content differs')
    return statement['predicate']


def producer(gh, pub, kind, environment, completed=True, recovered=False):
    rule = authority(pub,kind,environment)
    path = f'repos/{m.REPOSITORY}/actions/runs/{pub["run"]}'
    run = gh.get(path + (f'/attempts/{pub["attempt"]}' if completed else ''))
    m.require(run['id'] == pub['run'] and run['run_attempt'] == pub['attempt'] and
              run['event'] == pub['event'], 'producer run/attempt/event differs')
    if recovered:
        m.require(run['status'] == 'completed' and run['conclusion'] in ('success','failure'), 'original deployment unfinished')
    elif completed:
        if run['status'] != 'completed' or run['conclusion'] != 'success':
            raise PublisherIncomplete('receipt publisher unsuccessful or pending')
    else:
        m.require(run['status'] == 'in_progress', 'publisher no longer executing')
    gh.trusted(dict(run,status='completed',conclusion='success'),rule['caller'],pub['event'],
               pub['ref'].removeprefix('refs/heads/') if kind == 'deployment' else None)
    if kind == 'deployment':
        m.require(run['head_sha'] == pub['source_sha'], 'producer source differs')
    return run


def original_deployment(gh, record, recovered=False):
    public_record(record)
    run = producer(gh,record['producer'],'deployment',record['environment'],recovered=recovered)
    m.require(record['source'] == run['head_sha'] or run['event'] == 'workflow_dispatch', 'built source differs')
    jobs = list(gh.pages(f'repos/{m.REPOSITORY}/actions/runs/{run["id"]}/attempts/{run["run_attempt"]}/jobs','jobs'))
    steps = [s for j in jobs for s in j['steps'] if s['name'] == EXECUTE]
    m.require(len(steps) == 1 and steps[0]['status'] == 'completed' and
              steps[0]['conclusion'] in (('success','failure') if recovered else ('success',)),
              'original execution not evidenced')


def validate_predicate(gh, value, descriptor, completed):
    m.require(set(value) == {'schema','slot','publisher','record','recovered'} and
              value['schema'] == 'API_SIGNED_RECEIPT_V1' and value['slot'] == descriptor and
              type(value['recovered']) is bool, 'receipt envelope')
    pub, record = value['publisher'], value['record']
    env = descriptor.get('environment','prod'); kind = descriptor['kind']
    run = producer(gh,pub,kind,env,completed)
    m.require(pub['run'] == descriptor['run'], 'foreign slot producer')
    if kind == 'deployment':
        if record.get('schema') == 'API_NO_DEPLOYMENT_V1':
            m.require(not value['recovered'] and set(record) == {'schema','reason','run_id','run_attempt','event_source','environment'} and
                      record['reason'] == 'superseded' and record['environment'] == env and
                      (record['run_id'],record['run_attempt'],record['event_source']) ==
                      (pub['run'],pub['attempt'],pub['source_sha']), 'invalid no-deployment receipt')
        else:
            public_record(record)
            m.require(record['run_id'] == descriptor['run'] and record['environment'] == env, 'deployment slot mismatch')
            if value['recovered']:
                m.require(record['producer']['attempt'] < pub['attempt'] and
                          record['producer']['run'] == pub['run'] and record['producer']['source_sha'] == pub['source_sha'],
                          'reconciler/original producer mismatch')
                original_deployment(gh,record,recovered=True)
            else:
                m.require(record['producer'] == pub, 'claimed deployment signer differs')
                if completed: original_deployment(gh,record)
    else:
        m.require(not value['recovered'] and pub['attempt'] == descriptor['attempt'], 'promotion attempt')
        expected = {'schema','repository','pr','head','base','application','deployment','execution','run_id','run_attempt','check_id'}
        if record['deployment']: expected |= {'dev','dev_receipt'}
        m.require(set(record) == expected and record['schema'] == 'API_PROMOTION_V1' and record['repository'] == m.REPOSITORY and
                  (record['run_id'],record['run_attempt'],record['base']) == (pub['run'],pub['attempt'],pub['source_sha']), 'promotion fields')
        execution = record['execution']
        fields = {'event','workflow_sha','workflow_ref'} | ({'trigger'} if pub['event'] == 'workflow_run' else set())
        m.require(set(execution) == fields and execution['event'] == pub['event'] and execution['workflow_sha'] == pub['workflow_sha'] and
                  execution['workflow_ref'] == m.REPOSITORY+'/'+POLICY['promotion']['caller']+'@refs/heads/main', 'trusted base identity')
        if pub['event'] == 'pull_request_target':
            m.require(run['head_sha'] in (record['head'],record['base']) and any(
                p['number'] == record['pr'] and p['head']['sha'] == record['head'] and p['head']['ref'] == 'develop' and
                p['base']['sha'] == record['base'] and p['base']['ref'] == 'main' for p in run['pull_requests']), 'PR event identity differs')
        else:
            trigger = execution['trigger']
            m.require(set(trigger) == {'id','attempt','sha'} and all(type(trigger[k]) is int and trigger[k] > 0
                      for k in ('id','attempt')) and hexstr(trigger['sha'],40), 'trigger identity fields')
            origin = gh.get(f'repos/{m.REPOSITORY}/actions/runs/{trigger["id"]}/attempts/{trigger["attempt"]}')
            gh.trusted(origin,m.DELIVERY,'push','develop')
            m.require(origin['head_sha'] == trigger['sha'] and (run['head_sha'],run['head_branch']) in
                      ((record['base'],'main'),(trigger['sha'],'develop')), 'workflow_run trigger differs')
        if record['deployment']:
            public_record(record['dev'])
            dev, _ = resolve(gh,slot('deployment',record['dev']['run_id'],'dev'),record['dev_receipt'])
            m.require(dev == record['dev'], 'sealed DEV receipt differs')
    return record


def resolve(gh, descriptor, sealed=None, completed=True):
    if sealed is not None:
        locator(sealed)
        m.require(sealed['s'] == m.sha(m.canonical(descriptor)), 'receipt locator subject mismatch')
    found = []; signed_records = []; incomplete = False
    for bundle in bundles(gh,descriptor):
        if sealed and m.sha(payload(bundle)) != sealed['h']: continue
        try:
            untrusted = json.loads(payload(bundle))['predicate']
            pub = untrusted['publisher']
            value = cryptographic_verify(gh,bundle,descriptor,pub)
        except (ValueError,KeyError,TypeError,subprocess.CalledProcessError):
            # A foreign workflow can post at this slot. It cannot authorize it.
            continue
        loc = compact(descriptor,bundle,pub)
        if sealed: m.require(loc == sealed, 'receipt locator authority differs')
        signed_records.append(value['record'])
        try:
            record = validate_predicate(gh,value,descriptor,completed)
        except PublisherIncomplete:
            if sealed or descriptor['kind'] != 'deployment': raise
            incomplete = True
            continue
        found.append((record,loc,value['recovered']))
    m.require(bool(found), 'durable receipt missing/untrusted; publication pending or deleted')
    m.require(all(m.canonical(record) == m.canonical(found[0][0]) for record in signed_records), 'contradictory signed receipts')
    m.require(not incomplete or any(recovered for _,_,recovered in found), 'failed publisher requires authenticated reconciliation')
    return found[0][:2]


def proven_no_execution(gh, run):
    """Only the closed scope job may prove a docs/no-authority no-op.

    Missing receipts after any execution step are pending, never silently skipped.
    Inspect every attempt; a rerun cannot erase a successful predecessor.
    """
    m.require(type(run['run_attempt']) is int and 1 <= run['run_attempt'] <= 20, 'attempt history bound')
    for number in range(1,run['run_attempt']+1):
        original = gh.get(f'repos/{m.REPOSITORY}/actions/runs/{run["id"]}/attempts/{number}')
        m.require(original['status'] == 'completed' and original['conclusion'] in ('success','skipped'), 'unsettled receipt-free attempt')
        gh.trusted(dict(original,conclusion='success'),m.DELIVERY,run['event'],run['head_branch'])
        jobs = list(gh.pages(f'repos/{m.REPOSITORY}/actions/runs/{run["id"]}/attempts/{number}/jobs','jobs'))
        if jobs and all(j['conclusion'] == 'skipped' and not j.get('steps') for j in jobs):
            continue  # disabled caller, no runner and no authority
        scopes = [j for j in jobs if j.get('name','').endswith('/ scope')]
        deliveries = [j for j in jobs if j.get('name','').endswith('/ delivery')]
        m.require(len(scopes) == len(deliveries) == 1 and scopes[0]['conclusion'] == 'success' and
                  deliveries[0]['conclusion'] == 'skipped' and not deliveries[0].get('steps'),
                  'deployment receipt pending; execution cannot be excluded')


def prepare_files(path, kind, recovered=False):
    record = json.loads(Path(path).read_bytes()); pub = publisher()
    descriptor = slot(kind,pub['run'],record['environment'] if kind == 'deployment' else None,
                      pub['attempt'] if kind == 'promotion' else None)
    if kind == 'deployment' and record['schema'] != 'API_NO_DEPLOYMENT_V1': public_record(record)
    envelope = dict(schema='API_SIGNED_RECEIPT_V1',slot=descriptor,publisher=pub,record=record,recovered=recovered)
    directory = Path(path).parent
    (directory/'slot.json').write_bytes(m.canonical(descriptor))
    (directory/'predicate.json').write_bytes(m.canonical(envelope))
    return descriptor
