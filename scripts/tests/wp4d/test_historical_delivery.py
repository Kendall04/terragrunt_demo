"""Closed historical DEV preservation; synthetic fixtures are never approval.

Private live-readback tests separately verify the three production fingerprints.
CI exercises identical generated predicates with explicit synthetic fingerprints;
it never publishes the private VersionIds, image URIs or installed configuration.
"""
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import wp4d
from test_wp4d import installed_projection, ACCOUNT, REGION, ROOT
from terraform_console import decode


def fixture():
    doc = json.loads((ROOT / "terraform/infra/security/authority.json").read_text())
    installs, images, bindings = installed_projection(doc)
    pins = copy.deepcopy(wp4d.HISTORICAL_DELIVERY)
    for key, pin in pins.items():
        install, runtime = installs[key], images[key]
        install.update(sha256=pin["package_sha256"],
                       key="bundles/sha256/" + pin["package_sha256"] + ".json",
                       source_commit=wp4d.HISTORICAL_SOURCE)
        for field in ("installation", "version_origin", "publisher"):
            install.pop(field)
        runtime.update(package_sha256=pin["package_sha256"], approval="PENDING_NEW_APPROVAL")
        identity = wp4d.historical_identity(key, doc["wp4d"]["selected"][key],
            install, runtime, bindings["dev"], ACCOUNT, REGION,
            f"demo-release-artifacts-{ACCOUNT}")
        pin["installation_sha256"] = hashlib.sha256(wp4d.canonical(identity).rstrip(b"\n")).hexdigest()
    return doc, installs, images, bindings, pins


class HistoricalDelivery(unittest.TestCase):
    def test_allowlist_is_exact_and_separate_from_current_catalog(self):
        doc, _, _, _, _ = fixture()
        self.assertEqual(set(wp4d.HISTORICAL_DELIVERY), {
            "request-gateway/deploy-dev", "normal-delivery/deploy-dev", "cleanup-recovery/cleanup-dev"})
        self.assertEqual(wp4d.HISTORICAL_SOURCE, "57c8c0b46f875d60b5144040309d5e3d2bf2c3c6")
        for key, pin in wp4d.HISTORICAL_DELIVERY.items():
            self.assertNotEqual(pin["package_sha256"], doc["wp4d"]["selected"][key]["package_sha256"])
            self.assertIn('["' + key + '"]', pin["address"])

    def test_source_fingerprints_cannot_be_supplied_by_caller(self):
        doc, i, r, b, pins = fixture()
        active = wp4d.creation_supported(doc, i, r, b, ACCOUNT, REGION, preservation_approval="a"*64)
        self.assertTrue(set(wp4d.HISTORICAL_DELIVERY).isdisjoint(active))
        self.assertNotEqual(pins, wp4d.HISTORICAL_DELIVERY)

    def test_closed_fixture_preserves_all_three_without_fabricated_history(self):
        doc, i, r, b, pins = fixture()
        with patch.dict(wp4d.HISTORICAL_DELIVERY, pins, clear=True):
            active = wp4d.creation_supported(doc, i, r, b, ACCOUNT, REGION, preservation_approval="a"*64)
        self.assertTrue(set(pins) <= set(active))
        for key in pins:
            self.assertNotIn("version_origin", i[key])
            self.assertEqual(r[key]["approval"], "PENDING_NEW_APPROVAL")

    def test_approval_v1_and_delivery_inhibition_are_required(self):
        doc, i, r, b, pins = fixture()
        cases = ({}, {"preservation_approval":"invalid"},
                 {"preservation_approval":"a"*64, "dev_delivery_inhibited":False},
                 {"preservation_approval":"a"*64, "delivery_contract":"SQL_RESTORE_NO_MIGRATIONS_V2"})
        with patch.dict(wp4d.HISTORICAL_DELIVERY, pins, clear=True):
            for options in cases:
                with self.subTest(options=options):
                    self.assertTrue(set(pins).isdisjoint(wp4d.creation_supported(
                        doc, i, r, b, ACCOUNT, REGION, **options)))

    def test_every_identity_dimension_rejects_drift(self):
        doc, installs, images, bindings, pins = fixture()
        for field in ("sha256", "key", "bucket", "version_id", "source_commit", "binding"):
            i = copy.deepcopy(installs)
            for key in pins: i[key][field] = "foreign"
            with self.subTest(field=field), patch.dict(wp4d.HISTORICAL_DELIVERY, pins, clear=True):
                self.assertTrue(set(pins).isdisjoint(wp4d.creation_supported(
                    doc, i, images, bindings, ACCOUNT, REGION, preservation_approval="a"*64)))
        for field in ("uri", "binding", "package_sha256", "owner"):
            r = copy.deepcopy(images)
            for key in pins: r[key][field] = "foreign"
            with self.subTest(field=field), patch.dict(wp4d.HISTORICAL_DELIVERY, pins, clear=True):
                self.assertTrue(set(pins).isdisjoint(wp4d.creation_supported(
                    doc, installs, r, bindings, ACCOUNT, REGION, preservation_approval="a"*64)))
        with patch.dict(wp4d.HISTORICAL_DELIVERY, pins, clear=True):
            for kwargs in ({"account":"999999999999"}, {"region":"eu-west-1"},
                           {"evidence_bucket":"foreign"}):
                options={"account":ACCOUNT,"region":REGION,"preservation_approval":"a"*64,**kwargs}
                self.assertTrue(set(pins).isdisjoint(wp4d.creation_supported(doc,installs,images,bindings,**options)))

    def test_resource_bindings_names_and_dependencies_cannot_change(self):
        doc, i, r, b, pins = fixture()
        with patch.dict(wp4d.HISTORICAL_DELIVERY, pins, clear=True):
            bad = copy.deepcopy(b); bad["dev"]["colors"]["blue"]["cluster"] = "foreign"
            self.assertTrue(set(pins).isdisjoint(wp4d.creation_supported(
                doc,i,r,bad,ACCOUNT,REGION,preservation_approval="a"*64)))
            bad = copy.deepcopy(doc)
            for key in pins: bad["wp4d"]["selected"][key]["name"] = "foreign"
            self.assertTrue(set(pins).isdisjoint(wp4d.creation_supported(
                bad,i,r,b,ACCOUNT,REGION,preservation_approval="a"*64)))
            missing = copy.deepcopy(i); missing.pop("cleanup-recovery/cleanup-dev")
            self.assertTrue(set(pins).isdisjoint(wp4d.creation_supported(
                doc,missing,r,b,ACCOUNT,REGION,preservation_approval="a"*64)))

    def test_nat_prod_and_current_catalog_remain_unchanged(self):
        doc, i, r, b, _ = fixture()
        keys=set(doc["wp4d"]["selected"])-set(wp4d.HISTORICAL_DELIVERY)
        old=wp4d.creation_supported(doc,i,r,b,ACCOUNT,REGION)
        new=wp4d.creation_supported(doc,i,r,b,ACCOUNT,REGION,preservation_approval="a"*64)
        self.assertEqual(set(old)&keys,set(new)&keys)
        with patch.dict(wp4d.HISTORICAL_DELIVERY, fixture()[4], clear=True):
            self.assertTrue(set(wp4d.HISTORICAL_DELIVERY) <= set(wp4d.creation_supported(
                doc,i,r,b,ACCOUNT,REGION,preservation_approval="a"*64,dev_nat_inhibited=False)))


def check_terraform(terraform, environment):
    """Provider-free checks of actual generated gates/config, not a plan."""
    doc,i,r,b,pins=fixture()
    tf=json.loads((ROOT/'terraform/infra/security/modules/controller_compute/main.tf.json').read_text())
    local={k:v for k,v in tf['locals'].items() if k in (
        'nodes','wp4d_contract','wp4d_candidates','wp4d_historical_installations','wp4d_historical_ready',
        'wp4d_ready','wp4d_active','wp4d_gateways','wp4d_projects','wp4d_project_names','wp4d_config')}
    local['evidence_bucket']=f'demo-release-artifacts-{ACCOUNT}'
    # Closed, explicitly synthetic installation fingerprints; production pins
    # stay fixed in source and are never inputs to the real Terraform module.
    local['wp4d_historical_installations']=pins
    conditions=tf['variable']['dev_delivery_preservation_approval_sha256']['validation']['condition']
    precondition=tf['output']['wp4d']['precondition']['condition']
    with tempfile.TemporaryDirectory(prefix='historical-dev-provider-free-') as directory:
        path=Path(directory)/'main.tf.json'
        def evaluate(installs=i,images=r,binding=b['dev'],approval='a'*64,limited=True,nat=True,delivery=True,contract='V1'):
            values={'authority':doc,'account_id':ACCOUNT,'region':REGION,'wp4d_installations':installs,
                'wp4d_runtime_approvals':images,'wp4d_environment_bindings':b,'dev_delivery_binding':binding,
                'dev_delivery_contract':contract,'dev_nat_inhibited':nat,'dev_delivery_inhibited':delivery,
                'dev_delivery_preservation_approval_sha256':approval,'dev_cicd_installation_only':limited}
            configuration={'variable':{k:{'type':'any','default':v} for k,v in values.items()},
                'locals':{**local,'input_valid':conditions,'preservation_valid':precondition}}
            path.write_text(json.dumps(configuration),encoding='utf-8')
            query='jsonencode({active=keys(local.wp4d_active),ready=keys(local.wp4d_ready),historical=keys(local.wp4d_historical_ready),config=local.wp4d_config,valid=local.input_valid,preserved=local.preservation_valid})'
            run=subprocess.run([terraform,'console','-no-color'],input=query+'\n',capture_output=True,
                text=True,cwd=directory,env=environment,timeout=30)
            if run.returncode:raise AssertionError(run.stderr)
            return decode(run.stdout)
        for limited in (False,True):
            observed=evaluate(limited=limited)
            assert observed['historical']==sorted(pins) and set(pins)<=set(observed['active'])
            assert observed['valid'] and observed['preserved']
            for key in pins:
                config=json.loads(observed['config'][key])
                assert 'delivery_contract' not in config
                assert config['bundle']['sha256']==pins[key]['package_sha256']
                assert config['bundle']['version_id']==i[key]['version_id'] and config['runtime_image']==r[key]['uri']
        assert evaluate(nat=False)['historical']==sorted(pins), 'separately authorized NAT activation must not drop preserved delivery'
        for installs in ({}, {k:v for k,v in i.items() if k!='cleanup-recovery/cleanup-dev'}):
            assert not evaluate(installs=installs)['preserved'], 'mismatch must fail the output precondition'
        for field in ('sha256','version_id','source_commit'):
            bad=copy.deepcopy(i)
            for key in pins: bad[key][field]='foreign'
            assert not evaluate(installs=bad)['preserved']
        for kwargs in ({'approval':None},{'approval':'invalid'},{'delivery':False},{'contract':'SQL_RESTORE_NO_MIGRATIONS_V2'}):
            observed=evaluate(**kwargs)
            assert not observed['historical']
            if kwargs.get('approval') is not None or 'approval' not in kwargs:assert not observed['valid']
        # V2 remains an independent current-package contract, including its field.
        _,current_images,current_bindings=installed_projection(doc)
        current_i,_,_=installed_projection(doc)
        observed=evaluate(installs=current_i,images=current_images,binding=current_bindings['dev'],approval=None,
                          contract='SQL_RESTORE_NO_MIGRATIONS_V2')
        assert json.loads(observed['config']['normal-delivery/deploy-dev'])['delivery_contract']=='SQL_RESTORE_NO_MIGRATIONS_V2'
    print('Historical DEV: both modes, closed identities, dependencies, fail-closed precondition and separate V2 PASS')
