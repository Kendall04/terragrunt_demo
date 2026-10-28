"""Source facts/proposal coherence only, not provider/schema/plan evidence."""
import json,re,unittest
from pathlib import Path
class Wiring(unittest.TestCase):
 def setUp(self):self.x=json.loads((Path(__file__).parent/'wiring-proposal.json').read_text())
 def test_provider_not_silently_downgraded_or_global_updated(self):
  p=self.x['provider'];self.assertFalse(p['compatibleWith5_100']);self.assertEqual(p['upstreamMinimum'],'6.28.0');self.assertFalse(p['globalUpgradeAllowed']);self.assertIn('b3d0b3b595a9257bb6d4d849c899bf4e8dbc2828',self.x['source'])
 def test_forecast_explicit_and_not_plan_or_old_authority(self):
  c=self.x['counts'];self.assertEqual(c['proposedCombinedAddresses'],c['upstreamExpandedAddressesWithReports']+4+3);self.assertFalse(c['actualTerraformPlan']);self.assertFalse(c['previous102AndUsd6Applicable']);self.assertFalse(self.x['inputs']['enabled'])
 def test_workload_iam_only_own_bus_and_no_backups_secrets_or_ssm(self):
  p=self.x['runtimePermissions']['producer'];self.assertEqual(p['Action'],['events:PutEvents']);self.assertEqual(p['Resource'],'arn:aws:events:us-east-1:341936017254:event-bus/'+self.x['scope']['candidateDeployment']);self.assertEqual(p['Conditions']['events:source'],'sentinel.report.sql-observer');self.assertFalse(self.x['host']['newObserverEc2']);self.assertIn('ssm',self.x['runtimePermissions']['noRuntimeGrants'])
 def test_boundaries_retention_and_retirement_are_not_hidden(self):
  self.assertFalse(self.x['boundaries']['upstreamSuppliesThem']);self.assertIn('protection removal',self.x['deploymentLifecycleProposal']['retire']);self.assertEqual(self.x['deploymentLifecycleProposal']['originalSqlBackupsRetention'],'2+2 days unchanged');self.assertFalse(self.x['installed'])
if __name__=='__main__':unittest.main(verbosity=2)
