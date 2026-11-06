import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock

import native_step as step


class NativeDispatchTests(unittest.TestCase):
    def test_zero_service_counts_do_not_prove_task_stopped(self):
        ecs = Mock()
        ecs.list_tasks.return_value = {'taskArns': ['task-one']}
        for status in ('RUNNING', 'DEACTIVATING', 'STOPPING', 'DEPROVISIONING'):
            ecs.describe_tasks.return_value = {'tasks': [{'taskArn': 'task-one', 'lastStatus': status}]}
            with self.subTest(status=status), self.assertRaisesRegex(ValueError, 'ECS_TASKS_STILL_DRAINING'):
                step.verify_drained_tasks(ecs)
        ecs.describe_tasks.return_value = {'tasks': [{'taskArn': 'task-one', 'lastStatus': 'STOPPED'}]}
        step.verify_drained_tasks(ecs)
        self.assertEqual({call.kwargs['desiredStatus'] for call in ecs.list_tasks.call_args_list},
                         {'RUNNING', 'STOPPED'})

    def test_missing_task_readback_is_not_quiescence(self):
        ecs = Mock()
        ecs.list_tasks.return_value = {'taskArns': ['task-one']}
        ecs.describe_tasks.return_value = {'tasks': [], 'failures': [{'arn': 'task-one'}]}
        with self.assertRaisesRegex(ValueError, 'ECS_TASKS_STILL_DRAINING'):
            step.verify_drained_tasks(ecs)

    def test_isolated_cli_help_needs_no_credentials_or_sdk(self):
        result = subprocess.run([sys.executable, '-I', '-B', str(Path(step.__file__)), '--help'],
                                capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('--dispatch', result.stdout)

    def host(self):
        return {'State': {'Name': 'running'}, 'ImageId': 'ami-062944a84867f2386',
            'InstanceType': 't3a.small', 'Placement': {'AvailabilityZone': 'us-east-1b'},
            'SubnetId': step.SUBNETS['us-east-1b'], 'VpcId': 'vpc-00faf317507b09b03',
            'IamInstanceProfile': {'Arn': step.PROFILE}, 'MetadataOptions': {'HttpTokens': 'required'},
            'SecurityGroups': [{'GroupId': 'sg-09d69b4eda335675d'}],
            'Tags': [{'Key': 'Project', 'Value': 'demo'}, {'Key': 'Environment', 'Value': 'dev'}]}

    def test_target_must_be_exact_private_sql_host(self):
        step.verify_host(self.host(), {'targetAz': 'us-east-1b'})
        for key, value in [('PublicIpAddress', '203.0.113.1'), ('ImageId', 'other'),
                           ('MetadataOptions', {'HttpTokens': 'optional'}),
                           ('SubnetId', step.SUBNETS['us-east-1a']), ('Tags', [])]:
            host = self.host()
            host[key] = value
            with self.subTest(field=key), self.assertRaises(ValueError):
                step.verify_host(host, {'targetAz': 'us-east-1b'})

    def test_retention_requires_actual_root_mapping(self):
        ec2 = Mock()
        source = {'RootDeviceName': '/dev/sda1', 'BlockDeviceMappings': [
            {'DeviceName': '/dev/sda1', 'Ebs': {'VolumeId': 'vol-original', 'DeleteOnTermination': True}}]}
        with self.assertRaisesRegex(ValueError, 'SOURCE_DISK_NOT_RETAINED'):
            step.source_disk(ec2, source, 'vol-original', False)
        ec2.describe_volumes.assert_not_called()

    def test_detached_encrypted_retained_disk_is_required(self):
        ec2 = Mock()
        ec2.describe_volumes.return_value = {'Volumes': [{'VolumeId': 'vol-original',
            'Encrypted': True, 'KmsKeyId': 'arn:aws:kms:us-east-1:341936017254:key/585f0833-6a1c-465d-ab40-a6c8278cae39',
            'State': 'available', 'Attachments': []}]}
        step.source_disk(ec2, {}, 'vol-original', True)
        ec2.describe_volumes.return_value['Volumes'][0]['Attachments'] = [{'InstanceId': 'i-other'}]
        with self.assertRaisesRegex(ValueError, 'SOURCE_DISK_STILL_ATTACHED'):
            step.source_disk(ec2, {}, 'vol-original', True)

    def test_local_fence_claim_is_insufficient_without_successful_ssm_readback(self):
        with tempfile.TemporaryDirectory() as name:
            directory = Path(name)
            request = {'trial': 'v2-test', 'instanceId': 'i-target', 'sourceInstanceId': 'i-source',
                'sourceLaunchTime': '2026-11-04T20:00:00Z', 'expectedRows': 2,
                'expectedDataHash': 'a' * 64, 'backupReceipt': {'ManifestVersion': 'authentic'}}
            before = dict(request, instanceId='i-source')
            (directory/'v2-test-fence.dispatch-intent.json').write_text(json.dumps(
                {'sourceVolumeId': 'vol-original', 'request': before}))
            (directory/'v2-test-fence.dispatch-result.json').write_text(json.dumps({'Command': {'CommandId': 'one'}}))
            ssm = Mock()
            ssm.get_command_invocation.return_value = {'Status': 'InProgress', 'ResponseCode': -1}
            with self.assertRaisesRegex(ValueError, 'SQL_FENCE_NOT_CONFIRMED'):
                step.verify_prior_fence(ssm, directory, request, 'vol-original')
            ssm.get_command_invocation.return_value = {'Status': 'Success', 'ResponseCode': 0,
                'StandardOutputContent': json.dumps({'sourceFence': {'accessMode': 'READ_ONLY',
                'runtimeDisabled': True, 'otherSessions': 0}, 'backupReceipt': request['backupReceipt']})}
            step.verify_prior_fence(ssm, directory, request, 'vol-original')
            with self.assertRaisesRegex(ValueError, 'FENCE_RECEIPT_IDENTITY'):
                step.verify_prior_fence(ssm, directory, request, 'vol-another')


if __name__ == '__main__':
    unittest.main()
