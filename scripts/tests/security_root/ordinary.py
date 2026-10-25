"""Fixed extraction of ordinary TARGET configuration from pinned retired text.

No generic HCL interpretation: only reviewed blocks in these inert data inputs
are selected. Parent admission verifies immutable digests and forbids restored
legacy roots. Only protected WP5 lifecycle selects the resulting TARGET modules.
"""
from pathlib import Path
import re
import retired

ROOT = Path(__file__).resolve().parents[3]
BLOCK = re.compile(r'(?m)^(resource|data|module|variable|output|locals|terraform)\b[^\n]*')


def select(text, allowed):
    starts = list(BLOCK.finditer(text))
    return "\n".join(text[m.start():starts[i + 1].start() if i + 1 < len(starts) else len(text)].rstrip()
                     for i, m in enumerate(starts) if allowed(m.group())) + "\n"


def wiring(doc):
    result = {}
    for env in ("dev", "prod"):
        for layer, source in (("shared", "shared"), ("data", "data"), ("apps", "apps/fargate"), ("global", "global")):
            base = ROOT / "terraform/infra" / source
            for rel, path in retired.sources(ROOT, "terraform/infra/" + source):
                # These declarations are now exclusively neutral-owned. Recovery
                # behavior is reserved, not copied as an executable target.
                if layer == "shared" and (rel.startswith("modules/") or rel == "release_artifacts_bucket.tf"):
                    continue
                if layer == "apps" and (rel in ("iam_lambda_scale_down.tf", "lambda_scale_down.tf", "outputs.tf") or rel.endswith("/iam.tf")):
                    continue
                if layer == "global" and rel.startswith("modules/nat/"):
                    continue
                text = path.read_text(encoding="utf-8")
                if layer == "shared" and rel == "locals.tf":
                    text = 'locals {\n  name = "demo-' + env + '-shared"\n  tags = { Project = "demo", Environment = "' + env + '", ManagedBy = "terraform", Owner = "kendall" }\n}\n'
                elif layer == "shared" and rel == "main.tf":
                    text = select(text, lambda h: h.startswith('resource "aws_sns_'))
                elif layer == "shared" and rel == "outputs.tf":
                    text = select(text, lambda h: h.startswith('output "alerts_topic_arn"'))
                elif layer == "data" and rel == "main.tf":
                    text = select(text, lambda h: '"aws_iam_' not in h)
                    text = text.replace("aws_iam_instance_profile.ec2_profile.name", 'split("/", local.expected["' + env + '/sql-profile"])[1]')
                    text = text.replace("var.kms_key_id", "null")
                    if env == "dev":
                        text = text.replace("subnet_id                   = var.private_subnet_ids[0]", "subnet_id                   = coalesce(var.recovery_target_subnet_id, var.private_subnet_ids[0])")
                    text = text.replace("var.sql_sa_secret_arn", 'local.expected["' + env + '/sa"]').replace("var.sql_app_secret_arn", 'local.expected["' + env + '/db-user"]')
                    # The immutable CURRENT script is a source input, never an
                    # ordinary caller path. Its digest is separately pinned.
                    text = text.replace('${path.module}/user_data.sh', '${path.module}/../../../../infra/data/user_data.sh')
                elif layer == "global" and rel == "main.tf":
                    text = select(text, lambda h: not h.startswith('module "nat"'))
                    text = text.replace('source = "./modules/vpc"', 'source = "./modules/vpc"\n  protected_flow_role = local.expected["' + env + '/flow"]')
                elif layer == "global" and rel == "modules/vpc/vpc.tf":
                    text = select(text, lambda h: '"aws_iam_' not in h)
                    text = text.replace("aws_iam_role.vpc_flow_logs.arn", "var.protected_flow_role")
                    text += '\nvariable "protected_flow_role" { type = string }\n'
                elif layer == "apps" and rel == "demo.tf":
                    text = select(text, lambda h: h.startswith('module "demo_api_'))
                    text = re.sub(r'  (?:task_policy_arns|execution_policy_arns) = \[[\s\S]*?\n  \]\n', '', text)
                    text = re.sub(r'  secrets = \{[\s\S]*?\n  \}', '  secrets = {}', text)
                    text = text.replace("var.kms_key_id", 'local.expected["' + env + '/kms"]')
                    if env == "dev":
                        # ECS Exec needs a task role; the inert bootstrap has none.
                        text = text.replace("  desired_count = 0", "  enable_execute_command = false\n\n  desired_count = 0")
                elif layer == "apps" and rel == "modules/ecs_service/taskdef.tf":
                    # Inert bootstrap: no workload roles or secrets. Real runtime
                    # role bindings are published for WP4, never inherited here.
                    text = re.sub(r'^  (?:execution_role_arn|task_role_arn)\s*=.*\n', '', text, flags=re.M)
                elif env == "dev" and layer == "apps" and rel == "modules/ecs_service/locals.tf":
                    # Role-free, zero-count bootstrap cannot use awslogs on Fargate.
                    # Keep the log groups and the real WP4 task template unchanged.
                    block = '''      logConfiguration = {
        logDriver = "awslogs"
        options = {
          awslogs-group         = aws_cloudwatch_log_group.this.name
          awslogs-region        = data.aws_region.current.name
          awslogs-stream-prefix = coalesce(var.container_name, var.name)
        }
      }
'''
                    assert text.count(block) == 1, "reviewed inert bootstrap log block"
                    text = text.replace(block, "")
                elif env == "dev" and layer == "apps" and rel == "modules/ecs_service/logs.tf":
                    text = text.replace('data "aws_region" "current" {}\n', '')
                elif layer == "apps" and rel == "modules/ecs_service/outputs.tf":
                    text = select(text, lambda h: not h.startswith(('output "task_role_arn"', 'output "execution_role_arn"')))
                if rel == "variables.tf":
                    remove = {"env", "project", "aws_region"}
                    if layer == "data":
                        remove |= {"sql_sa_secret_arn", "sql_app_secret_arn", "secret_kms_key_arn"}
                    if layer == "apps":
                        remove |= {"kms_key_id", "kms_key_arn", "db_secret_arn"}
                    if layer == "data":
                        remove.add("kms_key_id")
                    text = select(text, lambda h: (h.startswith('variable "alert_email"') if layer == "shared" else not any(h.startswith('variable "' + name + '"') for name in remove)))
                if env == "dev" and layer == "data" and rel == "variables.tf":
                    text += '\nvariable "recovery_target_subnet_id" {\n  description = "Explicit reviewed recovery target; null preserves original placement. Membership is not native VPC/AZ proof."\n  type = string\n  default = null\n  nullable = true\n  validation {\n    condition = var.recovery_target_subnet_id == null ? true : can(regex("^subnet-[0-9a-f]{8,17}$", var.recovery_target_subnet_id)) && contains(var.private_subnet_ids, var.recovery_target_subnet_id)\n    error_message = "Recovery target must be one of the reviewed private subnets."\n  }\n}\n'
                if env == "dev" and layer == "shared":
                    if rel == "main.tf":
                        text = text.replace('resource "aws_sns_topic_subscription" "alerts_email" {',
                            'resource "aws_sns_topic_subscription" "alerts_email" {\n  count     = var.alert_email == null ? 0 : 1')
                    elif rel == "variables.tf":
                        text = text.replace('  type        = string', '  type        = string\n  default     = null')
                        text = text.replace('Email to receive CloudWatch alarms', 'Optional confirmed recipient; null leaves email notifications inactive')
                    elif rel == "outputs.tf":
                        text += '\noutput "alerts_email_configured" {\n  value       = var.alert_email != null\n  description = "Configured is not confirmed delivery; pending SNS confirmation cannot receive email"\n}\n'
                if "/" not in rel:
                    text = text.replace("var.env", '"' + env + '"').replace("var.project", '"demo"').replace("var.aws_region", "var.region")
                    # Simplify interpolated literal values for HCL readability.
                    text = text.replace('${"demo"}', 'demo').replace('${"' + env + '"}', env)
                if layer == "global" and rel == "main.tf":
                    text = text.replace('  source = "./modules/vpc"', '  source              = "./modules/vpc"').replace("  name   = local.name", "  name                = local.name").replace("  tags   = local.tags", "  tags                = local.tags").replace("  azs    = local.azs", "  azs                 = local.azs")
                text = "\n".join(line for line in text.splitlines() if not line.lstrip().startswith("#")) + "\n"
                text = text.encode("ascii", "ignore").decode("ascii").rstrip() + "\n"
                result["terraform/modules/target/" + env + "/" + layer + "/ordinary-" + rel if "/" not in rel else "terraform/modules/target/" + env + "/" + layer + "/" + rel] = text
    return result
