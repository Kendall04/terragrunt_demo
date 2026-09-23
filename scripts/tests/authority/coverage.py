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
from evaluator import evaluate, Decision, Unsupported
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
        routes = []
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
                else:
                    raise Unsupported("unmodeled fixture source")
            except (Unsupported, ValueError, TypeError) as exc:
                self.unknown.append({"source": rel, "reason": str(exc)})
            self.sources[rel] = hashlib.sha256(raw.encode()).hexdigest()
        seen = set()
        for rel, route in routes:
            try:
                if not isinstance(route, dict) or set(route) != {"id", "mechanism", "target", "prerequisites", "subjects", "request", "policies"}:
                    raise Unsupported("unmodeled route shape")
                if route["id"] in seen or not isinstance(route["id"], str):
                    raise Unsupported("ambiguous route identity")
                seen.add(route["id"])
                if route["mechanism"] not in self.mechanisms or route["target"] not in self.outcomes or not set(route["subjects"]) <= set(self.subjects):
                    raise Unsupported("unadmitted mechanism/subject/outcome")
                if not isinstance(route["prerequisites"], list) or not set(route["prerequisites"]) <= set(self.seeds + self.outcomes):
                    raise Unsupported("unadmitted prerequisite")
                policies = route["policies"]
                if not isinstance(policies, dict) or set(policies) - {"identities", "boundary", "resources", "trust"}:
                    raise Unsupported("unmodeled policy inputs")
                result = evaluate(route["request"], **policies)
                if result.decision == Decision.UNKNOWN:
                    self.unknown.append({"source": rel, "reason": "Unadmitted primitive: " + str(result.reasons)})
                self.rules.append(Rule(route["target"], tuple(route["prerequisites"]), (result,),
                                       route["id"], route["mechanism"]))
            except (Unsupported, ValueError, TypeError, KeyError) as exc:
                self.unknown.append({"source": rel, "reason": str(exc)})
        if not self.subjects or not self.mechanisms or not self.outcomes:
            self.unknown.append({"source": "universe.json", "reason": "Missing universe declaration"})
        self.snapshot = fingerprint({"sources": self.sources, "unknown": self.unknown,
                                     "subjects": self.subjects, "mechanisms": self.mechanisms})

    def certificate(self, outcome):
        if self.unknown or outcome not in self.outcomes:
            raise Unsupported("Completeness unavailable: applicable UNKNOWN or undeclared outcome")
        return Certificate(self.snapshot, graph_fingerprint(self.seeds, self.rules), outcome,
                           tuple(self.subjects), tuple(self.mechanisms), tuple(r.meaning for r in self.rules))

    def current(self, seeds, rules):
        fresh = ClosedUniverse(self.directory)
        return (not fresh.unknown and fresh.snapshot == self.snapshot and
                graph_fingerprint(seeds, rules) == graph_fingerprint(fresh.seeds, fresh.rules))

    def validates(self, certificate, outcome, seeds, rules):
        return (isinstance(certificate, Certificate) and self.current(seeds, rules) and
                certificate == self.certificate(outcome))
