# E1 WP1 authority contracts and evidence

Run from the repository root with installed Python 3.10+ and Git:

```text
python -I -B scripts/tests/authority/run.py --report <temporary-report-path>
```

No dependencies are installed. Success means `WP1_CHARACTERIZATION_PASS`, not
E1 acceptance. The current repository is expected to violate E1. Reports contain
executed test IDs, results, source hashes, Git revision/tree, dirty status and
baseline path witnesses. Store generated reports outside the repository.

## Contract sources

- `responsibilities.json`: eleven approved TARGET_REQUIREMENT responsibilities.
- `principals.json`: current GitHub role instances and workload role declarations;
  incomplete workload instance expansion is explicitly UNVERIFIED.
- `necessity.json`: evaluated statements mapped to consumers and purpose. Actual
  actions/resources/conditions are extracted from their source references.
- `ownership.json`: current ownership references and required target ownership.
- `source-inventory.json`: reviewed operational files, Terraform declarations,
  credential acquisitions, role inputs and executable dependencies.
- `synthetic-context.json`: fixed synthetic module inputs, not account discovery.
- `capabilities.json`: restricted primitive policy-permission applicability.
- `governance.json`: external expectations, all UNVERIFIED; both name-based and
  immutable-ID GitHub subject formats are represented.
- `requests.json`: closed capability-specific request shapes, not authorization.
- `runtime.schema.json`: closed canonical-task structural skeleton.
- `runtime-fields.json`: security-property rules and REJECT_UNKNOWN default.
- `runtime-vocabulary.json`: reviewed field vocabulary, explicitly not a complete
  downloaded AWS API model. WP4 must pin the full applicable model.

The runtime schema does not authorize a role pair, image or deployment. WP4 must
enforce exact protected bindings, image qualification, container-specific rules,
response normalization and pre-start ordering. Request fixture capacity limits
are synthetic, not installed operational policy. No controller exists in WP1.

## Source binding and shared-source migration

The JSON contracts are intended for later Terraform/controller and test consumers.
WP1 does not change existing Terraform policies. `source.py` provides a narrow
baseline adapter over actual aws_iam_policy_document blocks, role trust references,
inline policies and attachments. It admits literal strings/lists, scalar
interpolation, local references, concat/distinct and the existing environment
count forms. Unsupported expressions raise `Unsupported`; no Terraform, provider,
hook or source program is executed. This is not a general HCL interpreter.

Mutation tests edit actual policy/trust/attachment sources in disposable copies
and observe changed authorization. There is no golden policy JSON copy. Later
packages should consume the shared declarative sources directly rather than
expand the adapter into a Terraform interpreter.

Inventory covers operational files under Terraform, .github and scripts, plus
configuration/executable suffixes elsewhere. New, missing or changed sources fail
admission. The runner never refreshes the inventory automatically. Review hashes
establish freshness, not semantic correctness. UNVERIFIED surfaces cannot supply
a DENY or a passed E1 criterion. AWS-managed policy contents, jsonencode workload
policies, full root/module expansion and live configuration remain unevaluated.

## Evaluation limits

Supported: identity union, explicit deny precedence, boundary intersection, exact
role/service/federated trust, exact same-account role/session resource grants,
IAM star/question-mark matching, String/Arn Equals/Like, Bool/Null, set operators,
non-set IfExists and absent keys. Combined set-operator/IfExists expressions are UNKNOWN. Session grants bypass implicit identity and
boundary denies but not explicit denies. Same-account context must be explicit.

UNKNOWN or source Unsupported: NotAction/NotResource/NotPrincipal, policy
variables, negated/numeric/date/IP conditions, wildcard principals (including
conditioned wildcards), account-root/user delegation, cross-account resource
grants, KMS resource authorization, unsupported multivalued conditions,
multi-resource APIs, unmodeled dependencies and service-linked delegation.

`evaluate` answers a policy-permission question. `authorize` adds restricted
action/resource/context admission. ECS baseline paths explicitly combine primitive
registration, both PassRole checks, task service trust and service activation.
They do not claim that registration alone authorizes execution or that any KMS
key policy grants decrypt. The graph computes a fixed point of conjunctive
prerequisites and preserves statement witnesses. A proven alternative path wins
over an unknown path; UNKNOWN never becomes DENY.

Baseline findings cover token interchange, prod high-risk acceptance of dev
approval, workload-policy mutation plus ECS execution, runtime and role-field
substitution, direct routing, and combined legacy publication/prod-record writes.
They are repository-model reachability findings, not executed exploits. This is
a bounded graph foundation, not a complete automatic AWS escalation finder.

## Hermetic and positive evidence

Only fixed local Git metadata reads run before the guard, with system/global
configuration disabled and fsmonitor disabled. The runner then scrubs credential
and proxy variables, disables metadata discovery, points AWS configuration to the
null device, empties PATH and installs an audit hook denying sockets, processes,
os.system and dynamic-library loading. Guard tests attempt AWS/Terraform/GitHub
CLI launches and metadata resolution and require rejection before execution.

This is an accidental-I/O guard for trusted tests, not a malicious-native-code
sandbox. No application/Terraform code is executed. Tests use disposable files.
Positive fixtures include exact OIDC acquisition, environment reads, exact
PassRole matching, canonical runtime shape and actual baseline paths. Essential
grant removal and deny-all results break those assertions. Mutations cover old
subjects, policy mutation, PassRole, ECS, ALB, attachments, unsupported syntax,
workload boundary drift and new source files.

No AC1â€“AC16 is fully accepted by this package. External configuration remains
unverified, and no WP2â€“WP7 resources or behavioral changes are included.


## V2 correction boundary (F1–F5)

V1 is `fd6e17d89a805d05fe120f95d1b6fd61f8e09b33`; V2 is a separate correction
commit, not E1 acceptance. The spec and plan remain immutable.

* F1: condition-key names are case-insensitive; colliding request keys fail as
  UNKNOWN. Values retain case. ArnEquals and ArnLike use identical wildcard
  comparison of the six ARN components (the last component may contain colons).
  Empty/null datasets have explicit set/Null behavior. Mixed null/non-null sets
  and combined set/IfExists operators are unsupported, not approximated.
* F2: principal admission precedes matching. Exact AWS role ARNs, resource-policy
  session ARNs, and trust-only service/OIDC principals are modeled. Account/root,
  user, wildcard, trust-session and other delegation forms return UNKNOWN,
  including when conditioned or nonmatching. Trust results describe the trust
  side, not complete cross-account STS acquisition.
* F3: `source.RESOURCE_ATTRIBUTES` is the closed semantic resource schema. The
  adapter admits role, managed policy, separate inline policy and role-policy
  attachment resources, with the existing environment-count expression only.
  Other resources, nested inline/dynamic blocks, for_each, boundaries, alternate
  attachment attributes, Terraform JSON and policy-document merges are rejected.
  Unreferenced/count-zero documents are inspected too. Exact provider declarations
  are bound separately rather than interpreted. Refreshing source-inventory hashes
  does not relax these checks. The report enumerates security declarations outside
  this subset as SOURCE_ADMISSION_UNKNOWN, including workload expansion, KMS,
  resource policies, instance profiles and delegated Lambda permissions. These are
  known unsupported current surfaces, never an absence-of-authority assertion.
* F4: every synthetic module input/provider value has a SOURCE_BINDING entry.
  Locals must retain the exact admitted expression; variables must retain their
  admitted declaration. Provider/account/region declarations must exist. Values
  are fixed fixture inputs, not discovered root configuration. Separate reviewed
  workload dependency pins guard module, role, service, task-family and cluster
  wiring; updating the general inventory cannot update those pins. Names are
  derived from the validated module/role/service declarations, not PassRole
  allowlists. A changed/missing binding produces SOURCE_BINDING_FAILURE or UNKNOWN.
  These pins deliberately reject even harmless dependency edits pending review;
  they are not policy snapshots or a general Terraform interpreter.
* F5: each graph outcome has explicit coverage: COMPLETE_FOR_CURRENT_ADMITTED_MODEL,
  PARTIAL or UNKNOWN, with a reason. One grounded path establishes WITNESS_ALLOW.
  Only explicit complete coverage permits EFFECTIVE_DENY. Missing coverage defaults
  to PARTIAL and cannot establish DENY. All current baseline outcomes remain
  PARTIAL: the bounded graph has no exhaustive AWS escalation proof. Inline and
  create-managed-policy/attach routes are independent witnesses. Version/default,
  trust and existing Lambda mutation/invocation permissions are exposed separately;
  unexpanded attachment/default/executable/config transitions remain path gaps.
  Removing both modeled broadening routes therefore yields UNKNOWN, not DENY.
  Closed synthetic two-route graphs test the complete-coverage DENY behavior.

The regression suite changes disposable real sources, acknowledges inventory
hashes, and still requires semantic/binding rejection. It also checks role rename,
role removal, module drift, synthetic ARN mismatch, alternative-route removal,
cycles and independent IAM truth tables. Existing positive controls remain active.

N1 remains a failed Git Bash selector run caused by temporary-directory cleanup.
N2 remains outstanding supported-Linux validation; the inspected docker-desktop
WSL environment has no Bash/Git/Python. Neither is claimed passed. They are separate
from the F1–F5 correction and require no selector redesign here.
