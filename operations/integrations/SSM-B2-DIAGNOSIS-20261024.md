# SSM b2: native read-only diagnosis — 2026-10-24

## Result and confidence

**Proven failure layer: per-target Run Command authorization before script execution. Exact failing condition/policy remains unproven.** This is narrower than “SQL/Python failed” or “IAM in general”. Native CloudTrail confirms initial API acceptance by the intended operator; native GetCommandInvocation still returns terminal AccessDenied/−1 and no start. The ObserverControl plugin name labels the planned step; it does not prove the agent ran its shell script.

This investigation used existing Windows `cnp-cert-dev`, account341936017254/us-east-1, identity `cnp-cert-admin`, for read-only CloudTrail/SSM/IAM metadata. No AssumeRole call, SendCommand, reboot, resource creation, credential export, policy update or logging-service activation. CloudTrail LookupEvents/GetCommandInvocation/GetRole/list policies/GetPolicy/GetPolicyVersion all succeeded. No new access denial occurred and no previously denied action was retried. An initial local CloudTrail parser failed because Parameters was not an object; it was corrected without disclosing parameters or executing a command.

Sanitized native evidence: [ssm-b2-native-investigation.json](fixtures/ssm-b2-native-investigation.json). Original local readback files and hashes are retained under `task-3/ssm-b2-investigation`. The fixture contains real readbacks, not constructed success. Source IP, credentials and command bodies are excluded. No test was run against the old instance.

## Native timeline and bindings

| Time UTC | Event / evidence | Conclusion |
| --- | --- | --- |
| 06:09:12 | AssumeRole event `e5c2371e-61df-4d13-bdf7-f5c70d1a25aa` | Original admin assumed operator with3600s, no passed session policy/policy ARNs/tags |
| 06:09:13 | SendCommand event `254a45b0-55a4-4cd0-af79-289645d6a0c7`; command `a3894787-1d3d-430a-9d6d-900578376935` | API accepted under operator, no errorCode |
| 06:39:00 | PutRolePolicy event `9c38ddbc-b134-4628-80a7-37049ee5ed74`, `SentinelObserverr20261024b2` | Exact supplement was installed, not merely planned |
| 06:40:55 | AssumeRole event `072620c0-4d73-4d03-8e2c-a6fe187fb3e7` | New operator session after update; no passed session restriction |
| 06:40:56 | SendCommand event `524b7c80-4fe5-463d-95a9-c17e03f72c4a`; command `e5d894d1-1ce7-4d49-8c4f-bd8a72f5ede3` | One approved retry accepted but again terminal AccessDenied/−1 |
| 17:54–17:58 | Native readback today | Both invocations remain failed; operator has no boundary, zero inline policies, ten attached Parts; Part4 defaultv5 and Part7 defaultv3 equal preserved originals |

Both requests bind instance `i-009e213ec6cf1e3cb`, document `ecs-sentinel-r20261024b2-observer-control`, version1, SHA256 `29b383c0a0a1731781ab6c3f828d5945de4afdbbc8912b17f2f495b52a3a66fe`, and session issuer TerragruntDemoDevOperator. The command-specific Boto3 GetDocument calls succeeded immediately before both sends. CloudTrail masks/non-object-encodes Parameters; local intent and source bind Action=status, but CloudTrail does not independently reveal that parameter. Document snapshot: typeCommand, schema2.2, one aws:runShellScript step ObserverControl, timeout90, Action is String with explicit allowedValues/allowedPattern including status.

GetCommandInvocation now independently confirms document/version/plugin, Failed/AccessDenied, ResponseCode−1, ExecutionStartDateTime null, no end time. AWS documents −1 as not started/not received and AccessDenied as initiator lacking target-node access: [command statuses](https://docs.aws.amazon.com/systems-manager/latest/userguide/monitor-commands.html), [invocation API](https://docs.aws.amazon.com/systems-manager/latest/APIReference/API_GetCommandInvocation.html). Initial acceptance therefore cannot be admitted as agent/plugin success.

## What the installed supplement actually covered

The native06:39 PutRolePolicy content canonical compact JSON SHA256 is `9d566ec1b589ec6bfdacd74ab882eef911ee8e2d99078ecdbe8b212f6a0bf8f6`. Besides original region/tag branches for ViaAWSService=false/true, it contained ExactOwnObserverViaSsmServiceContext:

- SendCommand on exactly the above custom document ARN and exact EC2 instance ARN;
- Bool ViaAWSService=true;
- DateLessThan CurrentTime2026-10-25T05:41:51Z;
- no RequestedRegion or resource-tag condition in this exact forwarded statement.

The retry occurred115s after installation and used a fresh role session. Thus “supplement never installed”, “used an older session with an extra inline session deny”, “only forgot the tag/region in the new forwarded statement”, “deadline already elapsed”, “wrong document/version/hash/target in API request” are not supported explanations. Event history does not prove when every service-side cache converged, so propagation is reduced in plausibility rather than mathematically excluded.

AWS requires a ViaAWSService=true allowance when SendCommand uses global keys, and documents tag restrictions producing exactly this AccessDenied terminal status: [Run Command setup](https://docs.aws.amazon.com/systems-manager/latest/userguide/run-command-setting-up.html). Our supplement addressed a grounded hypothesis, but the result proves it was not a validated fix.

A constructed IAM evaluation of that exact new statement with matching ARNs, ViaAWSService=true and a date before expiry would allow regardless of region/tag. That is a logical statement check, **not a simulation of the actual SSM context**. If the asynchronous evaluation used false instead, it would still require the original branch's region/tag. The value supplied at that phase is not in available CloudTrail. Do not remove conditions or use BoolIfExists to paper over the unknown. IAM documents CurrentTime and ViaAWSService as always present in normal request context: [global keys](https://docs.aws.amazon.com/IAM/latest/UserGuide/reference_policies_condition-keys.html). Their absence is not a proven missing-key cause and is not justification to remove expiry.

## Ranked explanations and evidence gaps

| Rank | Hypothesis | Evidence / what would decide it |
| --- | --- | --- |
| 1 | Target authorization re-evaluation uses a different context/resource/decision than the inferred forwarded one | Fits documented per-target AccessDenied after API acceptance. Need SSM service evaluation showing actual action/resource/principal/context and implicit/explicit deny; CloudTrail SendCommand lacks that trace |
| 2 | Another effective restriction or service-side policy state/caching | No boundary in captured/current GetRole; no passed session policies in both native AssumeRole events; inspected saved Parts contain no matching SendCommand deny. SCP/other service restrictions and exact async effective policy set were not observed. Need historical effective decision or service trace, not current policy simulation |
| 3 | Agent/document delivery authorization | Node was Online, but that alone does not prove GetDocument/message-channel access. Captured node policy has own-document Get/Describe; queried CloudTrail GetDocument events show operator/Terraform clients, no matching node-client event. Absence of an event is not proof no agent call occurred. Agent authorization logs were not exported and host/disks are gone |
| 4 | Parameter/hash/plugin/script defect | Bound document/hash and pre-send GetDocument are consistent; no execution start/output. This is weak for a shell/program failure. Need service validation error or agent trace to promote it. Do not debug SQL/backup/systemd as though status action ran |

The captured console contains no AccessDenied/Unauthorized entry; it is cloud-init output, not a substitute for `/var/log/amazon/ssm/amazon-ssm-agent.log`. S3/CW command outputs were disabled/empty in the preserved invocation. We cannot recover deleted local disk logs by recreating the instance or querying another host. No paid diagnostic environment is warranted merely to repeat this observation.

## Minimum next step without creation

1. Use the two command IDs, event IDs, region, role ARN, document/hash, exact supplement content/hash, installation time and fresh-session timeline as an evidence packet. Request the **SSM per-target authorization decision** for those invocations from existing service-side diagnostic access or AWS Support if the account already has an appropriate support path. Request actual context and failed statement/resource, not another blanket Allow. This document sends no support message or opens a paid support plan.
2. An authorized administrator can supply existing organization/SCP/effective-policy history if applicable; do not infer it from the ten current attachments. No new organizations/logging permission or service was requested here. Current role has already been cleaned, so current implicit-deny simulation would not reconstruct b2.
3. If service-side trace is unavailable, state the root cause cannot be proven from retained customer evidence. Any future diagnostic execution would need a separate bounded proposal, the same principal/document contract, full sanitized evidence capture before teardown and a specific hypothesis/correction. No retry is authorized by this investigation. Do not keep escalating guessed conditions or substitute another document/principal.
4. Keep the ECS recovery/live package blocked until this transport gate is resolved or a genuinely different architecture is openly reviewed; no covert execution-route change. In parallel, local application-network/cutover work may proceed without AWS, preserving original runtime ownership.

No new framework, production change or IAM patch follows from this diagnosis. It narrows the failing boundary and excludes concrete wrong assumptions; it does not claim an exact failing key or an E2E fix that evidence cannot support.
