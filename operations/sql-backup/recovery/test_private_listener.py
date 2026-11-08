"""Offline exact private endpoint/network fixtures, never native SQL or AWS proof."""
import io
import sys
from contextlib import redirect_stdout
import json
import unittest
from unittest.mock import Mock, patch

import host
import prepare
import verify_effective as verify
from test_kernel_query_binding import CapturedPidPort
from test_runtime_precheck import query
from test_service_plan import fixture

IP = '10.77.1.8'


def private_kernel():
    p = CapturedPidPort()
    p.texts['/var/opt/mssql/mssql.conf'] = p.texts['/var/opt/mssql/mssql.conf'].replace('127.0.0.1', IP)
    p.answers['network.ipaddress'] = 'ipaddress : ' + IP
    p.texts['/proc/net/tcp'] = p.texts['/proc/net/tcp'].replace('0100007F', '08014D0A')
    return p


def service_input():
    value = fixture()
    value['ColdReceipt']['ColdFence']['SourceLaunchUtc'] = '2026-10-24T18:00:00Z'
    return value


def native_fixture(value):
    from prepare import PROFILE
    net = value['Network']
    source, target = value['ColdReceipt']['Source'], value['ColdReceipt']['Target']
    fence = value['ColdReceipt']['ColdFence']
    subnet = 'subnet-' + 'd' * 17
    pair = {'GroupId':net['TaskSgId'], 'UserId':prepare.ACCOUNT}
    old = {'InstanceId':source['instanceId'],'State':{'Name':'terminated'},
           'LaunchTime':fence['SourceLaunchUtc'],'Placement':{'AvailabilityZone':source['availabilityZone']}}
    node = {'InstanceId':target['instanceId'],'State':{'Name':'running'},
            'LaunchTime':fence['TargetLaunchUtc'],'Placement':{'AvailabilityZone':target['availabilityZone']},
            'VpcId':net['DbVpcId'],'SubnetId':subnet,'PrivateIpAddress':IP,
            'IamInstanceProfile':{'Arn':PROFILE},'Tags':[{'Key':'Trial','Value':value['Trial']}],
            'SecurityGroups':[{'GroupId':net['DbSgId']}],
            'NetworkInterfaces':[{'VpcId':net['DbVpcId'],'SubnetId':subnet,
                'PrivateIpAddress':IP,'Groups':[{'GroupId':net['DbSgId']}],
                'PrivateIpAddresses':[{'PrivateIpAddress':IP}]}]}
    return {
        'sts':{'Account':prepare.ACCOUNT,'Arn':f'arn:aws:sts::{prepare.ACCOUNT}:assumed-role/{prepare.ROLE_NAME}/'+target['instanceId']},
        'describe-instances':{'Reservations':[{'OwnerId':prepare.ACCOUNT,'Instances':[old,node]}]},
        'describe-subnets':{'Subnets':[{'SubnetId':subnet,'OwnerId':prepare.ACCOUNT,'VpcId':net['DbVpcId'],
            'CidrBlock':net['DbSubnetCidr'],'MapPublicIpOnLaunch':False}]},
        'describe-security-groups':{'SecurityGroups':[
            {'OwnerId':prepare.ACCOUNT,'VpcId':net['DbVpcId'],'GroupId':net['DbSgId'],
             'IpPermissions':[{'IpProtocol':'tcp','FromPort':1433,'ToPort':1433,'UserIdGroupPairs':[pair]}]},
            {'OwnerId':prepare.ACCOUNT,'VpcId':net['AppVpcId'],'GroupId':net['TaskSgId'],'IpPermissions':[]}]}}


class PrivateListenerTests(unittest.TestCase):
    def test_private_query_is_bound_to_same_kernel_owner_and_default_stays_loopback(self):
        p = private_kernel()
        result = verify.assess_runtime(p, lambda:query('380|' + IP + '|1433'), IP)
        verify.require_runtime_precheck(result, IP)
        self.assertFalse(result['Ipv4Loopback1433Only'])
        self.assertEqual(result['ExpectedSqlEndpoint'], IP)
        self.assertEqual(result['ProcessBinding']['KernelSqlPid'], 18)
        self.assertEqual(p.environment_pids, [18])
        self.assertFalse(result['RecoveryAcceptance'])
        with self.assertRaises(verify.Problem):
            verify.require_runtime_precheck(result)
        default = verify.assess_runtime(private_kernel(), lambda:query('380|' + IP + '|1433'))
        self.assertEqual(default['Code'], 'IP_NOT_LOOPBACK')
        old = verify.assess_runtime(CapturedPidPort(), lambda:query('380|127.0.0.1|1433'))
        verify.require_runtime_precheck(old)

    def test_wrong_wildcard_ipv6_extra_listener_and_fresh_query_endpoint_refuse(self):
        for address in ('00000000', '0100007F', '09014D0A'):
            p = private_kernel();p.texts['/proc/net/tcp'] = p.texts['/proc/net/tcp'].replace('08014D0A', address)
            call = Mock(return_value=query('380|' + IP + '|1433'))
            result = verify.assess_runtime(p, call, IP)
            self.assertEqual(result['Status'], 'REFUSED');call.assert_not_called()
        p = private_kernel();p.texts['/proc/net/tcp6'] = p.texts['/proc/net/tcp']
        self.assertEqual(verify.assess_runtime(p, lambda:query('380|' + IP + '|1433'), IP)['Status'], 'REFUSED')
        result = verify.assess_runtime(private_kernel(), lambda:query('380|127.0.0.1|1433'), IP)
        self.assertEqual(result['Code'], 'FRESH_QUERY_BINDING_INVALID')
        for bad in ('0.0.0.0','8.8.8.8','169.254.169.254','::1','10.77.1.8;bad'):
            call = Mock()
            self.assertEqual(verify.assess_runtime(private_kernel(), call, bad)['Code'], 'INVALID_LISTENER_ENDPOINT')
            call.assert_not_called()

    def test_private_restart_or_socket_replacement_during_query_refuses(self):
        for change in ('pid','socket','exe'):
            p = private_kernel()
            def action():
                if change == 'pid':p.texts['/proc/18/stat'] = p.texts['/proc/18/stat'].rsplit(' ',1)[0] + ' 9000'
                elif change == 'socket':
                    p.texts['/proc/net/tcp'] = p.texts['/proc/net/tcp'].replace('700','701')
                    p.links['/proc/18/fd/8'] = 'socket:[701]'
                else:p.links['/proc/18/exe'] = '/tmp/foreign'
                return query('380|' + IP + '|1433')
            result = verify.assess_runtime(p, action, IP)
            self.assertEqual(result['Status'], 'REFUSED')
            self.assertEqual(result['Stage'], 'runtime_binding_after')

    def native(self, value=None, changes=None):
        value = value or service_input()
        docs = native_fixture(value)
        if changes:changes(docs)
        port = host.Port()
        def run(args, **kwargs):
            self.assertEqual(args[0], 'aws')
            self.assertIn(args[1], ('sts','ec2'))
            self.assertIn(args[2], ('get-caller-identity','describe-instances','describe-subnets','describe-security-groups'))
            return json.dumps(docs['sts' if args[1] == 'sts' else args[2]])
        port.run = Mock(side_effect=run)
        return value, port

    def test_actual_read_adapter_checks_exact_network_fence_and_has_no_mutations(self):
        value, port = self.native()
        result = port.application_network(value, value['ColdReceipt']['Target'])
        self.assertEqual(result['PrivateIp'], IP)
        self.assertTrue(result['SingleTaskSgSql1433IngressOnly'])
        self.assertEqual(len(port.run.call_args_list), 4)
        self.assertEqual(port.run.call_args_list[1].args[0][6:8],
                         [value['ColdReceipt']['Source']['instanceId'], value['ColdReceipt']['Target']['instanceId']])

    def test_native_role_source_generation_public_address_extra_sg_subnet_and_ingress_fail(self):
        def node(d):return d['describe-instances']['Reservations'][0]['Instances'][1]
        for change in (
            lambda d:d['sts'].update(Arn='arn:foreign'),
            lambda d:d['describe-instances']['Reservations'][0]['Instances'][0]['State'].update(Name='stopped'),
            lambda d:d['describe-instances']['Reservations'][0]['Instances'][0].update(LaunchTime='2026-10-24T17:00:00Z'),
            lambda d:node(d).update(PublicIpAddress='203.0.113.10'),
            lambda d:node(d)['SecurityGroups'].append({'GroupId':'sg-'+'e'*17}),
            lambda d:d['describe-subnets']['Subnets'][0].update(CidrBlock='10.0.0.0/24'),
            lambda d:d['describe-security-groups']['SecurityGroups'][0]['IpPermissions'][0].update(IpRanges=[{'CidrIp':'0.0.0.0/0'}]),
            lambda d:d['describe-security-groups']['SecurityGroups'][0]['IpPermissions'][0]['UserIdGroupPairs'][0].update(GroupId='sg-'+'e'*17)):
            value, port = self.native(changes=change)
            with self.assertRaises(ValueError):port.application_network(value,value['ColdReceipt']['Target'])

    def test_pretransition_network_observation_needs_no_secret_query_or_host_changes(self):
        value,port=self.native();port.secret=Mock();port.runtime_precheck=Mock()
        result=host.check_application_network(port,value,value['ColdReceipt']['Target'])
        self.assertEqual(result['Status'],'APPLICATION_NETWORK_OBSERVATION_ONLY')
        self.assertFalse(result['AllowsHostChanges']);self.assertFalse(result['AllowsActivation'])
        port.secret.assert_not_called();port.runtime_precheck.assert_not_called()

    def test_read_denial_is_not_retried_or_followed_by_secret_or_sql(self):
        value, port = self.native()
        port.run = Mock(side_effect=ValueError('CHILD_FAILED_REVIEW_BEFORE_RETRY'))
        port.secret = Mock();port.runtime_precheck = Mock()
        with self.assertRaises(ValueError):host.check_application_listener(port,value,value['ColdReceipt']['Target'])
        self.assertEqual(port.run.call_count,1)
        port.secret.assert_not_called();port.runtime_precheck.assert_not_called()

    def test_whole_readonly_path_rechecks_network_and_private_sql_command_uses_exact_ip(self):
        value, port = self.native()
        kernel = private_kernel()
        port.secret = Mock(return_value='SYNTHETIC_NOT_EXPORTED')
        with patch.object(verify,'LocalPort',return_value=kernel),patch.object(host.subprocess,'run',return_value=query('380|' + IP + '|1433')) as child:
            result = host.check_application_listener(port,value,value['ColdReceipt']['Target'])
        self.assertEqual(child.call_args.args[0][2], 'tcp:' + IP + ',1433')
        self.assertEqual(port.run.call_count,8)
        self.assertEqual(result['Status'],'APPLICATION_LISTENER_OBSERVATION_ONLY')
        self.assertFalse(result['AllowsActivation']);self.assertFalse(result['FullEcsRecoveryProven'])
        self.assertNotIn('SYNTHETIC_NOT_EXPORTED',json.dumps(result))
        first = result['NetworkBinding']
        port.application_network = Mock(side_effect=[first,dict(first,SubnetId='subnet-foreign')])
        port.runtime_precheck = Mock(return_value=result['RuntimePrecheck'])
        with self.assertRaisesRegex(ValueError,'LISTENER_NETWORK_CHANGED'):
            host.check_application_listener(port,value,value['ColdReceipt']['Target'])

    def test_listener_cli_defaults_are_inert_even_with_missing_plan(self):
        for action in ('listener-network-check','listener-check'):
            with patch.object(sys,'argv',['host.py',action,'--trial','r20261024c1t','--directory','/never','--listener-plan','/missing']),patch.object(host,'Port',side_effect=AssertionError('NATIVE_PORT_FORBIDDEN')),redirect_stdout(io.StringIO()) as out:
                host.main()
            result=json.loads(out.getvalue())
            self.assertEqual(result['Status'],'HOST_PLAN_ONLY')
            self.assertFalse(result['ReadsSecrets'])

    def test_plan_never_executes_host_steps_and_uncertain_fence_refuses(self):
        value = service_input()
        plan = prepare.application_listener_plan(value)
        self.assertEqual(plan['ReviewedHostSteps'][1],['/opt/mssql/bin/mssql-conf','set','network.ipaddress',IP])
        self.assertFalse(plan['AllowsHostChanges']);self.assertFalse(plan['AllowsActivation'])
        value['ColdReceipt']['ColdFence']['Status'] = 'SOURCE_STOPPED'
        with self.assertRaises(ValueError):prepare.application_listener_plan(value)


if __name__ == '__main__':
    unittest.main()
