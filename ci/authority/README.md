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
supported IfExists and absent keys. Session grants bypass implicit identity and
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

No AC1–AC16 is fully accepted by this package. External configuration remains
unverified, and no WP2–WP7 resources or behavioral changes are included.
