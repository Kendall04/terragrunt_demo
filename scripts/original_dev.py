"""Thin DEV-only operator over the existing WP6 entry client.

Execution belongs in the approved, immutable GitHub entry job. A local terminal
cannot supply trusted OIDC or install IAM. No direct Terraform/AWS fallback.
"""
import argparse
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.lifecycle import contract as lifecycle
from scripts.workflow_requests import client, contract as workflow


def require(ok, reason):
    if not ok:
        raise ValueError('ORIGINAL_DEV_BLOCKED: ' + reason)


def select(action, raw):
    value = workflow.decode(raw)
    if action == 'up':
        require(value.get('operation') == 'create', 'UP accepts create only; existing/partial state needs protected reconciliation')
        layer = value.get('layer')
        require(layer in lifecycle.LAYERS, 'original layer only')
        identity = 'infra-high-risk-dev' if layer in ('data', 'apps') else 'infra-dev'
    elif action == 'plan':
        require(value.get('operation') == 'plan', 'read-only plan only')
        identity = 'plan-dev'
    elif action == 'verify-infrastructure':
        require(value == {'operation': 'preflight', 'layer': 'apps'}, 'existing installed ECS/ALB preflight only')
        identity = 'plan-dev'
    elif action == 'release':
        identity = 'release'
    elif action == 'deploy':
        require(value.get('action') == 'deliver', 'normal qualified delivery only')
        identity = 'deploy-dev'
    else:
        require(False, 'no supported execution authority')
    workflow.request(identity, raw)
    return identity


def main(argv=None):
    selected = list(sys.argv[1:] if argv is None else argv)
    if selected[:1] == ['dev']:
        from scripts.practical_dev import main as supervised
        try:return supervised(selected[1:])
        except (ValueError, KeyError, OSError) as error:
            print('E16 stopped: '+str(error)+'; preserve session/state, inspect status/residual, reconcile before a new reviewed plan. Possible EC2/Fargate/ALB/EBS/IPv4 charges.',file=sys.stderr)
            return 1
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('plan', 'up', 'release', 'deploy', 'verify-infrastructure', 'down', 'residual'))
    parser.add_argument('--account', required=True)
    parser.add_argument('--region', required=True)
    parser.add_argument('--request-file', type=Path)
    args = parser.parse_args(argv)
    workflow.match('[0-9]{12}', args.account)
    workflow.match('[a-z]{2}(?:-[a-z]+)+-[0-9]', args.region)
    if args.action == 'down':
        require(False, 'whole DOWN requires installed E15-G five-plan preparation, E15-C/D approvals, original E2 owner, authenticated ECS/NAT effect closure and residual observer; no public execution route')
    if args.action == 'residual':
        require(False, 'protected E15-G residual observer uninstalled; local declaration notes cannot certify AWS absence or billing')
    require(args.request_file is not None, 'exact reviewed request file required')
    raw = args.request_file.read_text(encoding='utf-8')
    identity = select(args.action, raw)
    # Same installed client configuration, source/governance and OIDC validation.
    # This helper does not choose role ARNs, backend keys or controller resources.
    configuration = client.configuration(identity, os.environ.get('E1_REQUEST_CONFIGURATION', '{}'))
    require(configuration['account'] == args.account and configuration['region'] == args.region, 'exact account/region must match protected configuration')
    require('ACTIONS_ID_TOKEN_REQUEST_URL' in os.environ and 'ACTIONS_ID_TOKEN_REQUEST_TOKEN' in os.environ, 'approved WP6 entry job required; no local credential fallback')
    previous_argv, previous_request = sys.argv, os.environ.get('E1_REQUEST')
    try:
        sys.argv = [client.__file__, identity]
        os.environ['E1_REQUEST'] = raw
        client.main()  # Real existing invoke-once / sanitized-status path.
    finally:
        sys.argv = previous_argv
        if previous_request is None:
            os.environ.pop('E1_REQUEST', None)
        else:
            os.environ['E1_REQUEST'] = previous_request
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (ValueError, KeyError, OSError, RuntimeError):
        raise SystemExit('ORIGINAL_DEV_REQUEST_FAILED: preserve operation UUID/state; do not resend; see terraform/docs/original-full-lifecycle.md') from None
