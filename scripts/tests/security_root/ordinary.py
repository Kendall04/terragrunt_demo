"""Fixed extraction of ordinary TARGET configuration from pinned CURRENT files.

No generic HCL interpretation: only top-level blocks in these exact legacy files
are selected. The parent admission verifies their immutable legacy digests first.
No workflow invokes these TARGET roots; protected lifecycle execution remains WP5.
"""
from pathlib import Path
import re

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
            for path in sorted(base.rglob("*.tf")):
                rel = path.relative_to(base).as_posix()
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
                elif layer == "apps" and rel == "modules/ecs_service/taskdef.tf":
                    # Inert bootstrap: no workload roles or secrets. Real runtime
                    # role bindings are published for WP4, never inherited here.
                    text = re.sub(r'^  (?:execution_role_arn|task_role_arn)\s*=.*\n', '', text, flags=re.M)
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
