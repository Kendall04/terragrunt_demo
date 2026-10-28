# Narrow Part4 amendment — proposal only

Run `ecs-sentinel-r20261023b1`, account `341936017254`, region `us-east-1`.
No execution consent has been granted for this new cycle. No IAM policy was
changed, no role assumed, no real DeleteBucket requested, no artifact uploaded.

## Exact permission delta

Policy `arn:aws:iam::341936017254:policy/TerragruntDemoDevOperatorPart4` currently
has default version `v5`. Its one unconditional mixed Deny includes seven actions
on `*`. The proposal removes only `s3:DeleteBucket` from that statement, then adds
a separate Deny of that same action using NotResource with exactly
`arn:aws:s3:::ecs-sentinel-r20261023b1-341936017254`.

Every original Allow and the other six Deny actions are unchanged. There is no
wildcard in the exception and no new Allow. The existing proposed temporary
inline policy supplies the exact-bucket Allow; it is also still uninstalled.
IAM creation/role-policy writes/attachments, bucket-policy writes, KMS key deletion
and Secrets Manager deletion remain denied by Part4. Runtime NAT permissions and
workers stay absent. No EKS policy or resource is changed.

Read-only attachment inventory found only `TerragruntDemoDevOperator` (no users
or groups). This managed-policy change affects **all sessions of that role** until
restored; it is not session-specific or an automatic timed permission expiry.
The proposed trial remains new USD1, at most24h with an approximately2h target,
same16 main resources plus3 IAM bootstrap resources and two stack objects.
Original budgets are closed; originals/backups/state and SQL2+2 days are untouched.

## Hashes (SHA256)

| Document | File bytes, UTF8/LF | Canonical sorted compact JSON |
| --- | --- | --- |
| Current default v5 | `f494b2d1915b9659c013ef955e83eb85f02ef2d02248ef142022ce42f8aaac8d` | `2dee64162063bf48daa6be793a92399fd8383104cd102078ae4bd7427a7876e2` |
| Proposed temporary replacement | `c185647fdcd4a9b77bd8c4c6d1a83d45ce18f7638ea904763baa87052ade8fe1` | `7e267edd726cbc087841d46dacd98530d26f6811583c2887b69e36030f84a077` |
| Preserved historical v1 | `4a35504fb3f4b6b15028168a495759e4a09471f7ccebc7184f7cc73dbb402f37` | `38824410ef0391c7f9c1afd5a62967fa377a74a16e013b973facdba91f68fb6b` |

Unchanged operator temporary Allow file hash:
`f74aa44382afccba19fe8437750597b84f42cd60cd95a72ab5a354f38b3efd2d`.
Its canonical hash is
`769dbaa1869754a41bae4690c890edb32f653b0e7e61b1fde8726bc72b770284`.

## Version-capacity consequence — include in the same consent

AWS has all five versions `v1`–`v5` saved. A direct managed-policy replacement
cannot preserve every original version identifier. The minimal proposed route
archives the already captured, nondefault `v1`, deletes that one IAM version to
free a slot, creates the proposal as a new nondefault version, verifies its hash,
then selects that returned version as default. **Do not guess its VersionId.**
Original default `v5` and versions `v2`–`v4` are never deleted. At closure restore
`v5`, remove the trial version, then recreate the preserved `v1` document as a
nondefault version. This restores the exact original effective policy and the
original set of five policy documents. The recreated historical document receives
a different VersionId/CreateDate; **that metadata cannot be restored exactly**.
If that historical-version substitution is not included in consent, the cycle
remains blocked; no alternate principal or policy-attachment workaround is proposed.

## Future operations and exact reversal (not executed)

Existing owner principal: `arn:aws:iam::341936017254:user/cnp-cert-admin`, through
Windows `cnp-cert-dev`, performs approved bootstrap/policy reversal. Operator
remains `arn:aws:iam::341936017254:role/TerragruntDemoDevOperator`; it receives no
IAM policy-management capability. Additional owner operations are scoped solely
to the Part4 policy ARN: GetPolicy/GetPolicyVersion/ListPolicyVersions/
ListEntitiesForPolicy, DeletePolicyVersion(v1 and the recorded trial version only),
CreatePolicyVersion(proposal and restored v1 content only), SetDefaultPolicyVersion
(recorded trial version, then original v5). Operation payloads must match the
reviewed hashes; no change to credentials or admin policies is proposed.

1. After consent, recheck identity, current default v5 hash, unchanged v1 hash,
   all five version IDs and sole attachment. Drift stops installation. Verify
   local preservation hashes before any deletion. Keep v5 available throughout.
2. Delete only the confirmed nondefault v1; create the proposed nondefault version,
   record returned ID and verify readback, then select it as default. Recheck exact
   temporary Allow and role-effective simulation before the first resource create.
   An uncertain API result is reconciled by reading versions/default before any
   retry. A denial causes no alternate-principal attempt.
3. Run the original bounded synthetic trial and retirement: disable mapping,
   wait leases/in-flight work, export/hash evidence, delete main stack, remove only
   retained own table/versions/delete markers/bucket, delete bootstrap stack.
   Never delete historical data, other buckets, EKS resources or unknown objects.
4. After the exact trial bucket has been retired (or immediately on an abort
   before any bucket exists), set Part4 default back to **v5** and read its canonical
   hash `2dee6416…7876e2`; remove the trial's separate inline policy and read back.
   Preserve the recorded trial version document/metadata, delete only that now
   nondefault version, recreate archived v1 **SetAsDefault=false**, and verify its
   canonical hash `38824410…f68fb6b`. Read back v5 default and the original five
   document hashes; v2–v4 IDs must be untouched. Record the new ID for archived v1.
5. Confirm role-effective DeleteBucket is denied again and exact resource absence;
   final receipt distinguishes restored effective policy, historical metadata delta,
   any cleanup failure, and actual charges unknown until billing evidence exists.

If creation fails after v1 removal but before default switching, v5 is still the
active restriction: remove any confirmed own nondefault proposal and restore v1
content without changing v5. If history recreation fails, effective rollback can
still be complete while history restoration is incomplete; report both accurately.
No runnable IAM mutation helper is included in this local package.

## Evidence and limits

15 focused offline tests verify exact unchanged Allow/other statements, fail-closed
source-shape checks, sole literal exception, other bucket/account/run/object negatives,
all other deny actions, captured baseline and preserved v1 hashes. Four read-only
SimulateCustomPolicy calls produced16 applicable action/resource checks: original+
Allow explicitDeny, proposal alone implicitDeny, proposal+Allow exact bucket allowed,
seven other resource negatives explicitDeny, and all six remaining actions on their
proper service resources explicitDeny. Eighteen invalid service/resource cross-products
are excluded from authority evidence; they returned implicitDeny. Standalone proposal
implicitDeny also lists three unrelated original Allow contexts, disclosed in summary.
No new Allow is established by exact structural comparison, not by filling those
unrelated contexts with invented values.

Initial local result-reader assertions stopped on missing unrelated contexts and
the API's nested ResourceSpecificResults/invalid cross-product behavior. All raw
responses and partial receipts are preserved under task-3; subsequent analysis
reused completed responses, with no repeated simulation call. The final offline
verifier interprets per-resource decisions. These were test-reader corrections,
not API denials or any attempted AWS operation being retried.

This is a focused custom-policy simulation, not native deletion or proof against
every attached policy/SCP/resource policy at future execution. Actual attached
Part4 remains unchanged and still denies the current retirement plan.

Official semantics:
[Deny with NotResource](https://docs.aws.amazon.com/IAM/latest/UserGuide/reference_policies_elements_notresource.html),
[managed-policy version limits and rollback](https://docs.aws.amazon.com/IAM/latest/UserGuide/access_policies_managed-versioning.html),
[SimulateCustomPolicy](https://docs.aws.amazon.com/IAM/latest/APIReference/API_SimulateCustomPolicy.html).

## Single bundled consent wording for parent

Authorize one `ecs-sentinel-r20261023b1` synthetic backup/Sentinel create/test/retire
cycle in341936017254/us-east-1, new USD1, at most24h (target2h), preserving original
closed budgets/resources/data. Include original scoped operator/bootstrap/runtime
permissions and resources, SNS subscription confirmation plus bounded failure and
recovery notice attempts to the **owner-supplied email**, and native deletion of
only trial resources/synthetic data. Include temporarily replacing Part4 with
the exact reviewed proposal solely to except that one trial bucket from DeleteBucket
Deny, affecting all operator sessions until rollback; keep all other restrictions.
Because five IAM versions already exist, include preserving/replacing historical
nondefault v1, restoring its exact content under a new IAM version ID at closure,
and restoring original default v5 plus removing temporary permissions. No AWS
execution is authorized by this preparation. Email, retention/frequency recommendations
and parameters remain for that same grouped owner decision; none are inferred or installed.
