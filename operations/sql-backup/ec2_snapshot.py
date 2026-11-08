#!/usr/bin/env python3
from pathlib import Path
import argparse,datetime,json,subprocess
parser=argparse.ArgumentParser(description='Read public SQL EC2 deployment metadata only; no secret values, state or AWS mutations.')
parser.add_argument('--output',type=Path,required=True)
args=parser.parse_args()
assert not args.output.exists(), 'Use a new snapshot filename; evidence is never overwritten'
assert args.output.parent.is_dir(), 'Existing evidence directory required'
def aws(*args):
    run=subprocess.run(['aws','--profile','cnp-cert-dev','--region','us-east-1','--output','json','--no-cli-pager',*args],capture_output=True,text=True,timeout=90)
    if run.returncode: return {'ReadFailed':True,'Operation':' '.join(args[:2])}
    return json.loads(run.stdout)
identity=aws('sts','get-caller-identity')
assert identity['Account']=='341936017254' and identity['Arn']=='arn:aws:iam::341936017254:user/cnp-cert-admin'
bucket='terragrunt-demo-sql-backup-341936017254-fa48a32dc9'; key='30f01bb6-03b5-4e5f-b7a8-e304fe607ced'
operations={
'Instances':('ec2','describe-instances','--query','Reservations[].Instances[].{Id:InstanceId,State:State.Name,Vpc:VpcId,Subnet:SubnetId,PublicIp:PublicIpAddress,Profile:IamInstanceProfile.Arn,Tags:Tags}'),
'Vpcs':('ec2','describe-vpcs','--query','Vpcs[].{Id:VpcId,Default:IsDefault,Tags:Tags}'),
'Endpoints':('ec2','describe-vpc-endpoints','--query','VpcEndpoints[].{Id:VpcEndpointId,Vpc:VpcId,Service:ServiceName,RouteTables:RouteTableIds}'),
'ManagedInstances':('ssm','describe-instance-information','--query','InstanceInformationList[].{Id:InstanceId,Ping:PingStatus}'),
'Role':('iam','get-role','--role-name','demo-dev-data-sql-ec2-role','--query','Role.{Arn:Arn,Trust:AssumeRolePolicyDocument}'),
'RolePolicy':('iam','get-role-policy','--role-name','demo-dev-data-sql-ec2-role','--policy-name','wp2d-dev_sql','--query','PolicyDocument'),
'AttachedPolicies':('iam','list-attached-role-policies','--role-name','demo-dev-data-sql-ec2-role'),
'BucketPolicy':('s3api','get-bucket-policy','--bucket',bucket,'--expected-bucket-owner','341936017254'),
'Lifecycle':('s3api','get-bucket-lifecycle-configuration','--bucket',bucket,'--expected-bucket-owner','341936017254'),
'Versioning':('s3api','get-bucket-versioning','--bucket',bucket,'--expected-bucket-owner','341936017254'),
'Encryption':('s3api','get-bucket-encryption','--bucket',bucket,'--expected-bucket-owner','341936017254'),
'BackupKeyPolicy':('kms','get-key-policy','--key-id',key,'--policy-name','default'),
'BackupKey':('kms','describe-key','--key-id',key,'--query','KeyMetadata.{Arn:Arn,State:KeyState}'),
'SecretsMetadata':('secretsmanager','list-secrets','--query','SecretList[].{Name:Name,Arn:ARN,KmsKeyId:KmsKeyId}'),
'OriginalSqlAmiCandidate':('ec2','describe-images','--owners','099720109477','--filters','Name=name,Values=ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-*','Name=state,Values=available','--query','sort_by(Images,&CreationDate)[-1].{Id:ImageId,Name:Name,Created:CreationDate,Architecture:Architecture,Owner:OwnerId}'),
}
snapshot={'SchemaVersion':1,'ReadUtc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'Identity':identity,'Region':'us-east-1','AwsMutations':False}
for name,args in operations.items():
    value=aws(*args)
    if name in ('BucketPolicy','BackupKeyPolicy') and not value.get('ReadFailed'): value=json.loads(value['Policy'])
    snapshot[name]=value
for instance in ('t3a.small','t3.micro'):
    filters=[{'Type':'TERM_MATCH','Field':k,'Value':v} for k,v in {'instanceType':instance,'location':'US East (N. Virginia)','operatingSystem':'Linux','tenancy':'Shared','preInstalledSw':'NA','capacitystatus':'Used'}.items()]
    result=aws('pricing','get-products','--service-code','AmazonEC2','--filters',json.dumps(filters),'--max-results','10')
    rows=[]
    for product in result.get('PriceList',[]):
        product=json.loads(product)
        for term in product.get('terms',{}).get('OnDemand',{}).values():
            for dimension in term['priceDimensions'].values(): rows.append({'Unit':dimension['unit'],'USD':dimension['pricePerUnit']['USD'],'Description':dimension['description']})
    snapshot.setdefault('PriceQuotes',{})[instance]=rows or result
args.output.write_text(json.dumps(snapshot,indent=2)+'\n')
print(json.dumps({'Snapshot':str(args.output),'InstanceCount':len(snapshot['Instances']),'ReadErrors':[k for k,v in snapshot.items() if isinstance(v,dict) and v.get('ReadFailed')],'Prices':snapshot['PriceQuotes']},indent=2))
