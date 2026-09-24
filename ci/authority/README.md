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
boundary denies but not explicit denies. Supported resource ARNs supply their
account; accountless S3 ARNs require an explicit source-bound account for resource
policy questions. Contradictory supplied facts are UNKNOWN.

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

No AC1–AC16 is fully accepted by this package. External configuration remains
unverified, and no WP2–WP7 resources or behavioral changes are included.


## Historical V2 correction boundary (F1-F5)

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
from the F1-F5 correction and require no selector redesign here.

## Historical V3 semantic-admission correction (R1–R6)

V1 is `fd6e17d89a805d05fe120f95d1b6fd61f8e09b33`; V2 is
`687a75defdb86d1ec58940443b6fa17e62be7ac9`. V3 is a separate correction
commit on V2. This is WP1 characterization, pending independent review, not
WP1 acceptance or evidence that E1 is secure. The spec and plan are unchanged.

V3 introduced these stages; the V4 section below supersedes its admission,
effective-input and uncertainty behavior:

1. `discovery.py` recursively discovers Terraform native/JSON files and local
   module boundaries independently of the freshness inventory. JSON and all
   override forms are unsupported applicable configuration. New resource types,
   embedded policy/provisioner mechanisms and unresolved module/attachment
   destinations are uncertainty. Local nested files cannot inherit MODELED from
   their directory. Declaration IDs receive MODELED only after adapter admission.
2. `source.py` admits the narrow IAM subset; `bindings.py` verifies root/wrapper
   inputs, the actual IAM module invocation, workload module/role/cluster/service
   relationships and ALB/listener/rule identities. Unsupported binding expressions
   abort admission. Existing workload hash pins remain an additional freshness
   check; refreshing them cannot substitute for semantic relationship checks.
3. `evaluator.py` admits the complete condition expression before truth evaluation.
   Every ARN value is checked even when a prior value matches or the key is absent.
   Empty operator mappings and malformed keys/values are UNKNOWN. A normalized
   request identity rejects contradictory role/session/service aliases. A role
   session's account and unique role name establish its parent relationship;
   IAM paths are checked against supplied full aliases, never invented.
4. `graph.py` evaluates the actual trust referenced by each workload role, separately.
   It combines primitive permissions, both role trusts, passing and activation.
   Applicable unresolved policy controls taint positive as well as negative
   conclusions. A possible omitted Deny is not an alternative Allow path.
5. `coverage.py` issues completeness only for its closed synthetic fixture grammar.
   A certificate binds the source snapshot, graph, seeds, outcome, subjects,
   mechanism classes and route families. Closure rereads the fixture universe;
   stale sources/rules or applicable UNKNOWN invalidate the evidence. A plain
   COMPLETE label cannot prove DENY. Current repository outcomes have no issuer
   and remain PARTIAL. A valid positive path does not need a negative certificate.

Applicability is deliberately conservative. Exact module-local attachment
references to role-name patterns disjoint from the queried GitHub principals
remain UNKNOWN for those other roles, but do not manufacture uncertainty about
GitHub identity grants. KMS and Lambda resource delegation retain service-specific
UNKNOWN scopes. Unresolved destinations, JSON and overrides taint all queried
subjects. Known non-policy resources retain alternate-path uncertainty; they do
not prove execution authority. Literal outputs cannot independently grant access.
This is neither a universal Terraform interpreter nor a complete escalation finder.

Reports expose declaration IDs, source hashes/admission reasons, module binding
expressions, fixed synthetic substitutions, actual role-specific trusts, concrete
resource bindings, applicable UNKNOWN records and graph prerequisite/statement
traces. Account/region/provider IDs remain explicit synthetic stand-ins, not live
facts. Routing uses the declared ALB identity rather than a permission allowlist.
Primitive permissions on hypothetical managed-policy/Lambda/ECR/object ARNs are
separately identified as policy-scope evidence, not existence or execution proof.

`test_v3.py` exercises R1–R6 using the production evaluator, source discovery,
resolver and graph. Mutations change disposable source files and deliberately
refresh inventory (and, for trust/identity tests, workload pins). Closed-universe
mutations add a fourth route, unsupported source, changed hash and explicit Deny;
a structurally inert literal output does not invalidate unrelated coverage.
Operand/identity permutations test generalized admission, not only review examples.
The original F1–F5 tests remain, including dual escalation routes and anti-deny-all
controls. Earlier absent-key ARN fixtures now use valid ARNs; malformed operands
have independent UNKNOWN tests. Complete synthetic graph tests now obtain actual
source-bound certificates instead of supplying a label.

Supported policy semantics remain identity union, explicit deny precedence,
boundary intersection, exact role/session grants, service/OIDC trust, supported
String/ARN/Bool/Null conditions, set quantifiers and non-set IfExists. Unsupported
operators/delegation, unknown API context/dependencies and unresolved applicable
sources remain UNKNOWN or visible source-admission failure. Target runtime schemas
are closed structural contracts only; WP4 enforcement/API-model work is unchanged.

No Terraform, application, deployment, AWS or GitHub-settings behavior changes.
The offline guard remains credential-scrubbed, metadata-disabled, null credential
files, empty PATH and process/socket/dlopen audit denial. It is not a general sandbox.
Git Bash full selector remains FAILED/UNRESOLVED (cleanup); supported Linux remains
UNVALIDATED. No platform result is inferred from Windows execution.

V3 also binds layer wrapper inputs and both platform output hops to the actual
cluster declaration, and rejects colliding workload role identities. The stronger
task-role witness separately checks the existing task policy inputs/attachments.
A closed, literal-Effect jsonencode subset proves only that these task identity
policies contain no Deny; it does not establish their resource grants. A changed
Deny, unsnapshotted policy or unresolved attachment preserves the primitive policy
mutation witness but makes the stronger composed outcome UNKNOWN.


## V4 correction boundary (A1–A5)

V3 is `909637c8f57c533c374f455fa8c4695f8d4b1c3b`. V4 is one correction
commit on V3, preserving V1/V2 and the immutable spec/plan. Executor tests are
characterization evidence awaiting independent review, not WP1 acceptance.

The processing order is discovery, source applicability, kind-specific policy
admission, effective source/input binding, normalized request facts, primitive
permissions, existential graph witnesses, then negative completeness analysis.
Source adapters bind expressions before interpolating policy documents; the
primitive evaluator admits every supplied document before matching statements.
Neither binding nor completeness can upgrade failed semantic admission.

- **A1 — policy kinds.** Identity, resource, trust and permissions-boundary
  documents have separate closed grammars. The evaluator checks containers,
  explicit versions, every statement/operator/operand and trust principal/action
  compatibility. The supported explicit version is `2012-10-17`; an omitted
  version is supported only without policy variables. Statement singleton and
  list forms are equivalent. Empty policy lists represent a known empty set;
  empty documents, malformed containers and empty explicit conditions are
  rejected. `None` means no supplied boundary/trust, while an empty boundary list
  remains a restrictive known boundary. Bool/Null accept one policy value.
  Trust has no Resource, identity/boundary has no Principal. Unsupported valid
  constructs and malformed constructs both yield visible semantic UNKNOWN;
  neither supplies a primitive witness or a completeness certificate.
- **A2 — facts.** One request model derives principal category, ARN, role-session
  parent relationship, account, requested action/service and supported resource
  account. Case-insensitive global principal/resource context must confirm these
  facts. Contradictions cannot produce ALLOW or DENY. A session's ARN omits its
  parent's IAM path: full PrincipalArn conditions require a bound role ARN;
  account/name matching can still establish a role-principal grant. Service/OIDC
  identities cannot receive role aliases. Unknown account families and
  cross-account resource authorization remain unsupported. Identity-only checks
  remain policy-scope evidence, not complete API authorization.
- **A3 — effective inputs.** Explicit root/shared/layer input schemas classify
  supported resolved values, fixed expectations, unsupported applicable values
  and unrelated inputs. Supported literal GitHub owner/repository and storage
  overrides take effect before interpolation. OIDC creation, explicit reference
  and lookup modes are distinguished; a different issuer/account is unsupported.
  Environment/account/region changes outside fixed fixtures fail binding. Include
  merge controls and provider-generation changes cannot silently alter inherited
  inputs. Shared module admission is conservative: an unresolved security input
  invalidates that environment's shared model, rather than lazily admitting some
  of its policies. The runner evaluates environments separately. Workload and
  routing bindings remain independent of unrelated primitive policy scope.
- **A4 — applicability.** Discovery records support and applicability separately.
  Literal local module paths, including sibling/parent paths, and Terragrunt
  dependencies establish directory reachability, without evaluating Terraform.
  Uninvoked modules and sources exclusive to another environment do not poison
  unrelated witnesses. Invoked JSON/overrides and unclassified root sources
  remain applicable uncertainty. Inert uninvoked JSON outputs stay inert; an
  invoked override of an identity output is unresolved. Module sources into
  excluded cache directories or through symlinks/junctions are rejected. Narrow
  local string templates establish role-name disjointness; unresolved expressions
  are wildcards. A role disjoint from GitHub callers can still collide with a
  workload role and taint its trust/controls.
- **A5 — existential versus negative.** A current, admitted, grounded route proves
  WITNESS_ALLOW even beside an unsupported alternative route. A source that can
  alter that route's controls still makes it UNKNOWN. The closed fixture grammar
  distinguishes route-local policy sources, subject-scoped shared controls and
  unknown global controls. Shared controls are evaluated with every affected
  request. Completeness requires all primitives and source mechanisms to be
  admitted, and still binds source hashes, graph topology, subjects, mechanisms,
  route inventory and outcome. Freshness alone proves neither validity nor
  closure. Current repository outcomes remain PARTIAL and have no issuer.

Traces include document-kind admission, normalized facts, effective input/source
bindings, applicable uncertainty, statements, prerequisites and alternative
routes. Definitive negative fixture results also retain their certificate.
Structured reason codes distinguish WITNESS_ALLOW, EFFECTIVE_DENY,
UNKNOWN_APPLICABLE_CONTROL, UNKNOWN_INCOMPLETE_PATHS, SOURCE_BINDING_UNKNOWN and
SEMANTIC_ADMISSION_UNKNOWN. The high-risk approval witness has the same primitive
provenance. Declared roles/services/listeners use explicit synthetic account,
region and provider IDs; managed-policy/Lambda/ECR/release-object permissions are
identified as policy scope where existence is not bound.

The V4 test modules exercise production source adapters, request evaluators and
source-backed graph fixtures. Mutations cover independent alternative retention,
ALLOW/UNKNOWN/DENY transitions, semantic and binding failures, invalid/stale
certificates, shared Deny/boundary controls and unrelated uncertainty. Earlier
F1–F5/R1–R6 tests are retained. Their trust-positive fixtures now use valid
kind-specific envelopes and compatible STS actions; malformed forms have separate
UNKNOWN regressions. Positive controls still reject deny-all/all-UNKNOWN engines.
The JSON report lists test IDs and per-module counts; generated reports remain
outside the repository.

Runtime contracts remain WP1 structural foundations; WP4 enforcement/API coverage
is not implemented. Governance remains EXTERNAL/UNVERIFIED. No AWS or GitHub
settings are accessed. Credential scrubbing, metadata disablement, null AWS files,
empty PATH and socket/process/dynamic-library guards are unchanged. This remains
an accidental-I/O guard, not a sandbox. Git Bash full selector remains
FAILED/UNRESOLVED (cleanup); supported Linux remains UNVALIDATED.

## V5 correction boundary (V4-01 through V4-05)

V5 is a correction on V4 `42bb3cc67c06200da70819d0d2883c5d58bd45bf`.
V1 through V4 and the approved specification/planning checkpoints are preserved.
This is executor characterization evidence awaiting independent review, not WP1
acceptance and not a claim that E1 is secure. The sections below supersede V4
where its admission, dependency selection or uncertainty rules were incomplete.

### Admission and authoritative facts

The evaluator separates three operations: policy Resource ARN admission,
componentwise condition ARN operand admission/comparison, and concrete request
resource normalization. A Resource pattern is not a condition pattern or a
concrete resource. Resource admission has a closed service/location subset;
prohibited service wildcards and unsupported resource families fail admission
for both Allow and Deny, including an invalid second list member. This is not a
universal service-specific ARN validator. AWS's
[Resource grammar](https://docs.aws.amazon.com/IAM/latest/UserGuide/reference_policies_elements_resource.html)
prohibits wildcards in the service component.

Every consumed condition key has an explicit registry classification:
`DERIVED_AUTHORITATIVE`, `SUPPORTED_CALLER_CONTEXT`,
`SUPPORTED_REQUEST_CONTEXT_WITH_VALIDATION`, or `UNSUPPORTED`. There is no
implicit arbitrary-key fallback. Current OIDC and IAM request keys and the
explicit synthetic operator-fixture key have distinct provenance. Unknown AWS
keys return semantic UNKNOWN even when the statement would otherwise not match.
Caller/request context remains a stated input to an offline policy-permission
fixture; it does not prove an externally observed token or API request.

Principal ARN/account/type and resource-account facts retain V4 reconciliation.
`aws:PrincipalIsAWSService` is derived as false for admitted IAM role/session
identities and true for a direct service principal. Web-identity and unbound
policy-scope requests do not invent that fact. A supplied conflicting value
cannot override a derived fact, and omission cannot erase a derivable value.
The limited distinction follows AWS's
[principal-service context contract](https://docs.aws.amazon.com/IAM/latest/UserGuide/reference_policies_condition-keys.html#condition-keys-principalisawsservice).

### Effective dependency selection and source applicability

The platform dependency supplying the bound workload service has an explicit
output-selection contract: path, enabled/skip controls, mock values, allowed
commands and merge controls are admitted together. CURRENT declared-resource
evidence permits the existing validate/plan-only mocks with output reads enabled
and the admitted real-output relationship. It does not execute Terragrunt, read
state, assert deployed outputs, or use plan mocks as runtime identities.
Effective mocks, disabled dependencies, expressions and unsupported selection
controls produce `UNSUPPORTED_OUTPUT_SELECTION`. They cannot retain an old
cluster/service ARN behind `BINDING_VALIDATED`. Independent task/execution role
identities and trust remain available when only the service relationship fails.
Selection mode, source hash, expressions and the failure reason are reported.
See the authoritative
[Terragrunt dependency controls](https://docs.terragrunt.com/reference/hcl/blocks/#dependency).

Discovery keeps module reachability separate from construct kind, security
relevance and consumer relationships. A reference-free, unused literal JSON
output in an invoked module can remain inert just as its native-HCL counterpart
does. JSON IAM, module inputs, overrides and consumed or unresolved output
relationships are not exempted by the literal-output rule. This is structural
recognition of a narrow inert subset, not a Terraform JSON evaluator.
Duplicate JSON keys, nonfinite numeric values and unresolved expressions cannot
receive the inert-output exemption.

### Witnesses, uncertainty and certificates

Closed-universe routes own their alternative policy inputs; shared controls are
separate sources. Once subject/resource ownership and route selectors are
admitted, an unadmitted alternative mechanism cannot become a global control
merely because mechanism admission failed. Its route stays UNKNOWN and negative
completeness is unavailable, while another grounded route can remain
`WITNESS_ALLOW`. A shared unknown control or an unknown prerequisite on the
actual witness still invalidates that witness. Unclassified sources and
contradictory ownership remain conservative uncertainty.

Structured traces expose separate `ADMISSION`, `IDENTITY_FACTS`,
`SOURCE_BINDING`, `APPLICABILITY`, `ROUTE_GROUNDING` and
`NEGATIVE_COMPLETENESS` dimensions. Policy kinds, Resource admission,
context-key classifications, normalized facts, dependency selection, applicable
unknown scopes, prerequisites and certificate identity remain inspectable.
A successful dimension cannot compensate for an unknown one. Positive grounding
does not require exhaustive alternatives; negative evidence does.

Certificate issuance requires supported primitive admission, reconciled facts,
bound source inputs and applicable-source closure independently of whether a
primitive returned Deny. The issuer still binds source content, subjects,
mechanisms, routes, graph topology, seeds and outcome, and rereads sources before
use. Unknown alternatives as well as unknown controls prevent issuance. Current
repository outcomes have no completeness issuer and remain PARTIAL.

### Validation and unchanged scope

V5 regression modules exercise the exact five independent-review failures and
fresh source-backed permutations. The integration matrix covers retained
alternatives, valid grant removal, new possible/admitted authority, shared
boundary uncertainty, malformed primitives, forged facts and stale certificates.
Historical tests are retained; synthetic condition keys are explicitly named and
OIDC fixture claims are provider-qualified without changing their test purpose.

The JSON execution report lists test IDs, per-module results and overlapping
evidence groups for ARN admission, facts, dependency binding, JSON applicability,
route uncertainty, certificates, historical regressions, baseline witnesses,
mutations, positive controls, runtime/governance contracts and hermetic guards.
Group counts are executed unittest methods, not individual subtest permutations;
missing, skipped or failed evidence is not reported as a passed group. Generated
reports stay outside the repository. Syntax checks compile source in memory
without creating repository bytecode.

The unchanged baseline findings remain bounded authority witnesses, not executed
exploits or downstream secret/KMS compromise. Runtime contracts remain structural
WP1 foundations; WP4 API-model/enforcement work is not included. Governance stays
EXTERNAL/UNVERIFIED. No live AWS, external GitHub/AWS settings or WP2-WP7 behavior
is part of this correction. Hermetic guards remain accidental-I/O protection,
not a malicious-code sandbox. Git Bash full selector remains
**FAILED / UNRESOLVED cleanup issue**; supported Linux remains **UNVALIDATED**.

## V6 correction boundary (V5-01–V5-03)

V6 corrects V5 `022523df2f064c20f812e1e6018068ed7a170ecc`; it does not
accept WP1 or implement WP2–WP7. Specification and planning remain immutable.
The earlier sections are historical where superseded below.

### Exact module-instance values

`instances.py` replaces the ambient scalar namespace for shared-root naming,
workload roles/trusts/services, cluster identity and routing identity. Each
instance carries its source directory, invocation identity, supplied argument
expressions, declared variables/defaults, locals and resolved-value evidence.
A child argument resolves in its parent instance; an omitted argument uses only
that child's admitted literal default. There is no fallback to a sibling, root
or IAM synthetic `var.*`/`local.*`. Resolution is lazy: an unsupported expression
only fails when a consumed binding needs it. The current graph can conservatively
invalidate its composed workload binding while independent acquisitions survive.

The intentionally small language admits consumed string variables, literal
strings, simple interpolation, exact variable/local references and string lists
needed by trust documents. Arbitrary functions, provider references, variable
validation blocks, unknown variable controls, cycles and template directives are
unsupported here. Workload role `count` is now unsupported instead of borrowing
the IAM instance's environment. General module expansion is not implemented.
Repeated invocations are distinct objects with distinct invocation identities;
the current repository witness still deliberately selects its declared blue
instance. It does not claim coverage of every module invocation.

Every synthetic substitution is explicitly `MODULE_INSTANCE_BOUND_FACT` in
`synthetic-context.json`, with exact source, declaration, expression and IAM
invocation identity. The adapter verifies those fields and keys its replacement
values by instance identity. No expression substitution is classified as
`GLOBAL_DETERMINISTIC_FACT`. Synthetic account/region values used to render ARNs
are explicitly taken from the admitted IAM fixture; they do not enter another
module's expression namespace or establish live/provider identity.

The V5 counterexample now resolves the child's omitted `env` to `prod`, so dev
PassRole no longer supports the delivery witness. Supplying `env = "dev"`
explicitly restores it. A child `local.aws_region` resolves its own declaration.
The unchanged repository's representative dev/prod witnesses remain available.

### Context-key audit and narrower admission

No current repository primitive requires SourceArn. V6 classifies it UNSUPPORTED,
including well-formed ARN values, omission in a policy that uses it, direct service
principals and assumed-role callers. Supplying SourceArn also invalidates an
otherwise unrelated request. No primitive or certificate can be based on it.
No service-forward-access or general AWS availability model is introduced.

| Keys | Syntax/type and provenance | Availability in the WP1 model |
| --- | --- | --- |
| PrincipalArn, PrincipalAccount, PrincipalType, PrincipalIsAWSService | Derived authoritative facts; supplied string/singleton values can only confirm normalized facts | Existing role/session/service derivation; unavailable facts remain UNKNOWN when used |
| ResourceAccount, S3 ResourceAccount | Derived encoded account, or explicit S3 source-bound fixture account; contradictions rejected | Supported resource normalization; S3 key only for S3 |
| SourceArn | UNSUPPORTED regardless of ARN syntax | REQUEST_KEY_AVAILABILITY_UNKNOWN; cannot supply evidence |
| SecureTransport | One `true`/`false` string; supplied offline transport assumption, not an observed AWS fact | Direct role/session or symbolic permission request only; service/OIDC supplied values rejected |
| PassedToService | One service-principal-shaped string; supplied request description | Only iam:PassRole for role/session or symbolic permission scope |
| PolicyARN | One concrete ARN; supplied attachment request description | Only iam:AttachRolePolicy for role/session or symbolic permission scope |
| S3 prefix | One string, including empty prefix; supplied request description | Only s3:ListBucket for role/session or symbolic permission scope |
| GitHub OIDC aud/sub | One nonempty string; supplied synthetic token claim | Exact GitHub provider principal and sts:AssumeRoleWithWebIdentity |
| fixture:k | Typed fixture strings/list; explicitly synthetic caller fact | Operator fixtures only; no AWS provenance asserted |

`CONTEXT_AVAILABILITY` records the rule for every registry key. The request
validator checks supplied values against principal/action availability; omission
retains supported missing-key semantics. Derived facts still require their own
normalization/reconciliation. Provenance records availability separately from
syntax/provenance classification. `REQUEST_HAS_AUTHORITATIVE_KEY` means the
request class can carry the described key, not that an external token/request was
observed. Unsupported keys and contradictions yield UNKNOWN before certificate
issuance; syntax alone never authorizes availability.

The historical ARN-operator fixture used SourceArn as a generic comparison
operand. It now uses the already-admitted `fixture:k` namespace, retaining its
wildcard, set, case and explicit-Deny assertions without asserting impossible AWS
context. No historical test was removed to conceal a regression.

### Narrow terminal-consumer classification

Discovery recognizes only exact-reference chains from an admitted literal JSON
output through local assignments. If every use terminates in unused locals, the
relationship is `TERMINAL_INERT`. A native-HCL equivalent remains inert as before.
Direct resource/data/module consumption is `SECURITY_RELEVANT_SINK`; transformed,
dynamic, cyclic, duplicate or unparsed consumers are `UNRESOLVED`. Both latter
classes preserve conservative applicability. JSON/override and security content
receive no broad exemption. Consumer invocations exclusive to another environment
are excluded from the selected environment's relationship analysis.

This is a small terminal-use proof, not general Terraform data-flow. Unknown
consumers may still conservatively affect multiple witnesses; an exact unused
local chain cannot globally suppress independent evidence merely by existing.

### Evidence and unchanged boundaries

V6 tests cover sibling and repeated instances, arguments/defaults, local collisions,
missing/unsupported symbols, the actual false repository witness, SourceArn Allow
and Deny/certificate cases, availability restrictions and inert/security/unresolved
consumer chains. The runner reports separate V6 evidence groups alongside all
historical, positive, mutation, runtime/governance and hermetic groups. Unsupported
alternatives still preserve an independently grounded witness; applicable controls
still invalidate it. Negative completeness still requires current source-bound
certificates and admitted primitives. Current repository coverage remains PARTIAL.

The process guard is unchanged: credentials/proxies scrubbed, metadata disabled,
AWS files redirected, PATH empty, socket/process/subprocess/dlopen execution denied.
No live AWS, external settings, Terraform execution or dependency installation is
part of validation. Git Bash full selector remains FAILED/UNRESOLVED cleanup;
supported Linux remains UNVALIDATED. Windows tests do not clear either gap.
