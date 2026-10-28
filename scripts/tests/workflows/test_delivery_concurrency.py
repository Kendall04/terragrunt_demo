"""Generated request job admission only; no workflow, token or AWS execution."""
import copy
import json
from pathlib import Path
import sys
import unittest
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))
from scripts.workflow_requests import render as r

def jobs(approvals):
    values=r.callers(approvals)
    return values,{
        'deploy':values['deploy-dev.yml']['jobs']['deploy'],
        'rollback-dev':values['rollback-manifest.yml']['jobs']['dev'],
        'cd':values['cd.yml']['jobs']['deploy'],
        'app-cd':values['cd-demo-api.yml']['jobs']['deploy'],
        'promote':values['promote-prod.yml']['jobs']['promote'],
        'rollback-prod':values['rollback-manifest.yml']['jobs']['prod']}

class DeliveryConcurrencyTests(unittest.TestCase):
    def test_all_dev_application_requests_share_one_noncancelling_group_across_refs(self):
        _,selected=jobs({})
        expected={'group':'e1-application-delivery-dev','cancel-in-progress':False}
        for key in ('deploy','rollback-dev','cd','app-cd'):
            with self.subTest(key=key):self.assertEqual(selected[key].get('concurrency'),expected)

    def test_prod_is_separate_but_promote_and_rollback_share_their_group(self):
        _,selected=jobs({})
        self.assertEqual(selected['promote'].get('concurrency'),
                         {'group':'e1-application-delivery-prod','cancel-in-progress':False})
        self.assertEqual(selected['promote']['concurrency'],selected['rollback-prod']['concurrency'])
        self.assertNotEqual(selected['deploy']['concurrency'],selected['promote']['concurrency'])

    def test_empty_approvals_remain_empty_permissions_no_dispatch_or_oidc(self):
        registry={};_,selected=jobs(registry)
        self.assertEqual(registry,{})
        for job in selected.values():
            self.assertEqual(job['permissions'],{})
            self.assertNotIn('uses',job);self.assertNotIn('with',job)
            self.assertIn('inactive',job['steps'][0]['run'])
            self.assertIn('exit 1',job['steps'][0]['run'])

    def test_same_queue_with_constructed_approved_pin_no_token_or_scope_changes(self):
        registry={k:{'workflow_commit':'a'*40} for k in ('deploy-dev','promote-prod')}
        original=copy.deepcopy(registry);_,selected=jobs(registry)
        self.assertEqual(registry,original)
        for key,job in selected.items():
            expected='prod' if key in ('promote','rollback-prod') else 'dev'
            self.assertEqual(job.get('concurrency'),{'group':'e1-application-delivery-'+expected,'cancel-in-progress':False})
            self.assertEqual(job['permissions'],{'contents':'read','id-token':'write'})
            self.assertTrue(job['uses'].endswith('@'+'a'*40))
            self.assertEqual(set(job['with']),{'request'})
        # Constructed registry is not installed or written anywhere.

    def test_plan_release_infra_emergency_and_reusable_entries_have_no_same_queue(self):
        values,_=jobs({})
        for name in ('release-build.yml','cd-terragrunt.yml','cd-rollback.yml','ci-terragrunt-plan.yml'):
            for job in values[name]['jobs'].values():self.assertNotIn('concurrency',job)
        for identity in ('deploy-dev','promote-prod'):
            for job in r.entry(identity)['jobs'].values():self.assertNotIn('concurrency',job)

    def test_checked_in_generated_jobs_match_without_approval_migration(self):
        authority=json.loads((ROOT/'terraform/infra/security/authority.json').read_text(encoding='utf-8'))
        self.assertEqual(authority['wp6']['approvals'],{})
        values,selected=jobs({})
        for name in ('deploy-dev.yml','rollback-manifest.yml','promote-prod.yml','cd-demo-api.yml','cd.yml'):
            self.assertEqual(json.loads((ROOT/'.github/workflows'/name).read_text(encoding='utf-8')),values[name])

if __name__=='__main__':unittest.main(verbosity=2)
