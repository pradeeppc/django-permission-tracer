"""Source-level summary of a permission class, shown on the dashboard."""

import builtins
import importlib
import inspect
import keyword
import re

_PATTERNS = {
    "checks_feature_flags": [
        r"\bfeature.*enabled",
        r"\bcheck.*feature",
        r"\bfeature.*flag",
        r"\bis.*enabled",
        r"\bfeature.*active",
    ],
    "checks_roles": [
        r"\bhas.*role",
        r"\bcheck.*role",
        r"\bis.*role",
        r"\brole.*permission",
        r"\buser.*role",
    ],
    "checks_permissions": [
        r"\bhas.*perm",
        r"\bcheck.*perm",
        r"\bpermission.*code",
        r"\bis.*permission",
    ],
    "checks_user": [
        r"request\.user",
        r"\buser\.id",
        r"\buser_id",
        r"\bcurrent_user",
    ],
    "checks_groups": [r"\bgroup"],
    "checks_authentication": [r"\bauthenticat"],
    "checks_action": [r"\baction\b"],
    "checks_method": [r"request\.method", r"\bmethod\s*(==|in)\b", r"\bsafe_methods\b"],
    "raises_exceptions": [r"\braise\s+\w+", r"permissiondenied", r"authenticationfailed"],
}
_CONDITION = re.compile(r"^\s*(if|elif|raise|assert|return)\b")
_BRANCH = re.compile(r"\b(if|elif|for|while|raise)\b")
_CALL = re.compile(r"\b([A-Za-z_]\w*)\s*\(")
_CLASS_NAME = re.compile(r"\b([A-Z][A-Za-z0-9_]{2,})\b")
_IGNORED_CALLS = set(dir(builtins)) | {"self", "super"}
_PERMISSION_METHODS = ("has_permission", "has_object_permission")


def import_class(dotted_path):
    module_path, _, class_name = dotted_path.rpartition(".")
    module = importlib.import_module(module_path)
    return getattr(module, class_name)


def _source(obj):
    try:
        return inspect.getsource(obj)
    except (OSError, TypeError):
        return None


def _own_methods(cls):
    """Permission methods implemented outside DRF itself."""
    for name in _PERMISSION_METHODS:
        method = getattr(cls, name, None)
        if method is not None and not method.__module__.startswith("rest_framework."):
            yield name, method


def summarize(permission_path):
    try:
        cls = import_class(permission_path)
    except (ImportError, AttributeError, ValueError) as exc:
        return {
            "error": f"Could not import permission class: {exc}",
            "permission_path": permission_path,
        }

    has_permission = getattr(cls, "has_permission", None)
    metadata = {
        "methods": [
            name
            for name, _ in inspect.getmembers(cls, inspect.isfunction)
            if not name.startswith("_")
        ],
        "is_builtin": cls.__module__.startswith(("rest_framework.", "django.")),
    }
    try:
        lines, line_number = inspect.getsourcelines(cls)
        metadata.update(
            file_path=inspect.getfile(cls),
            line_number=line_number,
            total_lines=len(lines),
        )
    except (OSError, TypeError):
        pass

    return {
        "class_name": cls.__name__,
        "module_path": cls.__module__,
        "full_path": permission_path,
        "source_code": _source(cls),
        "docstring": inspect.getdoc(cls) or "",
        "has_permission": {
            "docstring": (inspect.getdoc(has_permission) or "") if has_permission else "",
            "source_code": _source(has_permission) if has_permission else None,
        },
        "logic_summary": _logic_summary(cls),
        "metadata": metadata,
    }


def _logic_summary(cls):
    source = "\n".join(filter(None, (_source(m) for _, m in _own_methods(cls))))
    lowered = source.lower()
    summary = {
        key: any(re.search(p, lowered) for p in patterns) for key, patterns in _PATTERNS.items()
    }

    calls = {
        name
        for name in _CALL.findall(source)
        if name not in _IGNORED_CALLS
        and not keyword.iskeyword(name)
        and name not in _PERMISSION_METHODS
    }
    summary.update(
        conditions=[line.strip()[:100] for line in source.splitlines() if _CONDITION.match(line)][
            :10
        ],
        complexity_score=len(_BRANCH.findall(source)),
        methods_called=sorted(calls)[:15],
        imports=sorted(set(_CLASS_NAME.findall(source)) - {"True", "False", "None"})[:10],
        base_classes=[
            {
                "name": base.__name__,
                "module": base.__module__,
                "full_path": f"{base.__module__}.{base.__qualname__}",
            }
            for base in cls.__mro__[1:]
            if base is not object
        ][:4],
        class_attributes={
            name: {"value": str(value)[:200], "type": type(value).__name__}
            for name, value in vars(cls).items()
            if not name.startswith("_")
            and isinstance(value, (str, int, float, bool, list, tuple, dict))
        },
        method_signatures={
            name: {
                "parameters": [str(p) for p in inspect.signature(method).parameters.values()],
                "docstring": inspect.getdoc(method) or "",
            }
            for name, method in _own_methods(cls)
        },
    )
    return summary
