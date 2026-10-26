"""Prepare isolated module/lock from exact upstream source. No init, plan or AWS."""
import argparse,hashlib,json,subprocess
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--terraform',type=Path,required=True);a=p.parse_args();B=Path(__file__).parent
proposal=json.loads((B/'wiring-proposal.json').read_text());assert subprocess.check_output(['git','-C',str(a.source),'rev-parse','HEAD'],text=True).strip()==proposal['upstreamCommit']
original=(a.source/'deploy/portable/main.tf').read_text(encoding='utf-8');assert hashlib.sha256(original.encode()).hexdigest()==proposal['upstreamModuleSha256'];assert not a.output.exists();M=a.output;M.mkdir(parents=True)
s=original;begin=s.index('resource "aws_iam_role_policy" "runtime" {');end=s.index('\n}\n',begin)+2;block=s[begin:end];policy=block[block.index('jsonencode('):].rsplit('\n}',1)[0].strip();assert policy.endswith('})')
local='locals {\n  ecs_runtime_policies = { for component in local.roles : component => '+policy.replace('each.key','component')+' }\n}\n'
replacement='resource "aws_iam_role_policy" "runtime" {\n  for_each = local.roles\n  role = aws_iam_role.runtime[each.key].id\n  policy = local.ecs_runtime_policies[each.key]\n}'
s=s[:begin]+local+replacement+s[end:]
old='  name               = "${local.name}-${each.key}"\n  assume_role_policy';assert s.count(old)==1
s=s.replace(old,'  name               = "${local.name}-${each.key}"\n  permissions_boundary = aws_iam_policy.ecs_boundary[each.key].arn\n  tags = { Project = local.config.project, Deployment = local.name, ManagedBy = "Terraform", Component = "sentinel-portable" }\n  assume_role_policy')
s+='\nresource "aws_iam_policy" "ecs_boundary" {\n  for_each = local.roles\n  name = "${local.name}-${each.key}-boundary"\n  policy = local.ecs_runtime_policies[each.key]\n}\n'
s=s.replace('Sentinel.Portable.Lambda::Sentinel.Portable.Lambda.Function::${local.handlers[each.key]}','Ecs.Backup.Portable.Host::Ecs.Backup.Portable.Host.Function::${local.handlers[each.key]}')
(M/'main.tf').write_text(s,encoding='utf-8',newline='\n')
(M/'versions_override.tf').write_text('terraform {\n required_providers {\n  aws = { source = "hashicorp/aws", version = "= 6.28.0" }\n }\n}\n',encoding='utf-8')
(M/'.terraform.lock.hcl').write_bytes((B/'aws-6.28.lock.hcl').read_bytes())
subprocess.run([str(a.terraform),'-chdir='+str(M),'fmt','-no-color'],check=True)
(M/'ecs-module-receipt.json').write_text(json.dumps({'upstreamCommit':proposal['upstreamCommit'],'upstreamSha256':proposal['upstreamModuleSha256'],'preparedSha256':hashlib.sha256((M/'main.tf').read_bytes()).hexdigest(),'provider':'6.28.0','appliedToAws':False},indent=2)+'\n',encoding='utf-8')
