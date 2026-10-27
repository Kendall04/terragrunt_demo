"""Prepare isolated module/lock from exact upstream source. No init, plan or AWS."""
import argparse,hashlib,json,subprocess
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--terraform',type=Path,required=True);p.add_argument('--trial-root',action='store_true');p.add_argument('--package-manifest',type=Path);p.add_argument('--config',type=Path);p.add_argument('--zip',type=Path);a=p.parse_args();B=Path(__file__).parent
proposal=json.loads((B/'wiring-proposal.json').read_text());assert subprocess.check_output(['git','-C',str(a.source),'rev-parse','HEAD'],text=True).strip()==proposal['upstreamCommit']
original=(a.source/'deploy/portable/main.tf').read_text(encoding='utf-8');assert hashlib.sha256(original.encode()).hexdigest()==proposal['upstreamModuleSha256'];assert not a.output.exists();M=a.output;M.mkdir(parents=True)
s=original
name_line='  name   = local.config.deployment\n'
assert s.count(name_line)==1
s=s.replace(name_line,name_line+'  archive_bucket_name = "snt-${lower(local.name)}-${local.config.account}-${local.config.region}"\n')
bucket_begin=s.index('resource "aws_s3_bucket" "archive" {');bucket_end=s.index('\n}\n',bucket_begin)+2
s=s[:bucket_begin]+'resource "aws_s3_bucket" "archive" {\n  bucket        = local.archive_bucket_name\n  force_destroy = false\n  lifecycle {\n    precondition {\n      condition = length(local.archive_bucket_name) <= 63 && can(regex("^snt-[a-z0-9][a-z0-9-]*[a-z0-9]$", local.archive_bucket_name)) && alltrue([\n        for suffix in ["-s3alias", "--ol-s3", "--x-s3", "--table-s3", "-an"] : !endswith(local.archive_bucket_name, suffix)\n      ])\n      error_message = "Sentinel archive requires the snt- namespace and a valid shared-namespace S3 name, at most 63 characters; no truncation or legacy bucket fallback."\n    }\n  }\n}'+s[bucket_end:]
begin=s.index('resource "aws_iam_role_policy" "runtime" {');end=s.index('\n}\n',begin)+2;block=s[begin:end];policy=block[block.index('jsonencode('):].rsplit('\n}',1)[0].strip();assert policy.endswith('})')
local='locals {\n  ecs_runtime_policies = { for component in local.roles : component => '+policy.replace('each.key','component')+' }\n}\n'
replacement='resource "aws_iam_role_policy" "runtime" {\n  for_each = local.roles\n  role = aws_iam_role.runtime[each.key].id\n  policy = local.ecs_runtime_policies[each.key]\n}'
s=s[:begin]+local+replacement+s[end:]
old='  name               = "${local.name}-${each.key}"\n  assume_role_policy';assert s.count(old)==1
s=s.replace(old,'  name               = "${local.name}-${each.key}"\n  permissions_boundary = aws_iam_policy.ecs_boundary[each.key].arn\n  tags = { Project = local.config.project, Deployment = local.name, ManagedBy = "Terraform", Component = "sentinel-portable" }\n  assume_role_policy')
s+='\nresource "aws_iam_policy" "ecs_boundary" {\n  for_each = local.roles\n  name = "${local.name}-${each.key}-boundary"\n  policy = local.ecs_runtime_policies[each.key]\n}\n'
s=s.replace('Sentinel.Portable.Lambda::Sentinel.Portable.Lambda.Function::${local.handlers[each.key]}','Ecs.Backup.Portable.Host::Ecs.Backup.Portable.Host.Function::${local.handlers[each.key]}')
s=s.replace('locals {\n  config','variable "alarm_notices_enabled" {\n  type = bool\n  default = false\n}\nlocals {\n  config',1)
assert s.count('actions_enabled     = var.enabled')==3
s=s.replace('actions_enabled     = var.enabled','actions_enabled     = var.enabled && var.alarm_notices_enabled')
if a.trial_root:
 assert a.package_manifest and a.config and a.zip
 child=M/'runtime';child.mkdir();(child/'main.tf').write_text(s,encoding='utf-8',newline='\n');(child/'outputs.tf').write_bytes((B/'trial/runtime/outputs.tf').read_bytes())
 (M/'main.tf').write_bytes((B/'trial/main.tf').read_bytes());(M/'tests').mkdir()
 template=(B/'trial/tests/portable.tftest.hcl').read_text()
 for marker,value in [('@CONFIG@',a.config),('@ZIP@',a.zip),('@RECEIPT@',a.package_manifest),('@BADZIP@',M/'main.tf')]:template=template.replace(marker,value.resolve().as_posix())
 (M/'tests/portable.tftest.hcl').write_text(template,encoding='utf-8',newline='\n')
else:
 (M/'main.tf').write_text(s,encoding='utf-8',newline='\n')
(M/('versions.tf' if a.trial_root else 'versions_override.tf')).write_text('terraform {\n required_providers {\n  aws = { source = "hashicorp/aws", version = "= 6.28.0" }\n }\n}\n',encoding='utf-8')
(M/'.terraform.lock.hcl').write_bytes((B/'aws-6.28.lock.hcl').read_bytes())
subprocess.run([str(a.terraform),'-chdir='+str(M),'fmt','-recursive','-no-color'],check=True)
(M/'ecs-module-receipt.json').write_text(json.dumps({'upstreamCommit':proposal['upstreamCommit'],'upstreamSha256':proposal['upstreamModuleSha256'],'preparedSha256':hashlib.sha256((M/'main.tf').read_bytes()).hexdigest(),'provider':'6.28.0','appliedToAws':False},indent=2)+'\n',encoding='utf-8')
