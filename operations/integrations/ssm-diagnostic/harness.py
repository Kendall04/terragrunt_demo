#!/usr/bin/env python3
"""Exact observer control('status'), isolated config, no units/checker installed."""
import argparse,hashlib,importlib.util,json
from pathlib import Path
BASE=Path('/opt/terragrunt-demo/ssm-diagnostic')
def status(base=BASE):
    if base.is_symlink() or any(v.is_symlink() for v in base.parents):raise ValueError('SAFE_BASE_REQUIRED')
    config=json.loads((base/'harness-config.json').read_text(encoding='utf-8'))
    if set(config)!={'observerSha256'}:raise ValueError('HARNESS_CONFIG')
    source=base/'observer_host.py'
    if source.is_symlink() or hashlib.sha256(source.read_bytes()).hexdigest()!=config['observerSha256']:raise ValueError('SOURCE_CHANGED')
    spec=importlib.util.spec_from_file_location('diagnostic_observer',source);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    # Only paths differ. Actual host config validation, status/systemctl and uncertainty
    # semantics are unchanged. No replacement/mocking of status on the native host.
    module.BASE=base;module.STATE=base/'state'
    result=module.control('status')
    return result|{'diagnosticOnly':True,'checkerInstalled':False,'backupAcceptance':False}
def main():
    p=argparse.ArgumentParser();p.add_argument('--action',required=True,choices=['status']);p.parse_args()
    print(json.dumps(status(),sort_keys=True))
if __name__=='__main__':main()
