"""
Static discovery of which permissions protect each endpoint.

Each DRF endpoint is instantiated the way the router would (same ``initkwargs``
and action map) and ``get_permissions()`` is called once per HTTP method, so
``@action`` overrides, ``get_permissions()`` overrides and composed permissions
are reported as they behave at request time.
"""

import inspect
import logging
import re
import threading
from typing import Any, Optional

from django.urls import URLPattern, URLResolver, get_resolver
from django.urls.resolvers import RegexPattern

from . import describe

try:
    from rest_framework.views import APIView
except ImportError:
    APIView = None

logger = logging.getLogger(__name__)

_IGNORED_METHODS = ("options", "head", "trace")
_ROUTE_PARAM = re.compile(r"<(?:[^>:]+:)?([^>]+)>")

_cache_lock = threading.Lock()
_cache = {"resolver": None, "result": None}


def clear_cache():
    with _cache_lock:
        _cache["resolver"] = None
        _cache["result"] = None


class PermissionAnalyzer:
    def __init__(self):
        self.endpoint_permissions = {}
        self.permission_endpoints = {}

    def analyze(self, use_cache: bool = True) -> dict[str, Any]:
        resolver = get_resolver()
        with _cache_lock:
            cached = _cache["result"] if use_cache and _cache["resolver"] is resolver else None
        if cached is None:
            cached = self._build(resolver)
            with _cache_lock:
                _cache["resolver"], _cache["result"] = resolver, cached
        self.endpoint_permissions = cached["endpoint_permissions"]
        self.permission_endpoints = cached["permission_endpoints"]
        return cached

    def _build(self, resolver):
        endpoints = {}
        for path, pattern in _walk(resolver.url_patterns):
            try:
                info = analyze_endpoint(path, pattern)
            except Exception:
                logger.warning("Could not analyze permissions for %s", path, exc_info=True)
                continue
            if info is not None:
                key = (
                    path if path not in endpoints else f"{path} [{pattern.name or len(endpoints)}]"
                )
                endpoints[key] = info

        by_permission = {}
        for info in endpoints.values():
            for perm in info["permissions"]:
                by_permission.setdefault(perm, []).append(
                    {
                        "path": info["path"],
                        "view_class": info["view_class"],
                        "methods": [
                            m for m, d in info["methods"].items() if perm in d["permissions"]
                        ],
                    }
                )

        return {
            "endpoint_permissions": endpoints,
            "permission_endpoints": by_permission,
            "total_endpoints": len(endpoints),
            "total_permissions": len(by_permission),
        }

    def find_permission_usage(self, permission_name: str) -> list[dict[str, Any]]:
        return self.permission_endpoints.get(permission_name, [])

    def find_endpoint_permissions(self, endpoint_path: str) -> list[str]:
        for info in self.endpoint_permissions.values():
            if info["path"] == endpoint_path:
                return info["permissions"]
        return []

    def unprotected_endpoints(self) -> list[dict[str, Any]]:
        """Endpoint methods that an anonymous user is let through."""
        return [
            {
                "path": info["path"],
                "method": method,
                "action": detail.get("action"),
                "view_class": info["view_class"],
                "expression": detail["expression"],
            }
            for info in self.endpoint_permissions.values()
            for method, detail in info["methods"].items()
            if detail.get("anonymous_allowed")
        ]

    def get_permission_graph(self) -> dict[str, Any]:
        nodes, edges = [], []
        permission_nodes = {}
        for perm_name, usages in self.permission_endpoints.items():
            node_id = f"perm_{len(permission_nodes)}"
            permission_nodes[perm_name] = node_id
            nodes.append(
                {
                    "id": node_id,
                    "label": perm_name.rsplit(".", 1)[-1],
                    "type": "permission",
                    "full_name": perm_name,
                    "edge_count": len(usages),
                }
            )

        edge_counts = {}
        for index, info in enumerate(self.endpoint_permissions.values()):
            node_id = f"endpoint_{index}"
            nodes.append(
                {
                    "id": node_id,
                    "label": info["path"],
                    "type": "endpoint",
                    "full_path": info["path"],
                }
            )
            for perm_name in info["permissions"]:
                edges.append({"from": permission_nodes[perm_name], "to": node_id})
                edge_counts[perm_name] = edge_counts.get(perm_name, 0) + 1

        return {
            "nodes": nodes,
            "edges": edges,
            "stats": {
                "total_permissions": len(permission_nodes),
                "total_endpoints": len(self.endpoint_permissions),
                "total_edges": len(edges),
                "permission_edge_counts": edge_counts,
            },
        }


def _walk(patterns, prefix=()):
    for pattern in patterns:
        if isinstance(pattern, URLResolver):
            if pattern.namespace == "permission_tracer":
                continue
            try:
                children = pattern.url_patterns
            except Exception:
                logger.warning("Could not load URL include %s", pattern, exc_info=True)
                continue
            yield from _walk(children, (*prefix, pattern.pattern))
        elif isinstance(pattern, URLPattern):
            parts = (*prefix, pattern.pattern)
            # Skip the ``.json``-style duplicates added by format_suffix_patterns.
            if any("format" in p.regex.groupindex for p in parts):
                continue
            yield "/" + "".join(_readable(p) for p in parts), pattern


def _readable(pattern):
    """Render a URL pattern as ``users/{pk}/``."""
    raw = str(pattern)
    if not isinstance(pattern, RegexPattern):
        return _ROUTE_PARAM.sub(r"{\1}", raw)

    raw = re.sub(r"(\$|\\Z)$", "", raw.removeprefix("^"))
    out, i = [], 0
    while i < len(raw):
        if raw.startswith("(?P<", i):
            name = raw[i + 4 : raw.index(">", i)]
            depth, i = 1, i + 1
            while i < len(raw) and depth:
                if raw[i] == "\\":
                    i += 2
                    continue
                depth += {"(": 1, ")": -1}.get(raw[i], 0)
                i += 1
            out.append("{" + name + "}")
        elif raw[i] == "\\" and i + 1 < len(raw):
            out.append(raw[i + 1])
            i += 2
        else:
            out.append(raw[i])
            i += 1
    return "".join(out).replace("/?", "/")


def analyze_endpoint(path: str, pattern: URLPattern) -> Optional[dict[str, Any]]:
    callback = pattern.callback
    view_class = getattr(callback, "cls", None) or getattr(callback, "view_class", None)
    if not inspect.isclass(view_class) or view_class.__module__.startswith("permission_tracer."):
        return None

    if APIView is not None and issubclass(view_class, APIView):
        framework = "drf"
        methods = _drf_methods(path, callback, view_class)
    else:
        framework = "django"
        methods = _django_methods(view_class)

    permissions = list(dict.fromkeys(p for d in methods.values() for p in d["permissions"]))
    expressions = {d["expression"] for d in methods.values()}

    return {
        "path": path,
        "name": pattern.name,
        "view_class": describe.dotted_name(view_class),
        "framework": framework,
        "methods": methods,
        "permissions": permissions,
        "expression": expressions.pop() if len(expressions) == 1 else "varies by method",
        "dynamic": framework == "drf" and view_class.get_permissions is not APIView.get_permissions,
    }


def _http_methods(view_class):
    return [
        m
        for m in view_class.http_method_names
        if m not in _IGNORED_METHODS and hasattr(view_class, m)
    ]


def _drf_methods(path, callback, view_class):
    actions = getattr(callback, "actions", None) or {}
    return {
        method.upper(): _drf_method_permissions(
            path, callback, view_class, method, actions.get(method)
        )
        for method in (actions or _http_methods(view_class))
    }


def _drf_method_permissions(path, callback, view_class, method, action):
    from django.contrib.auth.models import AnonymousUser
    from django.test import RequestFactory
    from rest_framework.request import Request

    view = view_class(**(getattr(callback, "initkwargs", None) or {}))
    view.args, view.kwargs, view.format_kwarg, view.headers = (), {}, None, {}
    if action is not None:
        view.action_map = callback.actions
        view.action = action

    django_request = RequestFactory().generic(
        method.upper(), path.replace("{", "").replace("}", "")
    )
    django_request.user = AnonymousUser()
    request = Request(django_request)
    request.user = AnonymousUser()
    view.request = request

    detail = {"action": action}
    try:
        perms = list(view.get_permissions())
        detail["resolved"] = "runtime"
    except Exception as exc:
        # get_permissions() needs request state we can't fake; report the declared classes.
        perms = [describe.instantiate(p) for p in getattr(view, "permission_classes", ())]
        detail["resolved"] = "static"
        detail["note"] = (
            f"get_permissions() raised {type(exc).__name__}; showing declared permission_classes"
        )

    described = [describe.describe(p) for p in perms]
    detail["permissions"] = [leaf for d in described for leaf in d["leaves"]]
    detail["expression"] = " & ".join(_term(d, len(described)) for d in described) or "(none)"
    detail["tree"] = [d["tree"] for d in described]
    detail["anonymous_allowed"] = _anonymous_allowed(perms, request, view)
    return detail


def _term(described, count):
    """Parenthesize ``A | B`` when it is one of several ANDed permission classes."""
    op = described["tree"].get("op")
    if count > 1 and op in ("AND", "OR"):
        return f"({described['expression']})"
    return described["expression"]


def _anonymous_allowed(perms, request, view):
    """Whether an anonymous request passes every permission; None if one raised."""
    try:
        return all(perm.has_permission(request, view) for perm in perms)
    except Exception:
        return None


def _django_methods(view_class):
    from django.contrib.auth.mixins import AccessMixin, PermissionRequiredMixin

    guards = [
        describe.dotted_name(cls)
        for cls in view_class.__mro__[1:]
        if issubclass(cls, AccessMixin)
        and cls is not AccessMixin
        and cls.__module__ == "django.contrib.auth.mixins"
    ]
    extra = {}
    if issubclass(view_class, PermissionRequiredMixin):
        required = getattr(view_class, "permission_required", None)
        extra["django_permissions"] = (
            [required] if isinstance(required, str) else list(required or [])
        )

    return {
        method.upper(): {
            "action": None,
            "permissions": guards,
            "expression": " & ".join(g.rsplit(".", 1)[-1] for g in guards) or "(none)",
            "resolved": "static",
            "anonymous_allowed": None,
            **extra,
        }
        for method in _http_methods(view_class)
    }
