"""Literal/reference-only values owned by one explicit Terraform module instance.

No ambient namespace, provider execution, general expressions or implicit inputs.
Only values demanded by a security binding are resolved.
"""
import json
import re
from evaluator import Unsupported


class ModuleInstance:
    def __init__(self, bindings, directory, identity, supplied, parent=None):
        from source import attributes, blocks
        self.directory, self.identity = directory, identity
        self.supplied, self.parent = dict(supplied), parent
        self.variables, self.locals, self.active = {}, {}, set()
        self.evidence = {"instance": identity, "directory": directory,
                         "classification": "MODULE_INSTANCE_BOUND_FACT",
                         "supplied_arguments": dict(supplied), "resolved": []}
        bindings.evidence.append(self.evidence)
        for kind, name, _, body, path in bindings.declarations(directory):
            if kind == "variable":
                nested, rest = blocks(body)
                self.variables[name] = (attributes(rest), bool(nested), path)
            elif kind == "locals":
                values = attributes(body)
                if set(values) & set(self.locals):
                    raise Unsupported("SOURCE_BINDING_FAILURE duplicate instance local")
                self.locals.update({key: (expr, path) for key, expr in values.items()})

    def value(self, expression):
        from source import split_top
        expression = expression.strip()
        reference = re.fullmatch(r"(var|local)\.(\w+)", expression)
        if reference:
            if expression in self.active:
                raise Unsupported("SOURCE_BINDING_FAILURE cyclic instance reference")
            self.active.add(expression)
            try:
                kind, name = reference.groups()
                if kind == "local":
                    if name not in self.locals:
                        raise Unsupported("SOURCE_BINDING_FAILURE undeclared instance local " + expression)
                    expr, path = self.locals[name]
                    value, origin = self.value(expr), "LOCAL_DECLARATION"
                else:
                    if name not in self.variables:
                        raise Unsupported("SOURCE_BINDING_FAILURE undeclared instance variable " + expression)
                    attrs, nested, path = self.variables[name]
                    if nested or attrs.get("type") != "string" or set(attrs) - {"type", "default", "description", "nullable", "sensitive"}:
                        raise Unsupported("SOURCE_BINDING_FAILURE unsupported consumed variable declaration " + expression)
                    if name in self.supplied:
                        expr = self.supplied[name]
                        value = self.parent.value(expr) if self.parent else self.literal(expr)
                        origin = "INVOCATION_ARGUMENT"
                    elif "default" in attrs:
                        expr = attrs["default"]
                        value, origin = self.literal(expr), "VARIABLE_DEFAULT"
                    else:
                        raise Unsupported("SOURCE_BINDING_FAILURE missing instance input " + expression)
                    if not isinstance(value, str):
                        raise Unsupported("SOURCE_BINDING_FAILURE non-string consumed input " + expression)
                self.evidence["resolved"].append({"symbol": expression, "source": path,
                    "expression": expr, "origin": origin, "value": value})
                return value
            finally:
                self.active.remove(expression)
        if expression.startswith('"'):
            text = json.loads(expression)
            if "%{" in text or "$${" in text:
                raise Unsupported("SOURCE_BINDING_FAILURE unsupported template escape/directive")
            value = re.sub(r"\$\{([^}]+)\}", lambda m: str(self.value(m[1])), text)
            if "${" in value:
                raise Unsupported("SOURCE_BINDING_FAILURE unresolved template")
            return value
        if expression.startswith("[") and expression.endswith("]"):
            return [self.value(x) for x in split_top(expression[1:-1])]
        raise Unsupported("SOURCE_BINDING_FAILURE unresolved instance expression " + expression[:100])

    @staticmethod
    def literal(expression):
        try:
            value = json.loads(expression)
        except (ValueError, TypeError):
            raise Unsupported("SOURCE_BINDING_FAILURE nonliteral instance input/default") from None
        if isinstance(value, str) and any(x in value for x in ("${", "%{")):
            raise Unsupported("SOURCE_BINDING_FAILURE unresolved instance input/default")
        return value

    def scalar(self, expression):
        value = self.value(expression)
        if not isinstance(value, str):
            raise Unsupported("SOURCE_BINDING_FAILURE non-scalar instance identity")
        return value
