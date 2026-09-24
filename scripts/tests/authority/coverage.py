"""Source-bound completeness for closed synthetic universes only.

The current repository graph has no completeness issuer. A fixture owns its
entire grammar/directory: every JSON route is a policy-evaluated alternative;
every other executable/configuration source is UNKNOWN. This is not a claim
that an AWS account's authority mechanisms have been exhaustively modeled.
"""
from dataclasses import dataclass, asdict
from pathlib import Path
import hashlib
import json
from evaluator import evaluate, request_identity, Decision, Result, Unsupported
from contracts import load_json


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()


def graph_fingerprint(seeds, rules):
    return fingerprint({"seeds": sorted(seeds), "rules": [asdict(r) for r in rules]})


@dataclass(frozen=True)
class Certificate:
    snapshot: str
    graph: str
    outcome: str
    subjects: tuple
    mechanisms: tuple
    path_families: tuple


class ClosedUniverse:
    def __init__(self, directory):
        from graph import Rule
        self.directory = Path(directory)
        self.unknown, self.sources, self.rules = [], {}, []
        self.non_applicable = []
        self.seeds, self.subjects, self.mechanisms, self.outcomes = [], [], [], []
        self.subject_bindings, self.identity_subject_sets = {}, {}
        routes, controls = [], []
        for path in sorted(self.directory.rglob("*")):
            if not path.is_file():
                continue
            rel = path.relative_to(self.directory).as_posix()
            raw = path.read_text()
            try:
                if path.is_symlink() or path.suffix != ".json":
                    raise Unsupported("unrecognized source mechanism")
                doc = load_json(raw)
                if not isinstance(doc, dict):
                    raise Unsupported("invalid fixture source")
                if set(doc) == {"kind", "value"} and doc["kind"] == "LITERAL_OUTPUT" and isinstance(doc["value"], str):
                    self.non_applicable.append({"source": rel, "reason": "Closed fixture grammar: literal output cannot define a route, subject or grant"})
                    continue
                if rel == "universe.json" and set(doc) == {"kind", "seeds", "subjects", "mechanisms", "outcomes"} and doc["kind"] == "CLOSED_SYNTHETIC_UNIVERSE":
                    for field in ("seeds", "subjects", "mechanisms", "outcomes"):
                        values = doc[field]
                        if not isinstance(values, list) or not values or any(not isinstance(x, str) or not x for x in values) or len(values) != len(set(values)):
                            raise Unsupported("invalid universe identities")
                        setattr(self, field, values)
                elif set(doc) == {"routes"} and isinstance(doc["routes"], list):
                    routes.extend((rel, r) for r in doc["routes"])
                elif set(doc) == {"controls"} and isinstance(doc["controls"], list):
                    controls.extend((rel, c) for c in doc["controls"])
                else:
                    raise Unsupported("unmodeled fixture source")
            except (Unsupported, ValueError, TypeError) as exc:
                self.unknown.append({"source": rel, "reason": str(exc), "scope": "GLOBAL_CONTROL"})
            self.sources[rel] = hashlib.sha256(raw.encode()).hexdigest()
        # The fixture grammar gives a route exclusive ownership of its policy
        # inputs. Shared controls must be separate sources with explicit subjects;
        # they are merged into every affected request before policy evaluation.
        admitted_controls = []
        control_ids = set()
        for rel, control in controls:
            try:
                if not isinstance(control, dict) or set(control) != {"id", "subjects", "policies"}:
                    raise Unsupported("unmodeled control shape")
                if not isinstance(control["id"], str) or not control["id"] or control["id"] in control_ids:
                    raise Unsupported("ambiguous control identity")
                control_ids.add(control["id"])
                self.subject_set(control["subjects"])
                # Selector admission is separate from semantic admission. A bad
                # policy cannot erase an independently admitted subject selector
                # and become a global control over unrelated callers.
                admitted_controls.append((rel, control))
            except (Unsupported, ValueError, TypeError, KeyError) as exc:
                self.unknown.append({"source": rel, "reason": str(exc), "scope": "GLOBAL_CONTROL"})
        seen, consumed_controls = set(), set()
        for rel, route in routes:
            try:
                if not isinstance(route, dict) or set(route) != {"id", "mechanism", "target", "prerequisites", "subjects", "request", "policies"}:
                    raise Unsupported("unmodeled route shape")
                if not isinstance(route["id"], str) or not route["id"] or route["id"] in seen:
                    raise Unsupported("ambiguous route identity")
                seen.add(route["id"])
                self.subject_set(route["subjects"])
                subject_binding = self.bind_subjects(route["subjects"], route["request"])
                if route["mechanism"] not in self.mechanisms or route["target"] not in self.outcomes:
                    raise Unsupported("unadmitted mechanism/subject/outcome")
                if not isinstance(route["prerequisites"], list) or not set(route["prerequisites"]) <= set(self.seeds + self.outcomes):
                    raise Unsupported("unadmitted prerequisite")
                applicable = [(p, c) for p, c in admitted_controls if set(c["subjects"]) & set(route["subjects"])]
                consumed_controls.update(c["id"] for _, c in applicable)
                try:
                    self.policy_inputs(route["policies"])
                    policies = dict(route["policies"])
                    for _, control in applicable:
                        self.policy_inputs(control["policies"])
                        for kind, docs in control["policies"].items():
                            if kind in policies:
                                if kind not in ("identities", "resources") or not isinstance(policies[kind], list) or not isinstance(docs, list):
                                    raise Unsupported("unsupported shared control intersection")
                                policies[kind] = policies[kind] + docs
                            else:
                                policies[kind] = docs
                    result = evaluate(route["request"], **policies)
                except (Unsupported, ValueError, TypeError, KeyError) as exc:
                    result = Result(Decision.UNKNOWN, ("SEMANTIC_ADMISSION_UNKNOWN " + str(exc),))
                if applicable and result.decision == Decision.UNKNOWN:
                    result = Result(Decision.UNKNOWN, ("UNKNOWN_APPLICABLE_CONTROL",) + result.reasons, result.provenance)
                provenance = {"source": rel, "source_hash": self.sources[rel], "route": route["id"],
                              "subjects": route["subjects"], "subject_binding": subject_binding,
                              "controls": [{"source": p, "id": c["id"],
                              "source_hash": self.sources[p]} for p, c in applicable]}
                result = Result(result.decision, result.reasons, result.provenance + (provenance,))
                if result.decision == Decision.UNKNOWN:
                    self.unknown.append({"source": rel, "route": route["id"], "target": route["target"],
                                         "subjects": route["subjects"], "scope": "ROUTE_CONTROL" if applicable else "ALTERNATIVE_ROUTE",
                                         "reason": "Unadmitted primitive: " + str(result.reasons)})
                self.rules.append(Rule(route["target"], tuple(route["prerequisites"]), (result,),
                                       route["id"], route["mechanism"]))
            except (Unsupported, ValueError, TypeError, KeyError) as exc:
                self.unknown.append({"source": rel, "reason": str(exc), "scope": "GLOBAL_CONTROL"})
        # A control with no consumer cannot certify its unsupported policy away.
        # It need not erase unrelated positive routes, but closure is not proven.
        for rel, control in admitted_controls:
            if control["id"] not in consumed_controls:
                self.unknown.append({"source": rel, "scope": "UNCONSUMED_CONTROL",
                                     "reason": "Control has no admitted request against which to establish semantic closure"})
        if not self.subjects or not self.mechanisms or not self.outcomes:
            self.unknown.append({"source": "universe.json", "reason": "Missing universe declaration", "scope": "GLOBAL_CONTROL"})
        self.snapshot = fingerprint({"sources": self.sources, "unknown": self.unknown,
                                     "subjects": self.subjects, "subject_bindings": self.subject_bindings,
                                     "mechanisms": self.mechanisms})

    def subject_set(self, values):
        if (not isinstance(values, list) or not values or any(not isinstance(x, str) for x in values) or
                len(set(values)) != len(values) or not set(values) <= set(self.subjects)):
            raise Unsupported("unadmitted subject set")

    def bind_subjects(self, subjects, request):
        """A fixture label cannot split or merge a normalized physical caller.

        IAM role/session paths share account-unique role names, so a second STS
        session is not a new subject able to evade a role's shared controls.
        Requests without a principal remain explicitly symbolic policy-scope
        fixtures; their labels cannot also stand for real IAM identities.
        """
        if not isinstance(request, dict):
            raise Unsupported("SOURCE_BINDING_UNKNOWN invalid subject request")
        labels = frozenset(subjects)
        if "principal" in request or "role_arn" in request:
            identity = request_identity(request)
            canonical = (("role", identity.account, identity.role_name.lower())
                         if identity.category in ("role", "session") else
                         (identity.category, identity.principal))
            kind = "NORMALIZED_PRINCIPAL"
        else:
            canonical = ("symbolic_policy_scope", *sorted(subjects))
            kind = "SYMBOLIC_FIXTURE_ONLY"
        if canonical in self.identity_subject_sets and self.identity_subject_sets[canonical] != labels:
            raise Unsupported("SOURCE_BINDING_UNKNOWN physical principal has conflicting subject aliases")
        if any(label in self.subject_bindings and self.subject_bindings[label] != canonical for label in labels):
            raise Unsupported("SOURCE_BINDING_UNKNOWN subject label has conflicting physical/symbolic identities")
        self.identity_subject_sets[canonical] = labels
        self.subject_bindings.update({label: canonical for label in labels})
        return {"kind": kind, "canonical_identity": list(canonical), "subjects": sorted(labels)}

    @staticmethod
    def policy_inputs(value):
        if not isinstance(value, dict) or set(value) - {"identities", "boundary", "resources", "trust"}:
            raise Unsupported("unmodeled policy inputs")

    def positive_taints(self):
        """Route-local semantic failure is already represented on that rule.

        An unclassified source can alter any route's controls and taints all
        witnesses. A malformed alternative route cannot invent such a control
        in this closed fixture language. Repository sources have no such promise.
        """
        return [x for x in self.unknown if x["scope"] == "GLOBAL_CONTROL"]

    def certificate(self, outcome):
        if self.unknown or outcome not in self.outcomes:
            raise Unsupported("Completeness unavailable: applicable UNKNOWN or undeclared outcome")
        return Certificate(self.snapshot, graph_fingerprint(self.seeds, self.rules), outcome,
                           tuple(self.subjects), tuple(self.mechanisms), tuple(r.meaning for r in self.rules))

    def current(self, seeds, rules):
        fresh = ClosedUniverse(self.directory)
        # Freshness says nothing about closure or policy validity. Conflating
        # these erased valid independent positive paths in V3.
        return (fresh.snapshot == self.snapshot and
                graph_fingerprint(seeds, rules) == graph_fingerprint(fresh.seeds, fresh.rules))

    def validates(self, certificate, outcome, seeds, rules):
        return (not self.unknown and isinstance(certificate, Certificate) and self.current(seeds, rules) and
                certificate == self.certificate(outcome))
