"""WP3C extension of the existing compute generator, not a parallel root.

Canonical installation inputs are empty. Only admin-supplied verified records
can select the four responsibilities and three subordinate implementation jobs.
"""
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'scripts/internal_release'))
from e1_contract import CONTROLLERS, WORKERS, WORKER_ROLE, worker_buildspec, canonical, digest

SUPPORT = tuple('scripts/internal_release/' + name + '.py' for name in
                ('e1_contract','exchange','publisher','workers','adapters','services','runtime','worker'))


def support_identity(root):
    return digest(canonical({Path(p).name: digest((Path(root)/p).read_bytes().replace(b'\r\n',b'\n')) for p in SUPPORT}))


def contract(root, catalog):
    return {'schema':'E1_WP3C_SPLIT_PLANE_V1', 'owner':'SECURITY_ROOT_OWNED',
        'selected': {k:{'name':name,'engine':engine,'bundle_digest':catalog['consumer_references'][k]['sha256']}
                     for k,(name,engine) in CONTROLLERS.items()},
        'workers':{k:{'name':name,'owner':'build/release','role':WORKER_ROLE,
                       'privileged':k=='image','source':'NO_SOURCE','buildspec':worker_buildspec(k)}
                   for k,name in WORKERS.items()},
        'support_sha256':support_identity(root), 'installations':{}, 'runtime_approvals':{},
        'live':'UNVERIFIED_NOT_DEPLOYED','external_invocation':[],
        'controller_skeleton_identities':18,'subordinate_worker_identities':1,
        'reserved_lambda_bindings':['qualification-finalizer/qualification','status/status-neutral']}


def validate(root, doc):
    if doc.get('internal_release') != contract(root,doc['control_bundles']):
        raise ValueError('WP3C_SOURCE_ADMISSION_FAILURE: internal release contract')
    directory=Path(root)/'scripts/internal_release'
    admitted={Path(p).name for p in SUPPORT}|{'Controller.Dockerfile','Worker.Dockerfile'}
    for path in directory.rglob('*'):
        if '__pycache__' in path.parts:
            continue
        if path.is_symlink() or getattr(path,'is_junction',lambda:False)() or (
                path.is_file() and (path.parent!=directory or path.name not in admitted)):
            raise ValueError('WP3C_SOURCE_ADMISSION_FAILURE: unadmitted runtime source')


def policies(account, region, evidence, exchange, bundles_bucket, refs):
    """Exact action vocabulary; AWS-native project scope for BatchGetBuilds."""
    def allow(actions, resources, **kw):
        return dict(Effect='Allow',Action=actions,Resource=resources,**kw)
    def project(name):return f'arn:aws:codebuild:{region}:{account}:project/{name}'
    def objects(bucket,prefix):return f'arn:aws:s3:::{bucket}/{prefix}*'
    def logging(name):return allow(['logs:CreateLogStream','logs:PutLogEvents'],
        [f'arn:aws:logs:{region}:{account}:log-group:/aws/codebuild/{name}:log-stream:*'])
    def reads(prefix):return allow(['s3:GetObject','s3:GetObjectVersion'],[objects(evidence,prefix)])
    def writes(prefix):return allow(['s3:PutObject'],[objects(evidence,prefix)],
                                  Condition={'StringEquals':{'s3:if-none-match':'*'}})
    result={k:[] for k in CONTROLLERS}
    gateway=result['request-gateway/release']
    gateway.extend([allow(['codebuild:StartBuild'],[project(CONTROLLERS['build/release'][0])]),
                    writes('operations/demo-api/'),reads('operations/demo-api/'),reads('source-approvals/demo-api/')])
    build=result['build/release']
    build.extend([allow(['codebuild:StartBuild','codebuild:BatchGetBuilds'],[project(n) for n in WORKERS.values()]),
                  reads('operations/demo-api/'),writes('attempts/demo-api/'),reads('attempts/demo-api/'),
                  writes('releases/demo-api/by-digest/'),reads('releases/demo-api/by-digest/'),
                  allow(['s3:GetObject','s3:GetObjectVersion'],[objects(exchange,'quarantine/demo-api/')]),
                  allow(['s3:PutObject'],[objects(exchange,'quarantine/demo-api/')],Condition={'StringEquals':{'s3:if-none-match':'*'}}),
                  allow(['ecr:InitiateLayerUpload','ecr:UploadLayerPart','ecr:CompleteLayerUpload','ecr:PutImage','ecr:BatchGetImage'],
                        [f'arn:aws:ecr:{region}:{account}:repository/demo-shared-demo-ms'])])
    final=result['qualification-finalizer/qualification']
    final.extend([allow(['codebuild:BatchGetBuilds'],[project(CONTROLLERS['build/release'][0])]),
                  reads('operations/demo-api/'),reads('attempts/demo-api/'),
                  allow(['s3:GetObjectVersion'],[objects(evidence,'releases/demo-api/by-digest/')]),
                  writes('qualifications/demo-api/'),reads('qualifications/demo-api/')])
    result['status/status-neutral'].extend([reads('operations/demo-api/'),reads('attempts/demo-api/')])
    for binding,statements in result.items():
        prefixes={
            'request-gateway/release':['operations/demo-api/*','source-approvals/demo-api/*'],
            'build/release':['operations/demo-api/*','attempts/demo-api/*'],
            'qualification-finalizer/qualification':['operations/demo-api/*','attempts/demo-api/*','qualifications/demo-api/*'],
            'status/status-neutral':['operations/demo-api/*','attempts/demo-api/*']}[binding]
        statements.append(allow(['s3:ListBucket'],[f'arn:aws:s3:::{evidence}'],
            Condition={'StringLike':{'s3:prefix':prefixes},'NumericEquals':{'s3:max-keys':'1'}}))
        ref=refs[binding]
        statements.append(allow(['s3:GetObjectVersion'],[f'arn:aws:s3:::{bundles_bucket}/{ref["key"]}'],
                                Condition={'StringEquals':{'s3:VersionId':ref['version_id']}}))
        name,engine=CONTROLLERS[binding]
        group='/aws/lambda/' + name if engine=='LAMBDA' else '/aws/codebuild/' + name
        statements.append(allow(['logs:CreateLogStream','logs:PutLogEvents'],
                                [f'arn:aws:logs:{region}:{account}:log-group:{group}:log-stream:*']))
    result['payload']=[logging(name) for name in WORKERS.values()]
    return {k:{'Version':'2012-10-17','Statement':v} for k,v in result.items()}


def extend(tf):
    """Extend the one accepted controller_compute module; historical graph retained."""
    ex=lambda s:'${'+s+'}'
    tf['variable'].update({'account_id':{'type':'string'},'region':{'type':'string'},
        'admin_arn':{'type':'string'},'installations':{'type':'any','default':{}},
        'runtime_approvals':{'type':'any','default':{}}})
    local=tf['locals']
    local['wp3_contract']=ex('var.authority.internal_release')
    local['wp3_candidates']=ex('{ for key, v in local.wp3_contract.selected : key => merge(v, { install = try(var.installations[key], null), runtime = try(var.runtime_approvals[key], null) }) }')
    conditions=[
        'v.install.class == split("/", key)[0]', 'v.install.consumer == split("/", key)[1]',
        'v.install.sha256 == v.bundle_digest',
        'v.install.key == "bundles/sha256/${v.bundle_digest}.json"',
        'v.install.bucket == "e1-control-bundles-${var.account_id}-${var.region}"',
        'v.install.version_id != null', 'length(trimspace(v.install.version_id)) > 0',
        'v.install.version_id == trimspace(v.install.version_id)', 'length(v.install.version_id) <= 1024',
        '!contains(["null", "latest"], lower(v.install.version_id))',
        'v.install.installation == "VERIFIED"', 'v.install.readback == "EXACT_VERSION_BYTES_VERIFIED"',
        'v.install.version_origin == "CONDITIONAL_WRITE_RETURN"',
        'v.install.publisher == "SECURITY_ADMIN_EXTERNAL_BOOTSTRAP"',
        'v.install.configuration == local.wp3_contract.support_sha256',
        'v.runtime.owner == "SECURITY_ROOT_OWNED"', 'v.runtime.approval == "ADMIN_VERIFIED"',
        'v.runtime.binding == key', 'v.runtime.support_sha256 == local.wp3_contract.support_sha256',
        'can(regex("^${var.account_id}[.]dkr[.]ecr[.]${var.region}[.]amazonaws[.]com/e1-controller-${key == "build/release" ? "build" : replace(key, "/", "-")}@sha256:[0-9a-f]{64}$", v.runtime.uri))']
    local['wp3_ready']=ex('{ for key, v in local.wp3_candidates : key => v if try('+ ' && '.join(conditions)+', false) }')
    # The trusted controller cannot start until all three exact worker runtimes
    # and fixed technical-role bindings have been approved by security admin.
    local['worker_ready']=ex('{ for key, v in local.wp3_contract.workers : key => merge(v, { runtime = var.runtime_approvals["payload/${key}"] }) if try(var.runtime_approvals["payload/${key}"].owner == "SECURITY_ROOT_OWNED" && var.runtime_approvals["payload/${key}"].approval == "ADMIN_VERIFIED" && var.runtime_approvals["payload/${key}"].binding == "payload/${key}" && var.runtime_approvals["payload/${key}"].role == v.role && var.runtime_approvals["payload/${key}"].support_sha256 == local.wp3_contract.support_sha256 && can(regex("^${var.account_id}[.]dkr[.]ecr[.]${var.region}[.]amazonaws[.]com/e1-payload-${key}@sha256:[0-9a-f]{64}$", var.runtime_approvals["payload/${key}"].uri)), false) }')
    local['wp3_active']=ex('{ for key, v in local.wp3_ready : key => v if key != "build/release" || length(local.worker_ready) == 3 }')
    local['payloads']=ex('contains(keys(local.wp3_active), "build/release") ? local.worker_ready : {}')
    local['wp3_lambdas']=ex('{ for key, v in local.wp3_active : key => v if v.engine == "LAMBDA" }')
    local['wp3_build']=ex('{ for key, v in local.wp3_active : key => v if key == "build/release" }')
    local['evidence_bucket']=ex('"demo-shared-release-artifacts-${var.account_id}"')
    # This name is corrected from canonical ownership at generation call time.
    local['exchange_bucket']=ex('"e1-quarantine-${var.account_id}-${var.region}"')
    local['wp3_extra_roles']=ex('{ for key, v in local.wp3_lambdas : key => v if !contains(keys(local.nodes), key) }')
    local['wp3_role_arns']=ex('merge({ for key, v in aws_iam_role.execution : key => v.arn }, { for key, v in aws_iam_role.wp3_reserved : key => v.arn })')
    local['wp3_config']=ex('{ for key, v in local.wp3_active : key => jsonencode({ binding = key, account = var.account_id, region = var.region, bundle = { class = v.install.class, consumer = v.install.consumer, bucket = v.install.bucket, key = v.install.key, version_id = v.install.version_id, sha256 = v.install.sha256 }, runtime_image = v.runtime.uri, support_sha256 = local.wp3_contract.support_sha256, evidence_bucket = local.evidence_bucket, exchange_bucket = local.exchange_bucket }) }')
    r=tf['resource']
    trust=lambda service, source: {'Version':'2012-10-17','Statement':[dict(Effect='Allow',Action='sts:AssumeRole',Principal={'Service':service},**({'Condition':{'StringEquals':{'aws:SourceAccount':ex('var.account_id')},'ArnEquals':{'aws:SourceArn':source}}} if source else {}))]}
    local['wp3_trust']=ex('jsondecode('+json.dumps(json.dumps(trust('lambda.amazonaws.com',None)))+')')
    # Use native jsonencode so interpolation yields policy strings, not nested JSON.
    local['wp3_trust']=trust('lambda.amazonaws.com',None)
    local['wp3_build_trust']=trust('codebuild.amazonaws.com',ex('"arn:aws:codebuild:${var.region}:${var.account_id}:project/e1-controller-release"'))
    old=r['aws_iam_role']['execution']
    old['assume_role_policy']=ex('contains(keys(local.wp3_active), each.key) ? (each.value.engine == "CODEBUILD" ? jsonencode(local.wp3_build_trust) : jsonencode(local.wp3_trust)) : jsonencode(var.authority.controller_compute.role_trust[each.value.engine])')
    # Canonical stays inert. Positive policies replace, rather than accompany,
    # the old deny-all only for admitted selected implementations.
    r['aws_iam_role_policy']['inert']['for_each']=ex('{ for k,v in local.nodes : k=>v if !contains(keys(local.wp3_active),k) }')
    r['aws_iam_role']['wp3_reserved']={'for_each':ex('local.wp3_extra_roles'),'name':ex('"${each.value.name}-exec"'),
        'assume_role_policy':ex('jsonencode(local.wp3_trust)')}
    r['aws_iam_role']['payload']={'for_each':ex('length(local.payloads) == 3 ? { payload = true } : {}'),
        'name':WORKER_ROLE,'assume_role_policy':json.dumps(trust('codebuild.amazonaws.com',[
            'arn:aws:codebuild:${var.region}:${var.account_id}:project/'+n for n in WORKERS.values()]))}
    # Role policy expressions are supplied by canonical generated templates.
    refs={k:{'key':'__BUNDLE_KEY__', 'version_id':'__VERSION__'} for k in CONTROLLERS}
    ps=policies('${var.account_id}','${var.region}','${local.evidence_bucket}','${local.exchange_bucket}',
                'e1-control-bundles-${var.account_id}-${var.region}',refs)
    # Avoid eager indexing missing installations: policy values use each.value.
    local['wp3_policy_templates']={k:json.dumps(v) for k,v in ps.items() if k!='payload'}
    for k in CONTROLLERS:
        local['wp3_policy_templates'][k]=local['wp3_policy_templates'][k].replace(refs[k]['key'],'__BUNDLE_KEY__').replace(refs[k]['version_id'],'__VERSION__')
    r['aws_iam_role_policy']['wp3']={'for_each':ex('local.wp3_active'),'name':'wp3-internal',
        'role':ex('local.wp3_role_arns[each.key]'),'policy':ex('replace(replace(local.wp3_policy_templates[each.key], "__BUNDLE_KEY__", each.value.install.key), "__VERSION__", each.value.install.version_id)')}
    # aws_iam_role_policy.role requires role name, not ARN.
    r['aws_iam_role_policy']['wp3']['role']=ex('"${each.value.name}-exec"')
    # Explicit creation dependency: the literal role name alone does not order IAM.
    r['aws_iam_role_policy']['wp3']['depends_on']=['aws_iam_role.execution','aws_iam_role.wp3_reserved']
    r['aws_iam_role_policy']['payload']={'for_each':ex('aws_iam_role.payload'),'role':ex('each.value.name'),
        'name':'wp3-compromise-ceiling','policy':json.dumps(ps['payload'])}
    r.setdefault('aws_cloudwatch_log_group',{})['wp3']={'for_each':ex('merge({ for k,v in local.wp3_active : k => { name = "${v.engine == "LAMBDA" ? "/aws/lambda/" : "/aws/codebuild/"}${v.name}" } }, { for k,v in local.payloads : "payload/${k}" => { name = "/aws/codebuild/${v.name}" } })'),
        'name':ex('each.value.name'),'retention_in_days':14}
    r['aws_lambda_function']['wp3']={'for_each':ex('local.wp3_lambdas'),'function_name':ex('each.value.name'),
        'role':ex('local.wp3_role_arns[each.key]'),'package_type':'Image','image_uri':ex('each.value.runtime.uri'),
        'publish':True,'timeout':60,'memory_size':256,'reserved_concurrent_executions':1,
        'image_config':{'command':['runtime.handler']},
        'environment':{'variables':{'E1_PROTECTED_CONFIGURATION':ex('local.wp3_config[each.key]')}},
        'depends_on':['aws_cloudwatch_log_group.wp3','aws_iam_role_policy.wp3']}
    def project(each, role, buildspec, image, privileged, env):
        return {'for_each':ex(each),'name':ex('each.value.name'),'service_role':role,'build_timeout':15,
            'source':{'type':'NO_SOURCE','buildspec':buildspec},'artifacts':{'type':'NO_ARTIFACTS'},
            'environment':{'type':'LINUX_CONTAINER','compute_type':'BUILD_GENERAL1_SMALL','image':image,
                'image_pull_credentials_type':'CODEBUILD','privileged_mode':privileged,'environment_variable':env},
            'cache':{'type':'NO_CACHE'},'logs_config':{'cloudwatch_logs':{'status':'ENABLED','group_name':ex('"/aws/codebuild/${each.value.name}"')},'s3_logs':{'status':'DISABLED'}},
            'depends_on':['aws_cloudwatch_log_group.wp3']}
    outer={'version':'0.2','phases':{'build':{'on-failure':'ABORT','commands':['python3 /opt/e1/scripts/internal_release/runtime.py']}}}
    r['aws_codebuild_project']['wp3']=project('local.wp3_build',ex('local.wp3_role_arns[each.key]'),json.dumps(outer),
        ex('each.value.runtime.uri'),False,{'name':'E1_PROTECTED_CONFIGURATION','type':'PLAINTEXT','value':ex('local.wp3_config[each.key]')})
    r['aws_codebuild_project']['wp3']['build_timeout']=60
    r['aws_codebuild_project']['payload']=project('local.payloads',ex('aws_iam_role.payload["payload"].arn'),
        ex('jsonencode(each.value.buildspec)'),ex('each.value.runtime.uri'),ex('each.value.privileged'),[])
    r['aws_s3_bucket']={'quarantine':{'bucket':ex('local.exchange_bucket'),'force_destroy':False}}
    r['aws_s3_bucket_versioning']={'quarantine':{'bucket':ex('aws_s3_bucket.quarantine.id'),'versioning_configuration':{'status':'Enabled'}}}
    r['aws_s3_bucket_public_access_block']={'quarantine':{'bucket':ex('aws_s3_bucket.quarantine.id'),
        **dict.fromkeys(('block_public_acls','ignore_public_acls','block_public_policy','restrict_public_buckets'),True)}}
    r['aws_s3_bucket_server_side_encryption_configuration']={'quarantine':{'bucket':ex('aws_s3_bucket.quarantine.id'),
        'rule':{'apply_server_side_encryption_by_default':{'sse_algorithm':'AES256'}}}}
    r['aws_s3_bucket_lifecycle_configuration']={'quarantine':{'bucket':ex('aws_s3_bucket.quarantine.id'),
        'rule':{'id':'disposable-quarantine','status':'Enabled','filter':{'prefix':'quarantine/'},
                'expiration':{'days':1},'noncurrent_version_expiration':{'noncurrent_days':1},
                'abort_incomplete_multipart_upload':{'days_after_initiation':1}}}}
    account='${var.account_id}'
    region='${var.region}'
    admin='${var.admin_arn}'
    build_role=f'arn:aws:iam::{account}:role/e1-controller-release-exec'
    def deny(sid,actions,resources,condition):
        return {'Sid':sid,'Effect':'Deny','Principal':'*','Action':actions,'Resource':resources,'Condition':condition}
    qarn='arn:aws:s3:::${local.exchange_bucket}'
    quarantine={'Version':'2012-10-17','Statement':[
        deny('TLS',['s3:*'],[qarn,qarn+'/*'],{'Bool':{'aws:SecureTransport':'false'}}),
        deny('ControllerOrAdmin',['s3:*'],[qarn,qarn+'/*'],{'ArnNotEquals':{'aws:PrincipalArn':[admin,build_role]}}),
        deny('CreateOnly',['s3:PutObject'],[qarn+'/*'],{'StringNotEquals':{'s3:if-none-match':'*'}})]}
    evidence='arn:aws:s3:::${local.evidence_bucket}'
    statements=[deny('TLS',['s3:*'],[evidence,evidence+'/*'],{'Bool':{'aws:SecureTransport':'false'}}),
        deny('NoOrdinaryDelete',['s3:DeleteObject','s3:DeleteObjectVersion'],[evidence+'/*'],{'ArnNotEquals':{'aws:PrincipalArn':admin}}),
        deny('ImmutableWrites',['s3:PutObject'],[evidence+'/'+p+'*' for p in ('operations/','attempts/','releases/demo-api/by-digest/','qualifications/')],
             {'StringNotEquals':{'s3:if-none-match':'*'}})]
    owners={'operations/':'e1-gateway-release-exec','attempts/':'e1-controller-release-exec',
            'releases/demo-api/by-digest/':'e1-controller-release-exec','qualifications/':'e1-qualification-finalizer-exec',
            'eligibility/':None,'source-approvals/':None}
    for i,(prefix,role) in enumerate(owners.items()):
        principals=[admin]+([f'arn:aws:iam::{account}:role/{role}'] if role else [])
        statements.append(deny('Writer'+str(i),['s3:PutObject'],[evidence+'/'+prefix+'*'],{'ArnNotEquals':{'aws:PrincipalArn':principals}}))
    r['aws_s3_bucket_policy']={'quarantine':{'bucket':ex('aws_s3_bucket.quarantine.id'),'policy':json.dumps(quarantine)},
        'evidence':{'bucket':ex('local.evidence_bucket'),'policy':json.dumps({'Version':'2012-10-17','Statement':statements})}}
    # No caller can invoke the finalizer; only the exact outer-completion rule.
    local['completion']=ex('contains(keys(local.wp3_active), "build/release") && contains(keys(local.wp3_active), "qualification-finalizer/qualification") ? { release = true } : {}')
    r['aws_cloudwatch_event_rule']={'completion':{'for_each':ex('local.completion'),'name':'e1-release-completion',
        'event_pattern':json.dumps({'source':['aws.codebuild'],'detail-type':['CodeBuild Build State Change'],
            'account':[account],'region':[region],'detail':{'project-name':['e1-controller-release'],'build-status':['SUCCEEDED','FAILED','STOPPED']}})}}
    r['aws_cloudwatch_event_target']={'finalizer':{'for_each':ex('local.completion'),
        'rule':ex('aws_cloudwatch_event_rule.completion[each.key].name'),'target_id':'qualification',
        'arn':ex('aws_lambda_function.wp3["qualification-finalizer/qualification"].qualified_arn')}}
    r['aws_lambda_permission']={'completion':{'for_each':ex('local.completion'),'statement_id':'ExactOuterCompletion',
        'action':'lambda:InvokeFunction','function_name':ex('aws_lambda_function.wp3["qualification-finalizer/qualification"].function_name'),
        'qualifier':ex('aws_lambda_function.wp3["qualification-finalizer/qualification"].version'),
        'principal':'events.amazonaws.com','source_account':ex('var.account_id'),
        'source_arn':ex('aws_cloudwatch_event_rule.completion[each.key].arn')}}
    # CodeBuild pulls probe D using service credentials. The compromised worker
    # role never receives ECR authentication or pull/push permissions.
    pull={'Version':'2012-10-17','Statement':[{'Sid':'ExactProbePull','Effect':'Allow',
        'Principal':{'Service':'codebuild.amazonaws.com'},'Action':['ecr:BatchCheckLayerAvailability','ecr:GetDownloadUrlForLayer','ecr:BatchGetImage'],
        'Condition':{'StringEquals':{'aws:SourceAccount':account},'ArnEquals':{'aws:SourceArn':f'arn:aws:codebuild:{region}:{account}:project/{WORKERS["probe"]}'}}}]}
    pull['Statement'].append({'Sid':'ExclusiveContentPublisher','Effect':'Deny','Principal':'*',
        'Action':['ecr:InitiateLayerUpload','ecr:UploadLayerPart','ecr:CompleteLayerUpload','ecr:PutImage'],
        'Condition':{'ArnNotEquals':{'aws:PrincipalArn':[admin,build_role]}}})
    pull['Statement'].append({'Sid':'SeparateRepositoryAdministration','Effect':'Deny','Principal':'*',
        'Action':['ecr:DeleteRepository','ecr:DeleteRepositoryPolicy','ecr:SetRepositoryPolicy',
                  'ecr:PutLifecyclePolicy','ecr:DeleteLifecyclePolicy','ecr:BatchDeleteImage',
                  'ecr:PutImageTagMutability','ecr:PutImageScanningConfiguration'],
        'Condition':{'ArnNotEquals':{'aws:PrincipalArn':admin}}})
    r['aws_ecr_repository_policy']={'probe':{'repository':'demo-shared-demo-ms','policy':json.dumps(pull)}}
    runtime_names={('e1-controller-build' if k=='build/release' else 'e1-controller-'+k.replace('/','-')):
                   {'name':n,'engine':engine} for k,(n,engine) in CONTROLLERS.items()}
    runtime_names.update({'e1-payload-'+k:{'name':n,'engine':'CODEBUILD'} for k,n in WORKERS.items()})
    local['runtime_repositories']=runtime_names
    r['aws_ecr_repository']={'runtime':{'for_each':ex('local.runtime_repositories'),'name':ex('each.key'),
        'image_tag_mutability':'IMMUTABLE','image_scanning_configuration':{'scan_on_push':True}}}
    r['aws_ecr_repository_policy']['runtime']={'for_each':ex('local.runtime_repositories'),
        'repository':ex('aws_ecr_repository.runtime[each.key].name'),
        'policy':ex('jsonencode({ Version = "2012-10-17", Statement = [{ Effect = "Allow", Principal = { Service = each.value.engine == "LAMBDA" ? "lambda.amazonaws.com" : "codebuild.amazonaws.com" }, Action = ["ecr:BatchGetImage", "ecr:GetDownloadUrlForLayer", "ecr:BatchCheckLayerAvailability"], Condition = { StringEquals = { "aws:SourceAccount" = var.account_id }, ArnLike = { "aws:SourceArn" = each.value.engine == "LAMBDA" ? "arn:aws:lambda:${var.region}:${var.account_id}:function:${each.value.name}" : "arn:aws:codebuild:${var.region}:${var.account_id}:project/${each.value.name}" } } }] })')}
    tf['output']['internal_release']={'value':{'controllers':ex('keys(local.wp3_active)'),
        'workers':ex('keys(local.payloads)'),'external_invocations':[],
        'bundle_readers':ex('{ for k,v in local.wp3_active : k => local.wp3_role_arns[k] }'),'live':'UNVERIFIED_NOT_DEPLOYED'}}
    return tf
