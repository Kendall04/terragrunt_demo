"""Offline subprocess mocks only: no Terraform, AWS, sockets or real state."""
import subprocess
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from scripts import practical_dev as p
from scripts import original_dev as entry

CONFIG={'profile':'offline-fixture','region':'us-east-1'}

class DiagnosticDiscard(unittest.TestCase):
    def test_native_child_stderr_is_never_captured_in_review_mode(self):
        result=SimpleNamespace(returncode=0,stdout=b'PUBLIC_SYNTHETIC_METADATA')
        with patch.object(p.subprocess,'run',return_value=result) as run:
            self.assertEqual(result.stdout,p.Process(CONFIG,discard_diagnostics=True).run(['offline-synthetic-fixture']))
        self.assertIs(run.call_args.kwargs['stderr'],subprocess.DEVNULL)
        self.assertIs(run.call_args.kwargs['stdout'],subprocess.PIPE)
        self.assertNotIn('capture_output',run.call_args.kwargs)
    def test_failure_discards_even_unexpected_mock_diagnostic(self):
        result=SimpleNamespace(returncode=1,stdout=b'',stderr=b'SECRET-SENTINEL')
        with patch.object(p.subprocess,'run',return_value=result):
            with self.assertRaises(p.Failure) as raised:p.Process(CONFIG,discard_diagnostics=True).run(['offline-synthetic-fixture'])
        self.assertEqual(b'',raised.exception.stderr);self.assertNotIn('SECRET',str(raised.exception))
    def test_old_default_contract_is_preserved(self):
        result=SimpleNamespace(returncode=1,stdout=b'',stderr=b'SYNTHETIC_DEFAULT_DIAGNOSTIC')
        with patch.object(p.subprocess,'run',return_value=result) as run:
            with self.assertRaises(p.Failure) as raised:p.Process(CONFIG).run(['offline-synthetic-fixture'])
        self.assertEqual(result.stderr,raised.exception.stderr);self.assertIs(run.call_args.kwargs['stderr'],subprocess.PIPE)
    def test_sanitized_output_omits_values_and_confirmations(self):
        value={'plan_id':'synthetic','layer':'global','phase':'REVIEW_REQUIRED_NOT_EXECUTED','preview':'SECRET-SENTINEL',
               'state':{'password':'SECRET-SENTINEL'},'confirmation':'DO_NOT_EXPOSE','change_summary':[{'address':'aws_vpc.this','type':'aws_vpc','actions':['create']}]}
        summary=p.sanitized_plan_result(value)
        self.assertEqual({'plan_id','layer','phase','change_summary'},set(summary));self.assertNotIn('SECRET',str(summary));self.assertNotIn('DO_NOT_EXPOSE',str(summary))
    def test_review_mode_refuses_other_transport(self):
        with self.assertRaisesRegex(ValueError,'native route'):
            p.Process(CONFIG,terraform_wsl_bin='synthetic',discard_diagnostics=True)
    def test_mode_cannot_be_used_for_apply_or_teardown(self):
        with tempfile.TemporaryDirectory() as directory:
            config=Path(directory)/'fixture.json';config.write_text('{}')
            for action in ('apply','inhibit','down-plan'):
                with patch.object(p,'Session',side_effect=AssertionError('session escape')):
                    with self.assertRaisesRegex(ValueError,'never apply or teardown'):
                        p.main([action,'--config',str(config),'--directory',str(Path(directory)/'unused'),'--discard-diagnostics'])

class FixedStepMetadata(unittest.TestCase):
    def test_known_stage_has_only_label_and_integer(self):
        error=p.Failure(23,b'SECRET-SENTINEL','global:terraform state')
        self.assertEqual({'Status':'FAILED','Step':'GLOBAL_TERRAFORM_STATE','ExitCode':23},entry.safe_e16_failure(error))
    def test_unknown_stage_and_non_integer_cannot_escape(self):
        error=SimpleNamespace(stage='SECRET-SENTINEL',code='SECRET-SENTINEL')
        self.assertEqual({'Status':'FAILED','Step':'E16_PRECONDITION','ExitCode':1},entry.safe_e16_failure(error))
    def test_metadata_does_not_read_exception_text_or_stderr(self):
        class Unreadable:
            stage='AWS synthetic metadata';code=2
            def __str__(self):raise AssertionError('text read')
            @property
            def stderr(self):raise AssertionError('stderr read')
        self.assertEqual({'Status':'FAILED','Step':'AWS_METADATA','ExitCode':2},entry.safe_e16_failure(Unreadable()))

if __name__=='__main__':unittest.main(verbosity=2)
