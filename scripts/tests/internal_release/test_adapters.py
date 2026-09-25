"""SDK response fixtures exercise production ports, with sockets denied by runner."""
import base64
import copy
import io
import hashlib
import json
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import patch

import e1_contract as c
import adapters as a
import exchange
import publisher
import services
import workers
import runtime

OP = '11111111-1111-1111-1111-111111111111'
UUID = '22222222-2222-2222-2222-222222222222'
ACCOUNT = '111122223333'
REGION = 'us-east-1'
REGISTRY = ACCOUNT+'.dkr.ecr.'+REGION+'.amazonaws.com'


class ClientError(Exception):
    def __init__(self, code):
        self.response = {'Error': {'Code': code}}


class S3:
    def __init__(self):
        self.objects = {}; self.calls = []; self.urls = {}
    def put_object(self, **kw):
        self.calls.append(('put', kw.copy()))
        key = kw['Bucket'], kw['Key']
        if key in self.objects and kw.get('IfNoneMatch') == '*':
            raise ClientError('PreconditionFailed')
        version = 'sdk-returned-'+str(len(self.calls))
        self.objects[key] = version, kw['Body']
        return {'VersionId': version}
    def get_object(self, **kw):
        self.calls.append(('get',kw.copy()))
        if (kw['Bucket'],kw['Key']) not in self.objects:
            raise ClientError('NoSuchKey')
        version, raw = self.objects[kw['Bucket'],kw['Key']]
        if 'VersionId' in kw and kw['VersionId'] != version:
            raise ClientError('NoSuchVersion')
        return {'VersionId':version,'Body':io.BytesIO(raw)}
    def list_objects_v2(self,**kw):
        self.calls.append(('list',kw.copy()))
        assert kw['MaxKeys']==1
        keys=sorted(key for bucket,key in self.objects if bucket==kw['Bucket'] and key.startswith(kw['Prefix']))
        return {'Contents':[{'Key':k} for k in keys[:1]]}
    def head_object(self, **kw):
        self.calls.append(('head',kw.copy()))
        version,raw = self.objects[kw['Bucket'],kw['Key']]
        return {'VersionId':version,'ContentLength':len(raw)}
    def generate_presigned_url(self, method, **kw):
        url = 'https://fixture.invalid/capability/'+str(len(self.urls))
        self.urls[url] = method,kw
        return url
    def use(self,url,method,params,raw=None,headers=None):
        verb,kw = self.urls[url]
        if method != kw['HttpMethod'] or params != {k:v for k,v in kw['Params'].items() if k!='IfNoneMatch'}:
            raise PermissionError('signature scope')
        if verb == 'get_object': return self.get_object(**params)
        if headers != {'If-None-Match':'*'}: raise PermissionError('signed condition')
        return self.put_object(**kw['Params'],Body=raw)


def archive(extra=None):
    blobs = {}
    def descriptor(raw, media):
        identity = c.digest(raw); blobs['blobs/sha256/'+identity] = raw
        return {'digest':'sha256:'+identity,'size':len(raw),'mediaType':media}
    config = descriptor(c.canonical({'os':'linux','architecture':'amd64'}),'application/vnd.oci.image.config.v1+json')
    layer = descriptor(b'fixture application layer','application/vnd.oci.image.layer.v1.tar')
    manifest = c.canonical({'schemaVersion':2,'config':config,'layers':[layer]})
    top = descriptor(manifest,'application/vnd.oci.image.manifest.v1+json')
    blobs.update({'index.json':c.canonical({'schemaVersion':2,'manifests':[top]}),
                  'oci-layout':c.canonical({'imageLayoutVersion':'1.0.0'})})
    if extra: blobs.update(extra)
    result=io.BytesIO()
    with tarfile.open(fileobj=result,mode='w') as tar:
        for name in ('blobs','blobs/sha256'):
            item=tarfile.TarInfo(name);item.type=tarfile.DIRTYPE;tar.addfile(item)
        for name,raw in blobs.items():
            item=tarfile.TarInfo(name);item.size=len(raw);tar.addfile(item,io.BytesIO(raw))
    return result.getvalue(), 'sha256:'+c.digest(manifest)


class ECR:
    def __init__(self): self.calls=[]
    def initiate_layer_upload(self,**kw):
        self.calls.append(('begin',kw));return {'uploadId':'fixture','partSize':5*1024*1024}
    def upload_layer_part(self,**kw):self.calls.append(('part',kw))
    def complete_layer_upload(self,**kw):
        self.calls.append(('complete',kw));return {'layerDigest':kw['layerDigests'][0]}
    def put_image(self,**kw):
        self.calls.append(('image',kw));return {'image':{'repositoryName':kw['repositoryName'],
            'imageId':{'imageDigest':'sha256:'+c.digest(kw['imageManifest'].encode())}}}


def observation(project, failed=None):
    phases=[{'phaseType':p,'phaseStatus':'FAILED' if p==failed else 'SUCCEEDED'} for p in c.ORDER[:-1]]
    return {'builds':[{'id':project+':'+UUID,'projectName':project,'buildComplete':True,
        'buildStatus':'FAILED' if failed else 'SUCCEEDED','phases':phases+[{'phaseType':'COMPLETED'}]}]}


class CodeBuild:
    def __init__(self,s3=None):self.calls=[];self.s3=s3;self.failed={}
    def start_build(self,**kw):
        self.calls.append(kw)
        if kw['projectName']==c.WORKERS['image'] and self.s3:
            for entry in kw['environmentVariablesOverride']:
                if entry['name']=='E1_OUTPUT_URL':
                    _,cap=self.s3.urls[entry['value']]
                    self.s3.put_object(**cap['Params'],Body=archive()[0])
        return {'build':{'id':kw['projectName']+':'+UUID,'projectName':kw['projectName']}}
    def batch_get_builds(self,ids):
        return observation(ids[0].split(':')[0],self.failed.get(ids[0].split(':')[0]))


class Adapters(unittest.TestCase):
    def test_phase_mapping_positive(self):
        for stage,phase in c.PHASES.items():
            kind='dotnet' if stage.startswith('dotnet') else 'image' if stage=='image_build' else 'probe'
            result=c.observe(observation(c.WORKERS[kind]),c.WORKERS[kind]+':'+UUID,c.WORKERS[kind],stage)
            self.assertEqual(result['state'],'COMPLETED')
            self.assertEqual(result['exit_code'],1 if stage=='probe_no_server' else 0)
            self.assertIn(phase.lower(),c.worker_buildspec(kind)['phases'])

    def test_phase_failure_cannot_be_stdout_pass(self):
        for stage,phase in c.PHASES.items():
            kind='dotnet' if stage.startswith('dotnet') else 'image' if stage=='image_build' else 'probe'
            for failure in ('FAILED','FAULT','TIMED_OUT','STOPPED'):
                response=observation(c.WORKERS[kind],phase)
                response['builds'][0]['stdout']='PASS'
                next(p for p in response['builds'][0]['phases'] if p['phaseType']==phase)['phaseStatus']=failure
                got=c.observe(response,c.WORKERS[kind]+':'+UUID,c.WORKERS[kind],stage)
                self.assertEqual(got['exit_code'],0 if stage=='probe_no_server' else 1)

    def test_missing_duplicate_wrong_identity(self):
        project=c.WORKERS['dotnet'];response=observation(project)
        response['builds'][0]['phases']=[p for p in response['builds'][0]['phases'] if p['phaseType']!='BUILD']
        self.assertEqual(c.observe(response,project+':'+UUID,project,'dotnet_build')['state'],'UNKNOWN')
        response=observation(project);response['builds'][0]['phases']*=2
        with self.assertRaises(c.Rejected):c.observe(response,project+':'+UUID,project,'dotnet_test')
        with self.assertRaises(c.Rejected):c.observe(observation('wrong'),project+':'+UUID,project,'dotnet_test')

    def test_closed_worker_request_and_exact_probe(self):
        w=workers.Workers(CodeBuild(),ACCOUNT,REGION,'demo-shared-demo-ms',OP)
        for extra in ('serviceRoleOverride','buildspecOverride','imageOverride','sourceLocationOverride','command'):
            with self.assertRaises(c.Rejected):w.request('dotnet',{'SOURCE_URL':'https://fixture.invalid',extra:'evil'})
        for image in (REGISTRY+'/demo-shared-demo-ms:latest',REGISTRY+'/other@sha256:'+'a'*64):
            with self.assertRaises(c.Rejected):w.request('probe',image=image)
        uri=REGISTRY+'/demo-shared-demo-ms@sha256:'+'a'*64
        request=w.request('probe',image=uri)
        self.assertEqual(set(request),{'projectName','idempotencyToken','imageOverride','imagePullCredentialsTypeOverride'})
        self.assertEqual(request['imageOverride'],uri)
        self.assertEqual(request['imagePullCredentialsTypeOverride'],'CODEBUILD')

    def test_capabilities_and_conditional_output(self):
        s3=S3();e=exchange.Exchange(s3,'quarantine',OP)
        source=e.source((('demo-api','directory',493,b''),),'image')
        verb,cap=s3.urls[source]
        self.assertEqual(verb,'get_object');self.assertIn('VersionId',cap['Params'])
        output=e.output();verb,cap=s3.urls[output]
        self.assertEqual(cap['Params'].get('IfNoneMatch'),'*')
        params={k:v for k,v in cap['Params'].items() if k!='IfNoneMatch'}
        for wrong in (dict(params,Key='another-attempt'),dict(params,Bucket='protected')):
            with self.assertRaises(PermissionError):s3.use(output,'PUT',wrong,b'evil',{'If-None-Match':'*'})
        with self.assertRaises(PermissionError):s3.use(output,'PUT',params,b'evil',{})
        s3.use(output,'PUT',params,b'first',{'If-None-Match':'*'})
        with self.assertRaises(ClientError):s3.use(output,'PUT',params,b'second',{'If-None-Match':'*'})
        selected=e.selected_output()
        self.assertEqual(selected['bytes'],b'first');self.assertEqual(selected['sha256'],c.digest(b'first'))
        self.assertTrue(selected['version_id'].startswith('sdk-returned-'))
        self.assertEqual(s3.calls[-1][1].get('VersionId'),selected['version_id'])

    def test_publisher_oci_and_digest(self):
        raw,expected=archive();ecr=ECR()
        self.assertEqual(publisher.publish(ecr,'demo-shared-demo-ms',raw),expected)
        self.assertEqual(ecr.calls[-1][0],'image')
        self.assertNotIn('imageTag',ecr.calls[-1][1])
        for extra in ({'../escape':b'evil'},{'unreferenced':b'evil'},{'blobs/sha256/'+'0'*64:b'evil'}):
            with self.assertRaises(c.Rejected):publisher.oci(archive(extra)[0])

    def test_publisher_rejects_false_digest_and_confirms_exact_retry(self):
        raw,expected=archive()
        class FalseDigest(ECR):
            def put_image(self,**kw):
                result=super().put_image(**kw);result['image']['imageId']['imageDigest']='sha256:'+'f'*64;return result
        with self.assertRaises(c.Rejected):publisher.publish(FalseDigest(),'demo-shared-demo-ms',raw)
        class Existing(ECR):
            def complete_layer_upload(self,**kw):raise ClientError('LayerAlreadyExistsException')
            def put_image(self,**kw):self.manifest=kw['imageManifest'];raise ClientError('ImageAlreadyExistsException')
            def batch_get_image(self,**kw):
                assert kw['imageIds']==[{'imageDigest':expected}]
                return {'images':[{'repositoryName':kw['repositoryName'],'imageId':{'imageDigest':expected},'imageManifest':self.manifest}]}
        self.assertEqual(publisher.publish(Existing(),'demo-shared-demo-ms',raw),expected)

    def test_store_readback_and_version(self):
        s3=S3();store=a.Store(s3,'protected','attempts/')
        store.create('a',b'approved');self.assertEqual(store.read('a'),b'approved')
        with self.assertRaises(FileExistsError):store.create('a',b'evil')
        self.assertIsNone(store.read('missing'))
        for path in ('../escape','/absolute','a\\b'):
            with self.assertRaises(c.Rejected):store.create(path,b'evil')

    def test_exact_git_blob_source_and_rejection(self):
        raw=b'approved\r\nbytes\n';sha=hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()
        def fetch(path):
            if path.startswith('git/commits/'):return {'sha':'a'*40,'tree':{'sha':'b'*40}}
            if path.startswith('git/trees/'):return {'sha':'b'*40,'truncated':False,'tree':[
                {'path':'demo-api/Program.cs','type':'blob','mode':'100644','sha':sha}]}
            return {'sha':sha,'encoding':'base64','size':len(raw),'content':base64.b64encode(raw).decode()}
        with tempfile.TemporaryDirectory() as tmp:
            source=a.Source(fetch);source.acquire('Kendall04/terragrunt_demo','a'*40,tmp)
            self.assertEqual((Path(tmp)/'demo-api/Program.cs').read_bytes(),raw)
        for mutation in ('blob','symlink','traversal','commit'):
            def hostile(path):
                result=fetch(path)
                if mutation=='blob' and path.startswith('git/blobs/'):
                    result['content']=base64.b64encode(b'evil').decode()
                if path.startswith('git/trees/'):
                    if mutation=='symlink':result['tree'][0]['mode']='120000'
                    if mutation=='traversal':result['tree'][0]['path']='demo-api/../escape'
                if mutation=='commit' and path.startswith('git/commits/'):result['sha']='c'*40
                return result
            with tempfile.TemporaryDirectory() as tmp:
                with self.assertRaises((c.Rejected,a.supervisor.Rejected)):
                    a.Source(hostile).acquire('Kendall04/terragrunt_demo','a'*40,tmp)

    def test_verified_bundle_survives_warm_invocations(self):
        import bundles
        root=Path(__file__).resolve().parents[3]
        catalog=json.loads((root/'terraform/infra/security/authority.json').read_text())['control_bundles']
        for cls,consumer in (('request-gateway','release'),('status','status-neutral')):
            raw=bundles.artifact(root,catalog,cls);s3=S3()
            key='bundles/sha256/'+c.digest(raw)+'.json'
            version=s3.put_object(Bucket='bundles',Key=key,Body=raw,IfNoneMatch='*')['VersionId']
            ref=dict(bucket='bundles',key=key,version_id=version,sha256=c.digest(raw),consumer=consumer,**{'class':cls})
            with patch.object(runtime,'_installation',None):
                first=runtime.installed(s3,ref);second=runtime.installed(s3,ref)
                self.assertEqual(first,second);self.assertTrue((first/'scripts/qualification/finalizer.py').is_file())
                with self.assertRaises(c.Rejected):runtime.installed(s3,dict(ref,version_id='other-version'))
                runtime._installation[1].cleanup()

    def test_gateway_closed_and_outer_only(self):
        s3=S3();cb=CodeBuild();ops=a.Store(s3,'protected','operations/demo-api/')
        gateway=services.Gateway(cb,ops,ACCOUNT,REGION,lambda commit:commit=='a'*40)
        for extra in ('projectName','environmentVariablesOverride','buildspecOverride'):
            with self.assertRaises(c.Rejected):gateway.release({'source_commit':'a'*40,extra:'evil'})
        result=gateway.release({'source_commit':'a'*40})
        self.assertEqual(set(cb.calls[0]),{'projectName','idempotencyToken'})
        self.assertEqual(cb.calls[0]['projectName'],c.CONTROLLERS['build/release'][0])
        self.assertEqual(set(result),{'operation_id'})

    def test_outer_completion_is_wakeup_only(self):
        ops=a.Store(S3(),'protected','operations/demo-api/')
        with self.assertRaises(c.Rejected):services.wakeup({'source':'aws.codebuild','detail-type':'CodeBuild Build State Change',
            'account':ACCOUNT,'region':REGION,'detail':{'project-name':c.WORKERS['image'],'build-status':'SUCCEEDED'}},ops,ACCOUNT,REGION)

    def test_status_unknown_is_sanitized(self):
        s3=S3();ops=a.Store(s3,'protected','operations/demo-api/');records=a.Records(a.Store(s3,'protected','attempts/demo-api/'))
        self.assertEqual(services.status({'operation_id':OP},ops,records),{'operation_id':OP,'state':'UNKNOWN'})

    def test_full_split_trace_qualifies_through_unchanged_core(self, failures=None):
        s3=S3();cb=CodeBuild(s3);ops=a.Store(s3,'protected','operations/demo-api/')
        cb.failed=failures or {}
        with patch('services.uuid.uuid4',return_value=OP):
            services.Gateway(cb,ops,ACCOUNT,REGION,lambda _:True).release({'source_commit':'a'*40})
        control=a.Control(ops);op=control.operation(OP)
        context={k:op[k] for k in a.supervisor.CONTEXT_KEYS}
        context.update(github_run_id='0',github_run_attempt='0',created_at='2026-09-25T00:00:00Z',controller_image={
            'owner':'SECURITY_ROOT_OWNED','binding':'build/release','approval':'ADMIN_VERIFIED',
            'uri':REGISTRY+'/e1-controller-build@sha256:'+'c'*64})
        class Source:
            def acquire(self,repository,commit,workspace):
                root=Path(__file__).resolve().parents[3]
                # Actual committed input set; exclude generated application output.
                for path in (root/'demo-api').rglob('*'):
                    if not path.is_file() or set(path.parts)&{'bin','obj','.git'}:continue
                    target=Path(workspace)/path.relative_to(root);target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(path.read_bytes())
                return dict(repository=repository,commit=commit,workspace=workspace)
        payload=a.Payload(Source(),workers.Workers(cb,ACCOUNT,REGION,'demo-shared-demo-ms',OP),exchange.Exchange(s3,'quarantine',OP))
        records=a.Records(a.Store(s3,'demo-release-artifacts-'+ACCOUNT,'attempts/demo-api/'))
        manifests=a.Manifests(s3,'demo-release-artifacts-'+ACCOUNT)
        image=a.Images(ECR(),payload,REGISTRY,'demo-shared-demo-ms')
        result=a.supervisor.Supervisor(context,control,payload,image,manifests,records).run({'operation_id':OP})
        if failures:
            if c.WORKERS['probe'] in failures:
                self.assertEqual(result['schema'],'E1_SUPERVISED_RESULT_V1',result)
                self.assertEqual(result['state'],'FAILED',result)
            else:
                self.assertEqual(result['schema'],'E1_BUILD_ATTEMPT_TERMINAL_V1',result)
                self.assertEqual(image.ecr.calls,[])
            evidence=services.Evidence(cb,ops,records,manifests)
            qualifications=services.Qualifications(a.Store(s3,'demo-release-artifacts-'+ACCOUNT,''))
            with self.assertRaises(a.finalizer.Rejected):
                a.finalizer.Finalizer(ACCOUNT,REGION,evidence,qualifications).finalize({'operation_id':OP})
            return
        self.assertEqual(result['schema'],'E1_SUPERVISED_RESULT_V1',result)
        self.assertEqual(result['state'],'SUCCEEDED',result)
        self.assertEqual(set(result['checks'].values()),{'PASS'})
        evidence=services.Evidence(cb,ops,records,manifests)
        qualifications=services.Qualifications(a.Store(s3,'demo-release-artifacts-'+ACCOUNT,''))
        final=a.finalizer.Finalizer(ACCOUNT,REGION,evidence,qualifications).finalize({'operation_id':OP})
        self.assertTrue(final)
        self.assertEqual([x['projectName'] for x in cb.calls],[c.CONTROLLERS['build/release'][0],*c.WORKERS.values()])
        # Independent exact source transfers; no dotnet workspace adoption.
        sources=[kw for method,kw in s3.calls if method=='put' and '/source-' in kw['Key']]
        self.assertEqual(len(sources),2);self.assertEqual(sources[0]['Body'],sources[1]['Body'])
        self.assertNotEqual(sources[0]['Key'],sources[1]['Key'])

    def test_failed_worker_cannot_publish_or_qualify(self):
        for project,phase in ((c.WORKERS['dotnet'],'PRE_BUILD'),(c.WORKERS['dotnet'],'BUILD'),
                              (c.WORKERS['dotnet'],'POST_BUILD'),(c.WORKERS['image'],'BUILD'),
                              (c.WORKERS['probe'],'PRE_BUILD'),(c.WORKERS['probe'],'BUILD')):
            with self.subTest(project=project,phase=phase):
                self.test_full_split_trace_qualifies_through_unchanged_core({project:phase})
