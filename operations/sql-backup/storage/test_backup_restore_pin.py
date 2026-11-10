import unittest
import backup_restore_pin as pin
import backup_retention as retention
from test_backup_retention import Store,CFG,NOW
from storage_verification import Unverified

class PinStore(Store):
    def list_object_versions(self,**args):
        return {'Versions':[x for x in super().list_object_versions(**args)['Versions'] if x['Key'].startswith(args['Prefix'])]}
    def put_object(self,**args):
        assert args['IfNoneMatch']=='*' and args['ServerSideEncryption']=='aws:kms' and args['SSEKMSKeyId']=='key'
        assert args['Key'] not in self.objects
        version='real-fake-version-'+str(len(self.writes));self.writes.append(args)
        self.objects[args['Key']]={'Key':args['Key'],'VersionId':version,'IsLatest':True,'LastModified':NOW,'body':args['Body']}
        self.tags[args['Key']]=[]
        return {'VersionId':version}

class PinTests(unittest.TestCase):
    def test_verified_independent_pair_before_any_sql_mutation(self):
        s=PinStore();source=retention.PREFIX+'runs/'+f'{0:032x}'+'/manifest.json'
        r=pin.pin(s,CFG,source,'restore-test-20261106',NOW)
        self.assertEqual(r['source']['sha256'],r['pinned']['sha256'])
        self.assertNotEqual(r['source']['backupVersion'],r['pinned']['backupVersion'])
        self.assertTrue(r['pinned']['manifestKey'].startswith(retention.HOLD_PREFIX))
        self.assertFalse(r['pinned']['manifestKey'].startswith(retention.PREFIX))
        self.assertEqual(r['sqlMutations'],0);self.assertEqual(len(s.writes),4)
        with self.assertRaisesRegex(Unverified,'PIN_ALREADY_EXISTS'):pin.pin(s,CFG,source,'restore-test-20261106',NOW)
        self.assertEqual(len(s.writes),4)
    def test_corrupt_source_cannot_be_pinned(self):
        s=PinStore();source=retention.PREFIX+'runs/'+f'{0:032x}'+'/manifest.json'
        s.objects[source.replace('manifest.json','database.bak')]['body']=b'corrupt'
        with self.assertRaises(Unverified):pin.pin(s,CFG,source,'restore-test-20261106',NOW)
        self.assertEqual(s.writes,[])
    def test_ambiguous_write_not_retried(self):
        s=PinStore();source=retention.PREFIX+'runs/'+f'{0:032x}'+'/manifest.json'
        original=s.put_object
        def ambiguous(**args):original(**args);raise TimeoutError('unknown')
        s.put_object=ambiguous
        with self.assertRaises(TimeoutError):pin.pin(s,CFG,source,'restore-test-20261106',NOW)
        self.assertEqual(len(s.writes),1)
if __name__=='__main__':unittest.main()
