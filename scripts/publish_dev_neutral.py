"""One administrative DEV+neutral publication; preflight is read-only by default.

No bootstrap, state download, source promotion or Terraform init/plan/apply.
The publish command requires a separate owner decision and explicit confirmation.
"""
import argparse
import base64
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'scripts'), str(ROOT / 'scripts/tests/security_root'),
               str(ROOT / 'scripts/tests/authority')]
from first_dev_bootstrap import AWS, policy
import publication
from model import load_authority

ACCOUNT = '341936017254'
REGION = 'us-east-1'
ADMIN = 'arn:aws:iam::' + ACCOUNT + ':user/cnp-cert-admin'
BUCKET = 'terragrunt-demo-security-' + ACCOUNT + '-' + REGION
CANDIDATE_SHA256 = '2a03f96c79b2132aa3834f6591bf0bb08fbd36fa0d23d7eb241d2d0c30858504'
CONFIRM = 'PUBLISH DEV NEUTRAL ' + CANDIDATE_SHA256


def require(ok, category):
    if not ok:
        raise ValueError('DEV_NEUTRAL_REJECTED: ' + category)


def terraform_output(directory, env):
    """Read only the named output from the already initialized original backend."""
    directory = Path(directory).resolve(strict=True)
    metadata = json.loads((directory / '.terraform/terraform.tfstate').read_text())
    backend = metadata['backend']  # Local backend configuration, not remote state.
    config = backend['config']
    require(backend['type'] == 's3' and config['bucket'] == BUCKET
            and config['key'] == 'e1/security/terraform.tfstate'
            and config['region'] == REGION and config['encrypt'] is True
            and config['use_lockfile'] is True, 'original security backend required')
    workspace = directory / '.terraform/environment'
    require(not workspace.exists() or workspace.read_text().strip() == 'default', 'workspace')
    clean = dict(env, CHECKPOINT_DISABLE='1', TF_IN_AUTOMATION='true')
    version = subprocess.run(['terraform', 'version', '-json'], env=clean,
                             capture_output=True, timeout=30)
    require(version.returncode == 0 and json.loads(version.stdout)['terraform_version'] == '1.13.4', 'Terraform version')
    result = subprocess.run(['terraform', '-chdir=' + str(directory), 'output', '-json',
                             'protected_output_candidates'], env=clean,
                            capture_output=True, timeout=120)
    require(result.returncode == 0, 'named Terraform output read failed')
    return publication.decode_record(result.stdout)


class DevNeutralChannel(publication.AdminChannel):
    """Fixed administrator, bucket, candidate and key; no caller storage routes."""
    def __init__(self, aws, doc, candidate, output_reader, allow_publish=False):
        self.aws, self.doc, self.candidate = aws, doc, Path(candidate)
        self.raw = self.candidate.read_bytes()
        require(hashlib.sha256(self.raw).hexdigest() == CANDIDATE_SHA256, 'candidate checksum')
        self.expected = publication.decode_record(self.raw)
        publication.validate_publication(doc, self.expected, ACCOUNT, REGION)
        require(self.expected['schema'] == publication.DEV_NEUTRAL_SCHEMA, 'scope')
        historical = doc['ownership_closure']['publications'][ACCOUNT + '/' + REGION]['records']
        require(len(historical) == 20 and len(self.expected['records']) == 23
                and {k: v for k, v in self.expected['records'].items() if v['scope'] == 'dev'} == historical
                and set(self.expected['records']) - set(historical) == publication.NEUTRAL_KEYS, 'historical/neutral set')
        self.key = publication.output_key(doc, ACCOUNT, REGION, dev_neutral=True)
        self.output_reader = output_reader
        self.allow_publish = allow_publish
        self.prepared = self.attempted = self.put_dispatched = False
        self.stage = 'CREATED'
        self.version_id = None
        self.reconciliation = None

    def call(self, *args):
        self.stage = '/'.join(args[:2])
        return self.aws.call(*args, '--cli-connect-timeout', '8', '--cli-read-timeout', '20')

    def authenticate(self):
        value = self.call('sts', 'get-caller-identity')
        require(value.get('Account') == ACCOUNT and value.get('Arn') == ADMIN, 'administrator identity')

    def bucket_controls(self):
        owner = ('--bucket', BUCKET, '--expected-bucket-owner', ACCOUNT)
        require((self.call('s3api', 'get-bucket-location', *owner).get('LocationConstraint') or REGION) == REGION, 'bucket region')
        installed = json.loads(self.call('s3api', 'get-bucket-policy', *owner)['Policy'])
        require(installed == policy(BUCKET, ADMIN), 'exact admin-only/TLS bucket policy')
        require(self.call('s3api', 'get-bucket-versioning', *owner).get('Status') == 'Enabled', 'bucket versioning')
        public = {k: True for k in ('BlockPublicAcls', 'IgnorePublicAcls', 'BlockPublicPolicy', 'RestrictPublicBuckets')}
        require(self.call('s3api', 'get-public-access-block', *owner)['PublicAccessBlockConfiguration'] == public, 'public access')
        rules = self.call('s3api', 'get-bucket-encryption', *owner)['ServerSideEncryptionConfiguration']['Rules']
        require(len(rules) == 1 and rules[0]['ApplyServerSideEncryptionByDefault'] == {'SSEAlgorithm': 'AES256'}
                and not rules[0].get('BucketKeyEnabled', False), 'bucket encryption')
        require(self.call('s3api', 'get-bucket-ownership-controls', *owner)['OwnershipControls']['Rules'] ==
                [{'ObjectOwnership': 'BucketOwnerEnforced'}], 'bucket owner')
        # Policy evidence only: a simulation is not proof of a successful PUT.
        context = json.dumps([{'ContextKeyName': 'aws:PrincipalArn', 'ContextKeyType': 'string', 'ContextKeyValues': [ADMIN]},
                              {'ContextKeyName': 'aws:SecureTransport', 'ContextKeyType': 'boolean', 'ContextKeyValues': ['true']}])
        for actions, resource in ((['s3:ListBucketVersions'], 'arn:aws:s3:::' + BUCKET),
                                  (['s3:PutObject', 's3:GetObjectVersion'], 'arn:aws:s3:::' + BUCKET + '/' + self.key)):
            result = self.call('iam', 'simulate-principal-policy', '--policy-source-arn', ADMIN,
                               '--action-names', *actions, '--resource-arns', resource,
                               '--resource-policy', json.dumps(installed), '--caller-arn', ADMIN,
                               '--context-entries', context)['EvaluationResults']
            require(len(result) == len(actions) and {v['EvalActionName'] for v in result} == set(actions)
                    and all(v['EvalDecision'] == 'allowed' and v['EvalResourceName'] == resource for v in result), 'IAM policy evaluation')

    def history(self):
        found, markers = [], []
        pagination = []
        for _ in range(20):
            page = self.call('s3api', 'list-object-versions', '--bucket', BUCKET,
                             '--expected-bucket-owner', ACCOUNT, '--prefix', self.key,
                             '--no-paginate', '--max-keys', '1000', *pagination)
            found += [v for v in page.get('Versions', []) if v['Key'] == self.key]
            markers += [v for v in page.get('DeleteMarkers', []) if v['Key'] == self.key]
            require(type(page.get('IsTruncated')) is bool, 'history completeness')
            if not page['IsTruncated']:
                return found, markers
            pagination = ['--key-marker', page['NextKeyMarker']]
            if page.get('NextVersionIdMarker'):
                pagination += ['--version-id-marker', page['NextVersionIdMarker']]
        raise ValueError('DEV_NEUTRAL_REJECTED: history page limit')

    def read_output(self):
        self.authenticate()
        self.stage = 'terraform/output/protected_output_candidates'
        output = self.output_reader()
        catalog = self.doc['ownership_closure']
        require(set(output) == set(catalog['resources']) | {'recovery/' + k for k in catalog['recovery']}, 'output catalog')
        records = {k: v for k, v in output.items() if v['scope'] == 'dev' or k in publication.NEUTRAL_KEYS}
        publication.validate_records(self.doc, records, ACCOUNT, REGION, dev_neutral=True)
        require(records == self.expected['records'], 'candidate/output identity, properties and ARN mismatch')
        return copy.deepcopy(records)

    def preflight(self):
        self.read_output()
        self.bucket_controls()
        versions, markers = self.history()
        require(not versions and not markers, 'existing version or delete marker')
        self.prepared = True
        return {'result': 'PREFLIGHT_PASS', 'bucket': BUCKET, 'key': self.key,
                'administrator': ADMIN, 'records': 23, 'sha256': CANDIDATE_SHA256,
                'write_permission': 'SIMULATION_ALLOWED_NOT_WRITE_PROOF', 'aws_writes': 0}

    def create_publication(self, key, value):
        require(self.allow_publish and self.prepared and not self.attempted, 'publication disabled or already attempted')
        require(key == self.key and value == self.expected, 'fixed publication identity')
        self.authenticate()
        self.bucket_controls()
        require(self.history() == ([], []), 'existing version or delete marker')
        self.attempted = True
        # Private candidate parent must have its restrictive ACL verified by admin.
        with tempfile.TemporaryDirectory(prefix='dev-neutral-', dir=self.candidate.parent) as temp:
            body = Path(temp) / 'approved.json'
            body.write_bytes(self.raw)
            try:
                self.put_dispatched = True
                ack = self.call('s3api', 'put-object', '--bucket', BUCKET, '--key', self.key,
                                '--expected-bucket-owner', ACCOUNT, '--body', str(body),
                                '--if-none-match', '*', '--server-side-encryption', 'AES256',
                                '--content-type', 'application/json', '--checksum-sha256',
                                base64.b64encode(hashlib.sha256(self.raw).digest()).decode())
                self.version_id = ack.get('VersionId')
                require(isinstance(self.version_id, str) and self.version_id not in ('', 'null'), 'authentic returned VersionId')
                self.read_publication(self.key)
                versions, markers = self.history()
                require(not markers and len(versions) == 1 and versions[0]['VersionId'] == self.version_id, 'post-write history conflict')
            except (ValueError, KeyError, OSError, subprocess.SubprocessError):
                # Only readbacks after an uncertain write. Never resend or delete.
                self.reconciliation = 'UNVERIFIED'
                try:
                    versions, markers = self.history()
                    if len(versions) == 1 and not markers:
                        self.version_id = versions[0]['VersionId']
                        self.read_publication(self.key)
                        self.reconciliation = 'EXACT_VERSION_FOUND_AFTER_FAILED_ATTEMPT'
                except (ValueError, KeyError, OSError, subprocess.SubprocessError):
                    pass
                raise ValueError('DEV_NEUTRAL_WRITE_UNVERIFIED: stop; readback=' + self.reconciliation) from None

    def read_publication(self, key):
        require(key == self.key and isinstance(self.version_id, str) and self.version_id not in ('', 'null'), 'exact stored version required')
        with tempfile.TemporaryDirectory(prefix='dev-neutral-read-', dir=self.candidate.parent) as temp:
            body = Path(temp) / 'readback.json'
            receipt = self.call('s3api', 'get-object', '--bucket', BUCKET, '--key', self.key,
                                '--expected-bucket-owner', ACCOUNT, '--version-id', self.version_id, str(body))
            raw = body.read_bytes()
        require(receipt.get('VersionId') == self.version_id and receipt.get('ServerSideEncryption') == 'AES256', 'storage/version identity')
        require(raw == self.raw and hashlib.sha256(raw).hexdigest() == CANDIDATE_SHA256, 'readback bytes/checksum')
        value = publication.decode_record(raw)
        publication.validate_publication(self.doc, value, ACCOUNT, REGION)
        require(value == self.expected, 'readback content')
        return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation', choices=('preflight', 'publish', 'verify'))
    parser.add_argument('--candidate', required=True, type=Path)
    parser.add_argument('--terraform-dir', required=True, type=Path)
    parser.add_argument('--confirm')
    parser.add_argument('--version-id')
    args = parser.parse_args()
    channel = None
    try:
        require(args.operation != 'publish' or args.confirm == CONFIRM, 'separate owner approval/confirmation required')
        aws = AWS(ACCOUNT)
        channel = DevNeutralChannel(aws, load_authority(ROOT), args.candidate,
                                    lambda: terraform_output(args.terraform_dir, aws.env), args.operation == 'publish')
        if args.operation == 'verify':
            channel.authenticate()
            channel.bucket_controls()
            channel.version_id = args.version_id
            channel.read_publication(channel.key)
            result = {'result': 'EXACT_VERSION_VERIFIED', 'bucket': BUCKET, 'key': channel.key, 'version_id': channel.version_id, 'sha256': CANDIDATE_SHA256}
        else:
            result = channel.preflight()
            if args.operation == 'publish':
                publication.publish_outputs(channel.doc, ACCOUNT, REGION, channel, dev_neutral=True)
                result.update(result='PUBLICATION_VERIFIED', aws_writes=1, version_id=channel.version_id)
        print(json.dumps(result, indent=2))
        return 0
    except (ValueError, KeyError, OSError, subprocess.SubprocessError) as error:
        # Never print Terraform output, native stderr, credentials or record bodies.
        category = str(error) if isinstance(error, ValueError) and str(error).startswith('DEV_NEUTRAL_') else 'ADMIN_PUBLICATION_GUARD_OR_IO'
        print(json.dumps({'result': 'FAILED_OR_UNVERIFIED', 'operation': args.operation,
                          'stage': channel.stage if channel else 'LOCAL_ADMISSION',
                          'category': category, 'put_dispatched': bool(channel and channel.put_dispatched),
                          'observed_version_id': channel.version_id if channel else None,
                          'automatic_retry': False}), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
