#!/usr/bin/env python3
"""Install the existing verified DEV package on a newly provisioned SQL host.

Run only after strict TLS installation. Does not start backups or enable runtime.
The request contains public artifact metadata, host identity and backup config;
it is not an approval receipt. Secrets are fetched by the original helper.
"""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
import tarfile

SHA = '7658cb3ac4b226d1ee069a24e6e862d3435c8862bad40bee8444eeefeb52fa40'
VERSION = 'BkdqGclnbSplQTmo66qIF40pFWsruFrR'
BUCKET = 'terragrunt-demo-sql-backup-341936017254-fa48a32dc9'
KEY = 'terragrunt-demo/dev/sql-backup-artifacts/v2-20261105/' + SHA + '/SqlBackup.tar'
CMK = 'arn:aws:kms:us-east-1:341936017254:key/30f01bb6-03b5-4e5f-b7a8-e304fe607ced'
COMMIT = '93d4f877178569515c3edaa23c1d0280002b4443'


def require(value, code):
    if not value:
        raise ValueError(code)


def verified_files(body):
    require(hashlib.sha256(body).hexdigest() == SHA, 'PACKAGE_HASH')
    with tarfile.open(fileobj=io.BytesIO(body), mode='r:') as archive:
        members = archive.getmembers()
        require(len(members) < 2000 and sum(m.size for m in members) < 536870912, 'PACKAGE_LIMIT')
        require(len({m.name.casefold() for m in members}) == len(members), 'PACKAGE_COLLISION')
        for m in members:
            name = PurePosixPath(m.name)
            require(m.isfile() and not name.is_absolute() and '..' not in name.parts and
                    str(name) == m.name and '\\' not in m.name and not (m.mode & 0o7000), 'PACKAGE_PATH')
        manifest = json.load(archive.extractfile('manifest.json'))
        require(manifest['SourceCommit'] == COMMIT and
                set(manifest['Files']) == {m.name for m in members} - {'manifest.json'}, 'PACKAGE_MANIFEST')
        files = []
        for m in members:
            data = archive.extractfile(m).read()
            if m.name != 'manifest.json':
                require(hashlib.sha256(data).hexdigest() == manifest['Files'][m.name]['Sha256'] and
                        len(data) == manifest['Files'][m.name]['Bytes'], 'PACKAGE_FILE_HASH')
            files.append((m.name, m.mode, data))
        return files


def install_public_package(package, root):
    # The package contains public binaries/configuration, with explicit file
    # modes. Its parent directories must remain traversable by the service UID.
    # Restore the private umask before provisioning credential files below.
    private_umask = os.umask(0o022)
    try:
        package.install(root / 'SqlBackup.tar', SHA, root / 'config.json', Path('/'), 'mssql', True, SHA)
    finally:
        os.umask(private_umask)


def main():
    import resource
    from botocore.session import Session
    from botocore.config import Config
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--instance-id', required=True)
    parser.add_argument('--private-ip', required=True)
    parser.add_argument('--config', type=Path, required=True)
    args = parser.parse_args()
    require(os.geteuid() == 0 and re.fullmatch('i-[0-9a-f]{17}', args.instance_id), 'HOST_IDENTITY')
    require(re.fullmatch(r'10\.0\.(100|101)\.\d{1,3}', args.private_ip), 'PRIVATE_ENDPOINT')
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    os.umask(0o077)
    root = Path('/var/tmp/sql-backup-native-install')
    require(not root.exists(), 'PREVIOUS_ATTEMPT_REQUIRES_RECONCILIATION')
    session = Session()
    config = Config(retries={'total_max_attempts': 1}, connect_timeout=8, read_timeout=60)
    client = lambda name: session.create_client(name, region_name='us-east-1', config=config)
    require(client('sts').get_caller_identity()['Arn'] ==
            'arn:aws:sts::341936017254:assumed-role/demo-dev-data-sql-ec2-role/' + args.instance_id, 'ROLE')
    obj = client('s3').get_object(Bucket=BUCKET, Key=KEY, VersionId=VERSION, ExpectedBucketOwner='341936017254')
    require(obj['VersionId'] == VERSION and obj['SSEKMSKeyId'] == CMK, 'PACKAGE_VERSION_KMS')
    body = obj['Body'].read(536870913)
    files = verified_files(body)
    cfg = json.loads(args.config.read_text())
    require(cfg['Database'] == 'demodb' and cfg['Bucket'] == BUCKET and cfg['BackupKeyArn'] == CMK and
            cfg['Prefix'] == 'terragrunt-demo/dev/sql-backups/v2-20261105', 'CONFIG_SCOPE')
    root.mkdir(mode=0o700)
    for name, mode, data in files:
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('xb') as stream:
            stream.write(data)
        path.chmod(mode)
    (root / 'SqlBackup.tar').write_bytes(body)
    (root / 'config.json').write_text(json.dumps(cfg, indent=2) + '\n')
    admission = {'Schema': 'SQL_BACKUP_EC2_REVIEW_V1', 'Account': '341936017254', 'Region': 'us-east-1',
        'SourceCommit': COMMIT, 'Package': {'Sha256': SHA},
        'Runtime': {'ExpectedRole': 'arn:aws:iam::341936017254:role/demo-dev-data-sql-ec2-role',
            'ExistingSaSecret': 'arn:aws:secretsmanager:us-east-1:341936017254:secret:demo/dev/db/sql-sa-password-30fCjc',
            'InstanceId': args.instance_id, 'SqlEndpoint': args.private_ip,
            'DatabaseSecurity': {'Profile': 'validated-v2', 'CertificateHostName': 'sql.demo.internal'}},
        'PayloadSha256': {'config.json': hashlib.sha256((root / 'config.json').read_bytes()).hexdigest()}}
    (root / 'approval.json').write_text(json.dumps(admission, indent=2) + '\n')
    sys.path.insert(0, str(root))
    import package
    import ec2_credentials
    install_public_package(package, root)
    ec2_credentials.operate(root / 'approval.json', root / 'config.json', Path('/'), True,
                            hashlib.sha256((root / 'approval.json').read_bytes()).hexdigest())
    subprocess.run(['systemctl', 'daemon-reload'], check=True, capture_output=True)
    print(json.dumps({'status': 'INSTALLED_TIMER_DISABLED', 'packageSha256': SHA, 'source': COMMIT}))


if __name__ == '__main__':
    try:
        main()
    except Exception:
        print('INSTALLATION_FAILED_OR_UNCERTAIN; reconcile before any retry')
        raise SystemExit(1)
