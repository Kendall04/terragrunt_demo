# Draft only — SSM per-target authorization investigation

Not sent. No support case or support subscription has been created. Check existing technical-support entitlement before using; no upgrade or spend is authorized here.

Subject: Run Command accepted, then target AccessDenied before execution — request authorization decision

Account: 341936017254; region: us-east-1.

Please investigate the per-target authorization decisions for these existing Run Command invocations (UTC):

- 2026-10-24 06:09:13 — a3894787-1d3d-430a-9d6d-900578376935; CloudTrail SendCommand event254a45b0-55a4-4cd0-af79-289645d6a0c7.
- 2026-10-24 06:40:56 — e5d894d1-1ce7-4d49-8c4f-bd8a72f5ede3; CloudTrail SendCommand event524b7c80-4fe5-463d-95a9-c17e03f72c4a.

Target: i-009e213ec6cf1e3cb. Caller issuer: arn:aws:iam::341936017254:role/TerragruntDemoDevOperator. Document: ecs-sentinel-r20261024b2-observer-control, version1, SHA25629b383c0a0a1731781ab6c3f828d5945de4afdbbc8912b17f2f495b52a3a66fe; step ObserverControl. Both SendCommand events were accepted without API error. ListCommandInvocations and GetCommandInvocation return Failed/AccessDenied, response−1, no start/output. ListCommands reports one completed target, ErrorCount0 and DeliveryTimedOutCount0. No CloudWatch/S3 command-output destination was configured.

Before the second attempt, the exact document+instance ViaAWSService=true allowance was installed06:39:00 (CloudTrail9c38ddbc-b134-4628-80a7-37049ee5ed74); its only other condition was CurrentTime before2026-10-25T05:41:51Z. Policy canonical compact JSON SHA2569d566ec1b589ec6bfdacd74ab882eef911ee8e2d99078ecdbe8b212f6a0bf8f6. A fresh operator session began06:40:55, with no passed session policy/policy ARNs. GetDocument succeeded before send. The allowance still did not resolve target authorization.

Please identify the actual principal/action/resource and relevant context (including ViaAWSService, region/tag conditions), effective policy/statement and implicit/explicit denial at asynchronous target validation. Did evaluation occur before delivery to the agent? If available, provide the backend authorization reason/trace and a narrowly scoped correction. We are not requesting wildcard access or another execution attempt.

The temporary infrastructure/document/roles were retired and original access restored. Agent disk logs are unavailable. Historical snapshots and sanitized CloudTrail/SSM evidence can be supplied; no passwords, tokens or command bodies are included. We have not retried either command or recreated resources for this request.
