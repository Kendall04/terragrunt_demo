"""Terraform 1.13.4 empty refresh-plan shape; disposable, no providers/backend/init."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))
from scripts.lifecycle.runtime import teardown_readback


def main():
    binary=shutil.which('terraform')
    if not binary:raise SystemExit('E15_TERRAFORM_SHAPE_UNAVAILABLE')
    env={k:v for k,v in os.environ.items() if not k.upper().startswith(('AWS','AMAZON','BOTO','TF_','TERRAGRUNT'))
         and 'PROXY' not in k.upper()}
    env.update(CHECKPOINT_DISABLE='1',AWS_EC2_METADATA_DISABLED='true',AWS_CONFIG_FILE=os.devnull,
        AWS_SHARED_CREDENTIALS_FILE=os.devnull,TF_IN_AUTOMATION='1',TF_INPUT='0')
    with tempfile.TemporaryDirectory(prefix='e15-empty-plan-') as directory:
        root=Path(directory)
        (root/'main.tf').write_text('terraform { required_version = "= 1.13.4" }\n')
        for args in (['plan','-refresh-only','-input=false','-out=empty.tfplan'],['show','-json','empty.tfplan']):
            result=subprocess.run([binary,*args],cwd=root,env=env,capture_output=True,text=True,timeout=45)
            if result.returncode!=0:raise SystemExit('E15_EMPTY_PLAN_SHAPE_FAILED')
        plan=json.loads(result.stdout)
        assert plan['format_version']=='1.2' and plan['complete'] is True and plan['errored'] is False
        assert plan['planned_values']=={'root_module':{}} and 'resource_changes' not in plan
        teardown_readback(plan)
    print('E15 actual empty Terraform plan shape PASS; no providers/backend/init/AWS')


if __name__=='__main__':main()
