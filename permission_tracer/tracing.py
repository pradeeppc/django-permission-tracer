"""
Runtime tracing of DRF permission checks.

``install()`` wraps ``APIView.check_permissions`` and
``APIView.check_object_permissions`` once, at startup. The wrappers do the same
thing DRF does, but also record every permission's result on the trace of the
current request, which lives in a contextvar (so it is safe under threads and
async). Outside a traced request they call straight through to DRF.
"""

import contextvars

from . import describe

_current = contextvars.ContextVar("permission_tracer_trace", default=None)
_INSTALLED_FLAG = "_permission_tracer_wrapped"


def start(trace):
    return _current.set(trace)


def stop(token):
    _current.reset(token)


def current():
    return _current.get()


def is_installed():
    try:
        from rest_framework.views import APIView
    except ImportError:
        return False
    return getattr(APIView.check_permissions, _INSTALLED_FLAG, False)


def install():
    try:
        from rest_framework.views import APIView
    except ImportError:
        return False
    if is_installed():
        return True

    original_check = APIView.check_permissions
    original_object_check = APIView.check_object_permissions

    def check_permissions(self, request):
        trace = _current.get()
        if trace is None:
            return original_check(self, request)
        _record_view(trace, self, request)
        for permission in self.get_permissions():
            _check(trace, self, permission, "has_permission", request, self)

    def check_object_permissions(self, request, obj):
        trace = _current.get()
        if trace is None:
            return original_object_check(self, request, obj)
        _record_view(trace, self, request)
        for permission in self.get_permissions():
            _check(trace, self, permission, "has_object_permission", request, self, obj)

    for fn in (check_permissions, check_object_permissions):
        setattr(fn, _INSTALLED_FLAG, True)
    check_permissions.__wrapped__ = original_check
    check_object_permissions.__wrapped__ = original_object_check
    APIView.check_permissions = check_permissions
    APIView.check_object_permissions = check_object_permissions
    return True


def _record_view(trace, view, request):
    if trace.get("view_class") is None:
        trace["view_class"] = {
            "name": type(view).__name__,
            "module": type(view).__module__,
            "full_path": describe.dotted_name(view),
        }
        trace["action"] = getattr(view, "action", None)
        user = getattr(request, "user", None)
        authenticator = getattr(request, "successful_authenticator", None)
        trace["user"] = {
            "repr": str(user)[:100] if user is not None else None,
            "authenticated": bool(getattr(user, "is_authenticated", False)),
            "authenticator": type(authenticator).__name__ if authenticator else None,
        }


def _check(trace, view, permission, method_name, request, *args):
    info = describe.describe(permission)
    obj = args[1] if method_name == "has_object_permission" else None
    entry = {
        "permission": describe.dotted_name(permission),
        "expression": info["expression"],
        "leaves": info["leaves"],
        "level": "object" if obj is not None else "view",
        "object": _object_label(obj) if obj is not None else None,
        "allowed": None,
        "error": None,
    }
    trace["checks"].append(entry)
    _add_checked(trace, info["leaves"])
    composed = bool(describe.operands(permission))

    try:
        allowed = bool(getattr(permission, method_name)(request, *args))
    except Exception as exc:
        entry["allowed"] = False
        entry["error"] = f"{type(exc).__name__}: {exc}"
        _set_result(trace, info["leaves"], False)
        _record_denial(trace, entry, exc)
        raise

    entry["allowed"] = allowed
    if not composed:
        _set_result(trace, info["leaves"], allowed)
    if allowed:
        return

    if composed:
        entry["breakdown"] = _explain(permission, method_name, (request, *args))
        for leaf, ok in _flatten(entry["breakdown"]):
            _set_result(trace, [leaf], ok)
    try:
        view.permission_denied(
            request,
            message=getattr(permission, "message", None),
            code=getattr(permission, "code", None),
        )
    except Exception as exc:
        _record_denial(trace, entry, exc)
        raise


def _explain(permission, method_name, args):
    """Evaluate each operand of a composed permission so a denial can be explained."""
    children = describe.operands(permission)
    if not children:
        node = {"name": describe.dotted_name(permission)}
        try:
            node["allowed"] = bool(getattr(permission, method_name)(*args))
        except Exception as exc:
            node["allowed"] = False
            node["error"] = f"{type(exc).__name__}: {exc}"
        return node
    node = {
        "op": type(permission).__name__,
        "operands": [_explain(child, method_name, args) for child in children],
    }
    results = [c["allowed"] for c in node["operands"]]
    node["allowed"] = {"AND": all, "OR": any}.get(node["op"], lambda r: not r[0])(results)
    return node


def _flatten(node):
    if "name" in node:
        yield node["name"], node["allowed"]
    else:
        for child in node["operands"]:
            yield from _flatten(child)


def _add_checked(trace, leaves):
    for leaf in leaves:
        if leaf not in trace["permissions_checked"]:
            trace["permissions_checked"].append(leaf)


def _set_result(trace, leaves, allowed):
    for leaf in leaves:
        # A permission that failed once in a request stays failed.
        previous = trace["permission_results"].get(leaf)
        if previous is None or previous["allowed"]:
            trace["permission_results"][leaf] = {"allowed": allowed}


def _record_denial(trace, entry, exc):
    if trace.get("denied_by") is None:
        trace["denied_by"] = {
            "permission": entry["permission"],
            "expression": entry["expression"],
            "level": entry["level"],
            "exception": type(exc).__name__,
            "detail": str(getattr(exc, "detail", exc))[:500],
        }


def _object_label(obj):
    pk = getattr(obj, "pk", None)
    return f"{type(obj).__name__}(pk={pk})" if pk is not None else type(obj).__name__
