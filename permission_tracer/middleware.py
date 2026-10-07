"""Records which permissions were checked on each request, and which one denied it."""

import time
import uuid

from django.core.exceptions import MiddlewareNotUsed
from django.urls import NoReverseMatch, reverse

from . import conf, storage, tracing


def is_tracer_path(path):
    try:
        prefix = reverse("permission_tracer:index")
    except NoReverseMatch:
        return False
    return path.startswith(prefix)


def tracer_exempt(middleware_class):
    """
    Wrap a middleware class so it lets the tracer's own URLs through while the tracer
    is enabled, and behaves exactly as before for every other request.

    For projects whose authentication middleware rejects any request without a
    token, which would otherwise block the dashboard in a browser.
    """

    def exempt(request):
        return conf.get("ENABLED") and is_tracer_path(request.path)

    def call(self, request):
        if exempt(request):
            return self.get_response(request)
        return middleware_class.__call__(self, request)

    namespace = {"__call__": call, "__doc__": middleware_class.__doc__}
    for hook in ("process_view", "process_exception", "process_template_response"):
        original = getattr(middleware_class, hook, None)
        if original is not None:
            namespace[hook] = _skip_for_tracer(original, exempt, hook)

    return type(f"TracerExempt{middleware_class.__name__}", (middleware_class,), namespace)


def _skip_for_tracer(original, exempt, hook):
    def wrapper(self, request, *args, **kwargs):
        if exempt(request):
            # process_template_response must hand the response back.
            return args[0] if hook == "process_template_response" else None
        return original(self, request, *args, **kwargs)

    wrapper.__name__ = hook
    return wrapper


class PermissionTracerMiddleware:
    def __init__(self, get_response):
        if not conf.get("ENABLED"):
            raise MiddlewareNotUsed
        self.get_response = get_response
        tracing.install()

    def __call__(self, request):
        if self._excluded(request.path):
            return self.get_response(request)

        trace = {
            "id": uuid.uuid4().hex,
            "path": request.path,
            "method": request.method,
            "timestamp": time.time(),
            "view_class": None,
            "action": None,
            "user": None,
            "checks": [],
            "permissions_checked": [],
            "permission_results": {},
            "denied_by": None,
        }
        token = tracing.start(trace)
        try:
            response = self.get_response(request)
        finally:
            tracing.stop(token)

        if getattr(request, "resolver_match", None) is None:
            return response
        trace["status_code"] = response.status_code
        trace["duration"] = time.time() - trace["timestamp"]
        if trace["view_class"] is None:
            func = request.resolver_match.func
            view_class = getattr(func, "cls", None) or getattr(func, "view_class", None)
            if view_class is not None:
                trace["view_class"] = {
                    "name": view_class.__name__,
                    "module": view_class.__module__,
                    "full_path": f"{view_class.__module__}.{view_class.__qualname__}",
                }
        detail = getattr(response, "data", None)
        if response.status_code >= 400 and isinstance(detail, dict) and "detail" in detail:
            trace["response_detail"] = str(detail["detail"])[:500]
        storage.get_store().add(trace)
        return response

    def _excluded(self, path):
        return is_tracer_path(path) or any(path.startswith(p) for p in conf.get("EXCLUDE_PATHS"))
