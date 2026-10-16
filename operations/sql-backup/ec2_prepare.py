#!/usr/bin/env python3
"""Render a review packet from public AWS metadata. Never calls AWS or applies it."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import re
import tarfile

ACCOUNT='341936017254'
REGION='us-east-1'
BUCKET='terragrunt-demo-sql-backup-341936017254-fa48a32dc9'
KEY=f'arn:aws:kms:{REGION}:{ACCOUNT}:key/30f01bb6-03b5-4e5f-b7a8-e304fe607ced'
TEXT_KEY=f'arn:aws:kms:{REGION}:{ACCOUNT}:key/50d3fe36-8128-4d09-ac13-8f5536a230a7'
ROLE=f'arn:aws:iam::{ACCOUNT}:role/demo-dev-data-sql-ec2-role'
ADMIN=f'arn:aws:iam::{ACCOUNT}:user/cnp-cert-admin'
PREFIX='terragrunt-demo/dev/sql-backups/ec2-20261016'
SA=f'arn:aws:secretsmanager:{REGION}:{ACCOUNT}:secret:demo/dev/db/sql-sa-password-30fCjc'

def require(ok,code):
    if not ok: raise ValueError(code)

def sha(body): return hashlib.sha256(body).hexdigest()

def encoded(value): return (json.dumps(value,indent=2,sort_keys=True)+'\n').encode()

def append_statements(document,statements):
    result=copy.deepcopy(document)
    existing={s.get('Sid') for s in result['Statement']}
    require(not existing.intersection(s['Sid'] for s in statements),'REVIEW_EXISTING_OVERLAY')
    result['Statement']+=statements
    return result

def deny_puts(resource,suffix):
    conditions=[('Encryption',{'StringNotEquals':{'s3:x-amz-server-side-encryption':'aws:kms'}}),
                ('Key',{'StringNotEquals':{'s3:x-amz-server-side-encryption-aws-kms-key-id':KEY}}),
                ('Conditional',{'StringNotEquals':{'s3:if-none-match':'*'}})]
    return [{'Sid':'Ec2Backup'+suffix+name,'Effect':'Deny','Principal':'*','Action':'s3:PutObject','Resource':resource,'Condition':condition} for name,condition in conditions]

def render(snapshot,archive,expected_sha,output,network=None):
    require(snapshot['Identity']['Account']==ACCOUNT and snapshot['Identity']['Arn']==ADMIN and snapshot['Region']==REGION,'WRONG_ACCOUNT_OR_OPERATOR')
    require(snapshot['Role']['Arn']==ROLE,'WRONG_SQL_ROLE')
    require(snapshot['Versioning'].get('Status')=='Enabled' and snapshot['BackupKey']=={'Arn':KEY,'State':'Enabled'},'RETAINED_STORAGE_NOT_READY')
    encryption=snapshot['Encryption']['ServerSideEncryptionConfiguration']['Rules']
    require(len(encryption)==1 and encryption[0]['ApplyServerSideEncryptionByDefault'].get('KMSMasterKeyID')==KEY and encryption[0].get('BucketKeyEnabled') is False,'EXACT_S3_KMS_CONTEXT_REQUIRED')
    require(any(x['Arn']==SA and x['KmsKeyId']==TEXT_KEY for x in snapshot['SecretsMetadata']),'EXISTING_SA_METADATA_REQUIRED')
    require(re.fullmatch('[a-f0-9]{64}',expected_sha) is not None and sha(archive.read_bytes())==expected_sha,'PACKAGE_HASH_MISMATCH')
    with tarfile.open(archive,'r:') as package:
        member=package.getmember('manifest.json')
        require(member.isfile() and member.size<=262144,'PACKAGE_MANIFEST_BOUND')
        manifest=json.load(package.extractfile(member))
    require(manifest['Target']=='linux-x64' and manifest['Runtime']=='10.0.13' and re.fullmatch('[a-f0-9]{40}',manifest['SourceCommit']) is not None,'PACKAGE_CONTRACT_REQUIRED')
    require(all(name in manifest['Files'] for name in ('host.py','package.py','ec2_credentials.py')),'EC2_BOOTSTRAP_PACKAGE_REQUIRED')
    require(not output.exists(),'NEW_REVIEW_DIRECTORY_REQUIRED')
    objects=f'arn:aws:s3:::{BUCKET}/{PREFIX}/*'
    artifact_key=f'terragrunt-demo/dev/sql-backup-artifacts/ec2-20261016/{expected_sha}/SqlBackup.tar'
    artifact=f'arn:aws:s3:::{BUCKET}/{artifact_key}'
    config={'Database':'demodb','StagingDirectory':'/var/opt/mssql/backup/v2','RestoreDirectory':'/var/opt/mssql/backup/v2-restores',
            'Bucket':BUCKET,'Prefix':PREFIX,'BackupKeyArn':KEY,'TextKeyArn':TEXT_KEY,'ExpectedEc2RoleName':ROLE.rsplit('/',1)[1],
            'MaxBackupBytes':536870912,'FreeReserveBytes':268435456,'TimeoutSeconds':600,'RetainLocalVerifiedBackups':2,
            'ProposedIntervalHours':1,'ProposedRetentionDays':2,'ProposedMaxAgeHours':2}
    runtime_policy={'Version':'2012-10-17','Statement':[
        {'Sid':'PutOnlyNewBackupObjects','Effect':'Allow','Action':'s3:PutObject','Resource':objects,'Condition':{'StringEquals':{'s3:x-amz-server-side-encryption':'aws:kms','s3:x-amz-server-side-encryption-aws-kms-key-id':KEY,'s3:if-none-match':'*'}}},
        {'Sid':'VerifyExactBackupVersions','Effect':'Allow','Action':['s3:GetObject','s3:GetObjectVersion'],'Resource':objects},
        {'Sid':'ReadOnlyThisArtifact','Effect':'Allow','Action':'s3:GetObjectVersion','Resource':artifact},
        {'Sid':'BackupKeyThroughS3Only','Effect':'Allow','Action':['kms:GenerateDataKey','kms:Decrypt'],'Resource':KEY,'Condition':{'StringEquals':{'kms:ViaService':f's3.{REGION}.amazonaws.com'},'StringLike':{'kms:EncryptionContext:aws:s3:arn':[objects,artifact]}}}]}
    def key_statement(sid,principal,actions,context):
        return {'Sid':sid,'Effect':'Allow','Principal':{'AWS':principal},'Action':actions,'Resource':'*','Condition':{'StringEquals':{'kms:ViaService':f's3.{REGION}.amazonaws.com'},'StringLike':{'kms:EncryptionContext:aws:s3:arn':context}}}
    key_after=append_statements(snapshot['BackupKeyPolicy'],[
        key_statement('Ec2BackupProducer',ROLE,['kms:GenerateDataKey','kms:Decrypt'],objects),
        key_statement('Ec2BackupArtifactReader',ROLE,['kms:Decrypt'],artifact),
        key_statement('Ec2BackupTemporaryArtifactPublisher',ADMIN,['kms:GenerateDataKey','kms:Decrypt'],artifact)])
    bucket_after=append_statements(snapshot['BucketPolicy'],deny_puts(objects,'Data')+deny_puts(artifact,'Artifact'))
    lifecycle=copy.deepcopy(snapshot['Lifecycle']['Rules'])
    require(not any(x['ID'] in ('ec2-hourly-two-plus-two','ec2-artifact-one-day') for x in lifecycle),'REVIEW_EXISTING_LIFECYCLE')
    lifecycle += [
        {'ID':'ec2-hourly-two-plus-two','Status':'Enabled','Filter':{'Prefix':PREFIX+'/'},'Expiration':{'Days':2},'NoncurrentVersionExpiration':{'NoncurrentDays':2},'AbortIncompleteMultipartUpload':{'DaysAfterInitiation':1}},
        {'ID':'ec2-artifact-one-day','Status':'Enabled','Filter':{'Prefix':artifact_key},'Expiration':{'Days':1},'NoncurrentVersionExpiration':{'NoncurrentDays':1}}]
    files={'config.json':config,'role-inline-policy.json':runtime_policy,'bucket-policy.before.json':snapshot['BucketPolicy'],
           'bucket-policy.after.json':bucket_after,'backup-key-policy.before.json':snapshot['BackupKeyPolicy'],'backup-key-policy.after.json':key_after,
           'lifecycle.before.json':{'Rules':snapshot['Lifecycle']['Rules']},'lifecycle.after.json':{'Rules':lifecycle}}
    project_vpcs=[v for v in snapshot['Vpcs'] if v.get('Default') is False and {'Project':'demo','Environment':'dev'}.items() <= {t['Key']:t['Value'] for t in v.get('Tags') or []}.items()]
    network_status='ACTUAL_NETWORK_BINDING_REQUIRED' if project_vpcs else 'ORIGINAL_DEV_NETWORK_ABSENT'
    hosts=[v for v in snapshot['Instances'] if {t['Key']:t['Value'] for t in v.get('Tags') or []}.get('Name')=='demo-dev-data-sql-instance']
    require(len(hosts)<=1,'AMBIGUOUS_SQL_HOST')
    if hosts:
        require(hosts[0].get('PublicIp') is None and hosts[0].get('Profile')==f'arn:aws:iam::{ACCOUNT}:instance-profile/demo-dev-data-sql-ec2-profile','PRIVATE_ORIGINAL_SQL_HOST_REQUIRED')
    if network is not None:
        require(set(network)=={'VpcId','PrivateRouteTableIds','Environment','Project'} and network['Environment']=='dev' and network['Project']=='demo','PROJECT_NETWORK_BINDING_REQUIRED')
        require(re.fullmatch('vpc-[a-f0-9]{8,17}',network['VpcId']) is not None and len(set(network['PrivateRouteTableIds']))==2 and all(re.fullmatch('rtb-[a-f0-9]{8,17}',v) for v in network['PrivateRouteTableIds']),'TWO_DISTINCT_PRIVATE_ROUTE_TABLES_REQUIRED')
        require(any(v['Id']==network['VpcId'] and v.get('Default') is False and {'Project':'demo','Environment':'dev'}.items() <= {t['Key']:t['Value'] for t in v.get('Tags') or []}.items() for v in snapshot['Vpcs']),'OBSERVED_PROJECT_VPC_REQUIRED')
        network_status='BOUND_REQUIRES_ADMIN_REVIEW'
        # This is an admin candidate, not admitted into an ordinary/E1 root.
        files['s3-endpoint.candidate.tf.json']={'resource':{'aws_vpc_endpoint':{'sql_backup_s3':{
            'vpc_id':network['VpcId'],'service_name':f'com.amazonaws.{REGION}.s3','vpc_endpoint_type':'Gateway','route_table_ids':network['PrivateRouteTableIds'],
            'tags':{'Name':'demo-dev-sql-backup-s3','Environment':'dev','Project':'demo','Owner':'kendall'},
            'policy':json.dumps({'Version':'2012-10-17','Statement':[{'Effect':'Allow','Principal':'*','Action':'s3:*','Resource':'*'}]})}}}}
    hashes={name:sha(encoded(body)) for name,body in files.items()}
    quotes=snapshot.get('PriceQuotes',{})
    def rate(instance):
        rows=quotes.get(instance,[])
        require(isinstance(rows,list) and len(rows)==1 and rows[0]['Unit']=='Hrs','FRESH_EC2_PRICE_QUOTE_REQUIRED')
        return float(rows[0]['USD'])
    costs={'SqlAndTwoOriginalNatFourHours':round(4*(rate('t3a.small')+2*rate('t3.micro')),4),
           'TwoPublicNatIpv4FourHours':0.04,'InternalAlbFourHoursIncludingOneLcu':0.122,
           'EbsConservative62GiBFourHours':round(62*0.08*4/720,4),'LogsAlarmsRequestsContingency':0.50,
           'PriorRetainedComponentFirstMonthCeiling':1.2574,'ExistingTextKeyFirstMonth':1.0,'ExistingThreeSecretsFirstMonth':1.2}
    require(sum(costs.values())<=5,'REESTIMATE_EXCEEDS_REVIEW_ENVELOPE')
    approval={'Schema':'SQL_BACKUP_EC2_REVIEW_V1','Status':'REVIEW_ONLY_NOT_AUTHORIZED','Account':ACCOUNT,'Region':REGION,'Operator':ADMIN,
        'SnapshotReadUtc':snapshot['ReadUtc'],'SnapshotSha256':sha(encoded(snapshot)),'SourceCommit':manifest['SourceCommit'],
        'Package':{'Sha256':expected_sha,'Bucket':BUCKET,'Key':artifact_key,'VersionId':'BIND_EXACT_UPLOAD_RETURN_BEFORE_DOWNLOAD'},
        'Runtime':{'ExpectedRole':ROLE,'ExistingProfile':f'arn:aws:iam::{ACCOUNT}:instance-profile/demo-dev-data-sql-ec2-profile','Database':'demodb','ExpectedName':'demo-dev-data-sql-instance','InstanceId':hosts[0]['Id'] if hosts else None,'HostStatus':'OBSERVED_NEEDS_SSM_SQL_VERIFICATION' if hosts else 'ORIGINAL_RUNTIME_ABSENT','PublicIp':False,'Imds':'v2-required','ExistingSaSecret':SA},
        'CredentialBootstrap':{'Logins':['td_backup_dev','td_verify_dev'],'VerifierGrant':'master CREATE DATABASE; no sysadmin/dbcreator/source SELECT','BackupGrant':'demodb db_backupoperator','Persistence':'root:root 0600 connection files in 0700 credential directory on encrypted EBS; systemd LoadCredential copies to runtime','NewSecretsManagerSecrets':0,'SqlcmdPasswordInArgv':False},
        'Network':{'Status':network_status,'Name':'demo-dev-sql-backup-s3','Kind':'Gateway','PrivateRouteTables':2,'NewInboundRules':0,'DefaultRoutesChanged':False,'PaidInterfaceEndpoints':0,'Ownership':'separately reviewed admin candidate; no ordinary-root admission'},
        'Security':{'InlinePolicyName':'sql-backup-ec2-20261016','RoleTrustChanged':False,'OriginalSqlRolePolicyReplaced':False,'OriginalTextKeyPolicyChanged':False,'BucketPolicyChanges':'append six prefix/object-specific deny statements; preserve existing statements','KeyPolicyChanges':['Ec2BackupProducer','Ec2BackupArtifactReader','Ec2BackupTemporaryArtifactPublisher']},
        'HostPaths':['/opt/terragrunt-demo/sql-backup','/etc/terragrunt-demo/sql-backup/config.json','/etc/terragrunt-demo/sql-backup/credentials','/etc/systemd/system/sql-backup.service','/etc/systemd/system/sql-backup.timer','/etc/systemd/system/sql-backup.service.d/credentials.conf','/var/opt/mssql/backup/v2'],
        'Acceptance':{'ManualRemoteVerified':1,'RealHourlyTimerActivations':2,'MaxBackupRuns':3,'EachBackupMaxMiB':512,'WindowHours':4,'SafeStop':'disable timer; inhibit and wait idle; preserve UNKNOWN evidence; no final backup required for disposable lab data'},
        'Budget':{'Currency':'USD','SharedPreviouslyApprovedCeiling':10,'ThisIsNotAnotherTenDollars':True,'BeforeTaxFirstMonthEstimate':round(sum(costs.values()),4),'RoundedPlanningEnvelope':5,'Costs':costs,'ActualRemainingBudget':'NOT_PROVEN_BY_PRICE_QUOTES_OR_DELAYED_BILLING','NoNewMonthlyKeyOrSecret':True,'OperatorMustEndAfterTwoSuccessesOrFourHours':True,'Enforcement':'operator window; no AWS spending cap or automatic retirement installed','Sources':['AWS Pricing GetProducts quotes in snapshot','https://aws.amazon.com/vpc/pricing/','https://aws.amazon.com/elasticloadbalancing/pricing/','https://aws.amazon.com/ebs/pricing/','https://aws.amazon.com/kms/pricing/','https://aws.amazon.com/secrets-manager/pricing/']},
        'NotInScope':['independent observer/notification','cross-AZ restore','Cognito','new VPC architecture','Fargate application deployment','push/merge'],
        'Retirement':{'AfterArtifactReadback':'remove Ec2BackupTemporaryArtifactPublisher key-use statement','AfterAcceptance':'disable timer; inhibit/wait; export sanitized receipts and version/hash evidence; remove owned SQL logins/credential files and the named inline policy; remove the two EC2 key-use statements','Infrastructure':'original E16 supervised DOWN of newly activated global/data runtime, including disposable SQL/EBS; no ceremonial final backup','Preserve':['old backup prefix and every pre-existing S3 version','backup CMK and original text CMK','existing role/trust/wp2d policy/SSM attachment','new data-prefix encryption/conditional deny and scoped 2+2 retention'],'PolicyWrites':'compare current documents with reviewed before/after hashes; remove only owned Sids, never blindly overwrite concurrent edits','NoCredentialOrBackupValuesInEvidence':True},
        'Blockers':(['Original global/data runtime absent; original E16 saved plans and actual IDs required'] if not hosts else ['Observed host still requires fresh E16 ownership, SSM, IMDS and native SQL readiness checks'])+(['Two original private route-table IDs require fresh binding'] if network is None else [])+['No host/instance/endpoint identity may be invented','Package upload version must be bound after approved conditional write','Security/network/credential/host mutations require owner approval'],
        'PayloadSha256':hashes,'AwsMutations':False}
    files['approval.json']=approval
    output.mkdir(parents=True)
    for name,body in files.items(): (output/name).write_bytes(encoded(body))
    receipt={'Status':'REVIEW_PACKET_READY','ApprovalSha256':sha(encoded(approval)),'Files':len(files),'NetworkStatus':network_status,'AwsMutations':False}
    (output/'packet-receipt.json').write_bytes(encoded(receipt))
    return receipt

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--snapshot',type=Path,required=True); parser.add_argument('--package',type=Path,required=True)
    parser.add_argument('--expected-sha256',required=True); parser.add_argument('--output',type=Path,required=True); parser.add_argument('--network',type=Path)
    args=parser.parse_args()
    return render(json.loads(args.snapshot.read_text()),args.package,args.expected_sha256,args.output,json.loads(args.network.read_text()) if args.network else None)

if __name__=='__main__':
    try: print(json.dumps(main(),separators=(',',':')))
    except Exception as error:
        print(json.dumps({'Status':'FAILED','Code':str(error) if isinstance(error,ValueError) else 'REVIEW_PACKET_FAILED'}))
        raise SystemExit(1)
