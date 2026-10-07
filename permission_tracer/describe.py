"""Describe DRF permissions (classes, instances or ``A | B & ~C`` expressions) as JSON."""

import inspect

_OPERATORS = {"AND": "&", "OR": "|"}


def dotted_name(obj):
    cls = obj if inspect.isclass(obj) else type(obj)
    return f"{cls.__module__}.{cls.__qualname__}"


def instantiate(perm):
    """Classes and OperandHolders become instances; instances pass through."""
    if isinstance(perm, str):
        return perm
    if inspect.isclass(perm) or _is_operand_holder(perm):
        try:
            return perm()
        except Exception:
            return perm
    return perm


def _is_operand_holder(obj):
    try:
        from rest_framework.permissions import OperationHolderMixin
    except ImportError:
        return False
    return isinstance(obj, OperationHolderMixin) and not inspect.isclass(obj)


def _operator(perm):
    name = type(perm).__name__
    if type(perm).__module__ != "rest_framework.permissions":
        return None
    if name in _OPERATORS and hasattr(perm, "op2"):
        return name
    if name == "NOT" and hasattr(perm, "op1"):
        return "NOT"
    return None


def operands(perm):
    op = _operator(perm)
    if op == "NOT":
        return [perm.op1]
    if op:
        return [perm.op1, perm.op2]
    return []


def tree(perm):
    perm = instantiate(perm)
    if isinstance(perm, str):
        return {"name": perm}
    op = _operator(perm)
    if op:
        return {"op": op, "operands": [tree(p) for p in operands(perm)]}
    return {"name": dotted_name(perm)}


def expression(node, top=True):
    if "name" in node:
        return node["name"].rsplit(".", 1)[-1]
    if node["op"] == "NOT":
        return "~" + expression(node["operands"][0], top=False)
    joined = f" {_OPERATORS[node['op']]} ".join(expression(n, top=False) for n in node["operands"])
    return joined if top else f"({joined})"


def leaves(node):
    if "name" in node:
        return [node["name"]]
    return [name for child in node["operands"] for name in leaves(child)]


def describe(perm):
    node = tree(perm)
    return {"tree": node, "expression": expression(node), "leaves": leaves(node)}
