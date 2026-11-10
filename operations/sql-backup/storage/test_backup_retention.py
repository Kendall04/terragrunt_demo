import copy
import datetime as dt
import hashlib
import io
import json
import unittest
import backup_retention as r
from storage_verification import Unverified

NOW=dt.datetime(2026,11,6,7,tzinfo=dt.timezone.utc)
CFG={'bucket':r.BUCKET,'prefix':r.PREFIX.rstrip('/'),'database':'demodb','backupKeyArn':'key','textKeyArn':'text','maxBytes':100}
class Store:
    def __init__(self):
        self.objects={};self.tags={};self.writes=[];self.markers=[]
        for i in range(4):
            run=f'{i:032x}'; base=r.PREFIX+'runs/'+run+'/'; at=NOW-dt.timedelta(hours=i)
            body=b'backup'+bytes([i]);version='bak-'+run
            m={'SchemaVersion':1,'Id':run,'Database':'demodb','StartedUtc':at.isoformat(),'CompletedUtc':at.isoformat(),'SqlVersion':'16.0','RecoveryModel':'FULL','Length':len(body),'Sha256':hashlib.sha256(body).hexdigest(),'NativeChecksumVerified':True,'TextKeyArn':'text','BackupKey':base+'database.bak','BackupVersion':version}
            for key,ver,data in [(base+'database.bak',version,body),(base+'manifest.json','man-'+run,json.dumps(m).encode())]:
                self.objects[key]={'Key':key,'VersionId':ver,'IsLatest':True,'LastModified':at,'body':data};self.tags[key]=[]
    def list_object_versions(self,**kw): return {'Versions':[{k:v for k,v in x.items() if k!='body'} for x in self.objects.values()], 'DeleteMarkers':self.markers}
    def head_object(self,**kw):
        x=self.objects[kw['Key']]
        return {'ServerSideEncryption':'aws:kms','SSEKMSKeyId':'key','VersionId':x['VersionId'],'ContentLength':len(x['body'])}
    def get_object(self,**kw):
        x=self.objects[kw['Key']];assert x['VersionId']==kw['VersionId'];return {**self.head_object(**kw),'Body':io.BytesIO(x['body'])}
    def get_object_tagging(self,**kw):return {'TagSet':copy.deepcopy(self.tags[kw['Key']])}
    def put_object_tagging(self,**kw):self.writes.append(kw);self.tags[kw['Key']]=copy.deepcopy(kw['Tagging']['TagSet'])

class RetentionTests(unittest.TestCase):
    def test_only_verified_older_pairs_tagged_latest_two_retained(self):
        s=Store();p=r.plan(s,CFG,NOW)
        self.assertEqual(len(p['preserved']),2);self.assertEqual(len(p['candidates']),2)
        result=r.apply_plan(s,CFG,p);self.assertEqual(len(result['taggedVersions']),4)
        self.assertEqual(result['deletedObjects'],0)
        for run in [f'{i:032x}' for i in (0,1)]:
            self.assertTrue(all(not tags for key,tags in s.tags.items() if run in key))
        self.assertEqual(r.plan(s,CFG,NOW)['candidates'],[])
    def test_bad_newest_never_falls_back_or_enrolls(self):
        s=Store();s.objects[r.PREFIX+'runs/'+f'{0:032x}'+'/database.bak']['body']=b'bad'
        with self.assertRaises(Unverified):r.plan(s,CFG,NOW)
        self.assertEqual(s.writes,[])
    def test_protected_tag_or_changed_plan_refused(self):
        s=Store();key=next(iter(s.tags));s.tags[key]=[r.TAG]
        with self.assertRaisesRegex(Unverified,'LAST_BACKUP'):r.plan(s,CFG,NOW)
        s=Store();p=r.plan(s,CFG,NOW);p['candidates'][0]['runId']='0'*32
        with self.assertRaisesRegex(Unverified,'PLAN_CHANGED'):r.apply_plan(s,CFG,p)
        self.assertEqual(s.writes,[])
    def test_historical_rules_preserved_and_no_overlap(self):
        old=[{'ID':'historical','Status':'Enabled','Filter':{'Prefix':'old/'},'Expiration':{'Days':2}}]
        rules=r.lifecycle(old);self.assertEqual(rules[0],old[0]);self.assertEqual(len(rules),4)
        self.assertIn(r.TAG,rules[1]['Filter']['And']['Tags']);self.assertEqual(rules[1]['Expiration'],{'Days':7})
        self.assertEqual(rules[1]['NoncurrentVersionExpiration'],{'NoncurrentDays':1})
        self.assertFalse(r.HOLD_PREFIX.startswith(r.PREFIX))
        with self.assertRaisesRegex(Unverified,'OVERLAP'):r.lifecycle([{'Status':'Enabled','Filter':{'Prefix':'terragrunt-demo/'}}])
    def test_orphan_and_old_enrollment_quarantined(self):
        s=Store();old=r.PREFIX+'runs/'+f'{3:032x}'+'/manifest.json';s.objects[old]['LastModified']=NOW-dt.timedelta(days=7)
        p=r.plan(s,CFG,NOW);self.assertEqual(len(p['quarantined']),1)
        orphan=r.PREFIX+'runs/'+'f'*32+'/database.bak';s.objects[orphan]={**next(iter(s.objects.values())),'Key':orphan,'VersionId':'orphan'}
        self.assertIn(orphan,r.plan(s,CFG,NOW)['uncommittedObjects'])
    def test_lifecycle_markers_not_reintroduced_or_counted(self):
        s=Store();key=r.PREFIX+'runs/'+'f'*32+'/database.bak';s.objects[key]={**next(iter(s.objects.values())),'Key':key,'VersionId':'gone','IsLatest':False};s.markers=[{'Key':key,'IsLatest':True}]
        self.assertEqual(len(r.plan(s,CFG,NOW)['preserved']),2)

if __name__=='__main__':unittest.main()
