"""Evaluate actual generated E13 resource expressions in a provider-free root.

Only console/validate, using installed Terraform. Never init, AWS or downloads.
"""
import copy
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path[:0] = [str(HERE), str(HERE.parent/"security_root"), str(HERE.parent/"authority"), str(HERE.parent/"wp4d"), str(ROOT)]
from terraform_console import decode as console_json
import wp4d
from test_wp4d import ACCOUNT, REGION, installed_projection, permits


def expression(value):
    if isinstance(value, str):
        return re.sub(r"(?<!var\.)(aws_[a-z_]+)\.", r"var.\1.", value).replace("each.key", "key").replace("each.value", "value")
    if isinstance(value, list): return [expression(v) for v in value]
    if isinstance(value, dict): return {k:expression(v) for k,v in value.items()}
    return value


def project(resource):
    fields = expression({k:v for k,v in resource.items() if k not in ("for_each", "depends_on", "lifecycle")})
    # jsonencode/jsondecode inside Terraform keeps recursively nested expressions.
    def hcl(value):
        if isinstance(value,str) and value.startswith("${") and value.endswith("}"): return value[2:-1]
        if isinstance(value,dict): return "{"+", ".join(json.dumps(k)+"="+hcl(v) for k,v in value.items())+"}"
        if isinstance(value,list): return "["+",".join(hcl(v) for v in value)+"]"
        return json.dumps(value)
    return "${{for key,value in " + expression(resource["for_each"])[2:-1] + " : key => " + hcl(fields) + "}}"


def main():
    terraform=shutil.which("terraform")
    if not terraform: raise SystemExit("E13_TERRAFORM_STATIC_UNAVAILABLE")
    doc=json.loads((ROOT/"terraform/infra/security/authority.json").read_text())
    tf=json.loads((ROOT/"terraform/infra/security/modules/controller_compute/main.tf.json").read_text())
    installs,images,bindings=installed_projection(doc)
    queues={}
    for kind in ("delivery","execution"):
        queues["nat_"+kind+"_failed"]={env:{"arn":f"arn:aws:sqs:{REGION}:{ACCOUNT}:e1-wp4-{env}-nat-{kind}-failed",
            "url":f"https://sqs.{REGION}.amazonaws.com/{ACCOUNT}/e1-wp4-{env}-nat-{kind}-failed",
            "name":f"e1-wp4-{env}-nat-{kind}-failed"} for env in ("dev","prod")}
    fake={"aws_sqs_queue":queues,"aws_cloudwatch_event_rule":{"wp4d_nat":{env:{"name":f"e1-wp4-{env}-nat-launch",
          "arn":f"arn:aws:events:{REGION}:{ACCOUNT}:rule/e1-wp4-{env}-nat-launch"} for env in ("dev","prod")}},
          "aws_lambda_function":{"wp4d":{key:{"function_name":v["name"],"version":"7",
          "qualified_arn":f"arn:aws:lambda:{REGION}:{ACCOUNT}:function:{v['name']}:7"} for key,v in doc["wp4d"]["selected"].items()}}}
    local={key:expression(value) for key,value in tf["locals"].items() if key in (
        "wp4d_contract","wp4d_candidates","wp4d_ready","wp4d_active","wp4d_gateways","wp4d_nat_events","wp4d_nat_targets","nat_failure_queues")}
    resource=tf["resource"]
    local["targets"]=project(resource["aws_cloudwatch_event_target"]["wp4d_nat"])
    # Invoke config uses the same authoritative stable target binding map.
    fake["aws_cloudwatch_event_target"]={"wp4d_nat":{key:{"arn":"synthetic"} for key in doc["wp4d"]["selected"] if key.startswith("nat-recovery/")}}
    local["invocations"]=project(resource["aws_lambda_function_event_invoke_config"]["wp4d_nat"])
    local["queue_policies"]=project(resource["aws_sqs_queue_policy"]["nat_failures"])
    local["queue_alarms"]=project(resource["aws_cloudwatch_metric_alarm"]["nat_failure_queue"])
    env={k:v for k,v in os.environ.items() if not k.upper().startswith(("AWS","AMAZON","BOTO","TF_","TERRAGRUNT")) and "PROXY" not in k.upper()}
    env.update(AWS_EC2_METADATA_DISABLED="true",AWS_CONFIG_FILE=os.devnull,AWS_SHARED_CREDENTIALS_FILE=os.devnull,CHECKPOINT_DISABLE="1")
    with tempfile.TemporaryDirectory(prefix="e13-provider-free-") as directory:
        path=Path(directory)/"main.tf.json"
        for name,i,r,b in (("undeployed",{},{},{}),("all-synthetic",installs,images,bindings)):
            values={"authority":doc,"account_id":ACCOUNT,"region":REGION,"admin_arn":f"arn:aws:iam::{ACCOUNT}:role/SeparateAdmin",
                    "wp4d_installations":i,"wp4d_runtime_approvals":r,"wp4d_environment_bindings":b,"dev_delivery_binding":None,**fake}
            # Inert resources must also stay inert in the synthetic provider map.
            local_case=copy.deepcopy(local)
            if name=="undeployed":
                values["aws_sqs_queue"]={k:{} for k in queues}
                values["aws_cloudwatch_event_target"]={"wp4d_nat":{}}
            variables={key:{"type":"any","default":value} for key,value in values.items()}
            path.write_text(json.dumps({"variable":variables,"locals":local_case}),encoding="utf-8")
            query='jsonencode({targets=local.targets,invocations=local.invocations,queues=local.nat_failure_queues,policies=local.queue_policies,alarms=local.queue_alarms})'
            result=subprocess.run([terraform,"console","-no-color"],input=query+"\n",text=True,capture_output=True,cwd=directory,env=env,timeout=30)
            if result.returncode: raise AssertionError(name+": "+result.stderr)
            try: actual=console_json(result.stdout)
            except json.JSONDecodeError: raise AssertionError((name,result.stdout[:500],result.stderr[-2500:]))
            if name=="undeployed":
                assert all(not value for value in actual.values()),actual
            else:
                assert len(actual["targets"])==6 and len(actual["invocations"])==6 and len(actual["queues"])==4
                for binding,target in actual["targets"].items():
                    environment=doc["wp4d"]["selected"][binding]["environment"]
                    assert target["dead_letter_config"]["arn"]==queues["nat_delivery_failed"][environment]["arn"]
                    assert target["retry_policy"]==dict(maximum_event_age_in_seconds=900,maximum_retry_attempts=3)
                    invocation=actual["invocations"][binding]
                    assert invocation["qualifier"]=="7" and invocation["maximum_retry_attempts"]==1
                    assert invocation["destination_config"]["on_failure"]["destination"]==queues["nat_execution_failed"][environment]["arn"]
                for key,record in actual["policies"].items():
                    environment,kind=key.split("/"); policy=json.loads(record["policy"])
                    send=[v for v in policy["Statement"] if v["Action"]=="sqs:SendMessage"]
                    assert len(send)==1 and send[0]["Resource"]==queues["nat_"+kind+"_failed"][environment]["arn"]
                    if kind=="delivery":
                        assert send[0]["Principal"]=={"Service":"events.amazonaws.com"}
                        assert send[0]["Condition"]=={"ArnEquals":{"aws:SourceArn":fake["aws_cloudwatch_event_rule"]["wp4d_nat"][environment]["arn"]},"StringEquals":{"aws:SourceAccount":ACCOUNT}}
                    else:
                        assert send[0]["Principal"]["AWS"]==[f"arn:aws:iam::{ACCOUNT}:role/{v['role']}" for k,v in sorted(doc["wp4d"]["selected"].items()) if k.startswith("nat-recovery/") and v["environment"]==environment]
                    assert actual["alarms"][key]["alarm_actions"]==[f"arn:aws:sns:{REGION}:{ACCOUNT}:demo-{environment}"+("-shared" if environment=="dev" else "")+"-alerts"]
            print(name+": actual Terraform retry/destination/queue-policy/alert projection PASS")
        result=subprocess.run([terraform,"validate","-no-color"],text=True,capture_output=True,cwd=directory,env=env,timeout=30)
        if result.returncode: raise AssertionError(result.stderr)
    print("E13 provider-free expressions PASS; provider schemas/live delivery remain unverified")


if __name__=="__main__": main()
