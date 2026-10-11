"""Evaluate the actual generated E2 bucket barriers, without provider/init/AWS."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
HERE=Path(__file__).resolve().parent
sys.path[:0]=[str(HERE.parents[2]),str(HERE.parent/"authority"),str(HERE.parent/"wp4d"),str(HERE.parent/"security_root")]
from evaluator import condition, matches, many
from test_wp4d import ACCOUNT,REGION,policy,permits
ROOT=HERE.parents[2]


def denied(document,action,resource,context):
    for statement in document["Statement"]:
        if not any(matches(p,action,True) for p in many(statement["Action"])):
            continue
        if "Resource" in statement and not any(matches(p,resource) for p in many(statement["Resource"])):
            continue
        if "NotResource" in statement and any(matches(p,resource) for p in many(statement["NotResource"])):
            continue
        def compare(op,key,expected):
            actual=context.get(key)
            if op in ("ArnNotEquals","StringNotEquals"):
                # These actual bucket operands are exact principal/header strings.
                assert op != "ArnNotEquals" or all("*" not in x and "?" not in x for x in many(expected))
                return actual is None or actual not in many(expected)
            return condition({op:{"fixture:k":expected}},
                             {"fixture:k":actual} if actual is not None else {})
        valid=all(compare(op,key,expected) for op,fields in
                  statement.get("Condition",{}).items() for key,expected in fields.items())
        if valid:return True
    return False


def main():
    terraform=shutil.which("terraform")
    if not terraform:raise SystemExit("E2_TERRAFORM_STATIC_UNAVAILABLE")
    tf=json.loads((ROOT/"terraform/infra/security/modules/controller_compute/main.tf.json").read_text())
    names=("wp4d_bucket_readers","wp4d_bucket_writers","e2_lifecycle_writers")
    locals_={name:tf["locals"][name] for name in names}
    authority=json.loads((ROOT/"terraform/infra/security/authority.json").read_text())
    locals_["wp4d_active"]={key:{"environment":v["environment"],"role":v["role"]}
                          for key,v in authority["wp4d"]["selected"].items()}
    env={k:v for k,v in os.environ.items() if not k.upper().startswith(
        ("AWS","AMAZON","BOTO","TF_","TERRAGRUNT")) and "PROXY" not in k.upper()}
    env.update(AWS_EC2_METADATA_DISABLED="true",AWS_CONFIG_FILE=os.devnull,
               AWS_SHARED_CREDENTIALS_FILE=os.devnull,CHECKPOINT_DISABLE="1",TF_IN_AUTOMATION="1")
    with tempfile.TemporaryDirectory(prefix="e2-static-") as directory:
        path=Path(directory)/"main.tf.json"
        path.write_text(json.dumps(dict(variable={key:{"default":value} for key,value in
            dict(account_id=ACCOUNT,admin_arn=f"arn:aws:iam::{ACCOUNT}:role/admin").items()},
            locals=locals_)),encoding="utf-8")
        for environment in ("dev","prod"):
            bucket=f"arn:aws:s3:::e1-wp4-{environment}-{ACCOUNT}-{REGION}"
            source=tf["resource"]["aws_s3_bucket_policy"]["wp4d"]["policy"][2:-1]
            source=source.replace("aws_s3_bucket.wp4d[each.key].arn",json.dumps(bucket)).replace("each.key",json.dumps(environment))
            result=subprocess.run([terraform,"console","-no-color"],input=source+"\n",cwd=directory,env=env,
                                  capture_output=True,text=True,timeout=30)
            assert result.returncode==0,result.stderr
            document=json.loads(json.loads(result.stdout))
            assert {"E2LifecycleOnlyCoordination","E2ConditionalUpdates","E2ImmutableTerminals","ExternalOnlyPublic"} <= {s["Sid"] for s in document["Statement"]}
            principal=f"arn:aws:iam::{ACCOUNT}:role/e1-controller-infra-{environment}-exec"
            context={"aws:PrincipalArn":principal,"aws:SecureTransport":"true","s3:if-match":"etag"}
            key=bucket+f"/arbitration/{environment}/application.json"
            assert not denied(document,"s3:PutObject",key,context)
            for other in ("delivery/x","history/blue.json","gateway/x",
                          "arbitration/"+("prod" if environment=="dev" else "dev")+"/application.json"):
                assert denied(document,"s3:PutObject",bucket+"/"+other,context),other
                assert denied(document,"s3:GetObject",bucket+"/"+other,context),other
            assert denied(document,"s3:DeleteObject",key,context)
            assert denied(document,"s3:PutObject",key,{k:v for k,v in context.items() if k!="s3:if-match"})
            terminal=bucket+f"/arbitration/{environment}/terminals/environment-lifecycle/infra-{environment}/id.json"
            assert denied(document,"s3:PutObject",terminal,context)
            assert not denied(document,"s3:PutObject",terminal,dict(context,**{"s3:if-none-match":"*"}))
            print(environment+": actual E2 bucket barriers PASS")
        result=subprocess.run([terraform,"validate","-no-color"],cwd=directory,env=env,
                              capture_output=True,text=True,timeout=30)
        assert result.returncode==0,result.stderr
    print("E2 provider-free generated coordination storage PASS")
if __name__=="__main__":main()
