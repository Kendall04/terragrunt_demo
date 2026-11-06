import datetime as dt
import io
import json
import unittest
import nat_observer as n
from storage_observer import Unverified

NOW=dt.datetime(2026,11,6,8,tzinfo=dt.timezone.utc)
C={'expiresAt':'2026-11-09T04:00:00Z','asg':'demo-dev-asg-nat-a','publicSubnet':'sub-a','vpc':'vpc-dev','lt':'lt-a','routeTable':'rt-a','allocationId':'eip-a','expectedEip':'192.0.2.1','probeArn':'own-probe'}
class Aws:
    def __init__(self):self.terminated=False;self.healthy=True;self.sdc=False;self.route='eni-a';self.egress='192.0.2.1';self.probe_error=False;self.https_failed=False;self.read_error=False;self.calls=[]
    def describe_auto_scaling_groups(self,**kw):
        self.calls.append(kw)
        if self.read_error:raise RuntimeError('AWS_READ_UNAVAILABLE')
        return {'AutoScalingGroups':[{'AutoScalingGroupName':C['asg'],'DesiredCapacity':1,'Instances':[{'InstanceId':'i-a','LifecycleState':'InService' if self.healthy else 'Pending','HealthStatus':'Healthy','LaunchTemplate':{'LaunchTemplateId':'lt-a','Version':'4'}}]}]}
    def describe_instances(self,**kw):
        if self.terminated:return {'Reservations':[{'Instances':[{'InstanceId':'i-a','State':{'Name':'terminated'}}]}]}
        return {'Reservations':[{'Instances':[{'InstanceId':'i-a','State':{'Name':'running'},'SubnetId':'sub-a','VpcId':'vpc-dev','SourceDestCheck':self.sdc,'NetworkInterfaces':[{'NetworkInterfaceId':'eni-a'}]}]}]}
    def describe_route_tables(self,**kw):return {'RouteTables':[{'VpcId':'vpc-dev','Routes':[{'DestinationCidrBlock':'0.0.0.0/0','State':'active','NetworkInterfaceId':self.route}]}]}
    def describe_addresses(self,**kw):return {'Addresses':[{'PublicIp':C['expectedEip'],'NetworkInterfaceId':'eni-a','AllocationId':'eip-a'}]}
    def invoke(self,**kw):
        self.calls.append(kw);event=json.loads(kw['Payload'])
        self.body=io.BytesIO(json.dumps({'status':'HTTPS_FAILED' if self.https_failed else 'HTTPS_SUCCESS','egressIp':self.egress,'at':NOW.isoformat(),'observationId':event['observationId'],'httpsRequests':1}).encode())
        return {'FunctionError':'failed','Payload':self.body} if self.probe_error else {'Payload':self.body}

class NatTests(unittest.TestCase):
    def test_control_plane_requires_real_egress_with_exact_eip(self):
        s=Aws();self.assertEqual(n.observe(lambda _:s,C,NOW,'one')['verdict'],'Pass')
        s.egress='192.0.2.2';self.assertIn('PRIVATE_HTTPS_EGRESS_FAILED',n.observe(lambda _:s,C,NOW,'two')['failures'])
    def test_real_state_failures_are_not_hidden_by_healthy_asg(self):
        for field,value,code in [('sdc',True,'NAT_CONFIGURATION_NOT_RECOVERED'),('route','eni-old','PRIVATE_ROUTE_NOT_RECOVERED'),('healthy',False,'ONE_HEALTHY_NAT_NOT_PRESENT')]:
            s=Aws();setattr(s,field,value);self.assertIn(code,n.observe(lambda _:s,C,NOW,'test')['failures'])
    def test_terminated_member_without_network_fields_still_runs_private_probe(self):
        s=Aws();s.terminated=True;s.egress='192.0.2.2'
        r=n.observe(lambda _:s,C,NOW,'terminated')
        self.assertEqual(r['verdict'],'Fail')
        self.assertIn('NAT_CONFIGURATION_NOT_RECOVERED',r['failures'])
        self.assertIn('PRIVATE_HTTPS_EGRESS_FAILED',r['failures'])
        self.assertEqual(r['evidence']['state'],'terminated')
        self.assertTrue(any('Payload' in c for c in s.calls))
    def test_unavailable_executor_is_unknown_not_infrastructure_failure(self):
        s=Aws();s.probe_error=True;s.terminated=True
        result=n.observe(lambda _:s,C,NOW,'one')
        self.assertEqual(result['verdict'],'Unknown')
        self.assertEqual(result['checks']['connectivity']['verdict'],'Unknown')
        self.assertEqual(result['checks']['controlPlane']['verdict'],'Fail')
        self.assertEqual(result['evidence']['state'],'terminated')
        self.assertTrue(s.body.closed)
        self.assertNotIn('PRIVATE_HTTPS_EGRESS_FAILED',result['failures'])
    def test_control_read_failure_does_not_discard_real_https_result(self):
        s=Aws();s.read_error=True
        self.assertEqual(n.observe(lambda _:s,C,NOW,'one')['verdict'],'Unknown')
        s.https_failed=True
        result=n.observe(lambda _:s,C,NOW,'two')
        self.assertEqual(result['verdict'],'Fail')
        self.assertEqual(result['checks']['controlPlane']['verdict'],'Unknown')
        self.assertEqual(result['checks']['connectivity']['verdict'],'Fail')
    def test_replacement_is_distinct_from_proven_https_loss(self):
        s=Aws();s.healthy=False
        result=n.observe(lambda _:s,C,NOW,'one')
        self.assertEqual(result['checks']['controlPlane']['verdict'],'Fail')
        self.assertEqual(result['checks']['connectivity']['verdict'],'Pass')
        self.assertNotIn('PRIVATE_HTTPS_EGRESS_FAILED',result['failures'])
    def test_expired_window_has_no_aws_calls(self):
        s=Aws()
        with self.assertRaisesRegex(Unverified,'WINDOW_EXPIRED'):n.observe(lambda _:s,C,NOW+dt.timedelta(days=4),'one')
        self.assertEqual(s.calls,[])
if __name__=='__main__':unittest.main()
