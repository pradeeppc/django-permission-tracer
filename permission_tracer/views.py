"""
Dashboard and JSON API.

Every view returns 404 unless the tracer is enabled, and checks
``PERMISSION_TRACER["ACCESS_CHECK"]`` (staff only by default), because the API
exposes permission source code and request traces.
"""

import logging
from urllib.parse import unquote

from django.contrib.auth.views import redirect_to_login
from django.http import Http404, HttpResponseForbidden, JsonResponse
from django.shortcuts import render
from django.urls import reverse
from django.views import View

from . import conf, inspection, storage, tracing
from .analyzer import PermissionAnalyzer

logger = logging.getLogger(__name__)


def _error(message, status):
    return JsonResponse({"status": "error", "message": message}, status=status)


def _success(data, **extra):
    return JsonResponse({"status": "success", "data": data, **extra})


class TracerAccessMixin:
    def dispatch(self, request, *args, **kwargs):
        if not conf.get("ENABLED"):
            raise Http404
        if not conf.has_access(request):
            return self.handle_no_access(request)
        try:
            return super().dispatch(request, *args, **kwargs)
        except Http404:
            raise
        except Exception:
            logger.exception("Permission Tracer view %s failed", type(self).__name__)
            return _error("Internal error; see server logs.", status=500)

    def handle_no_access(self, request):
        return _error("Permission Tracer is restricted to staff users.", status=403)


class PermissionTracerIndexView(TracerAccessMixin, View):
    def handle_no_access(self, request):
        if not request.user.is_authenticated:
            return redirect_to_login(request.get_full_path())
        return HttpResponseForbidden("Permission Tracer is restricted to staff users.")

    def get(self, request):
        return render(
            request,
            "permission_tracer/index.html",
            {"title": "Permission Tracer", "base_url": reverse("permission_tracer:index")},
        )


class PermissionTracerDebugView(TracerAccessMixin, View):
    def get(self, request):
        return _success(
            {
                "tracing_installed": tracing.is_installed(),
                "storage_backend": conf.get("STORAGE_BACKEND"),
                "stored_traces": storage.get_store().count(),
            }
        )


class PermissionTracerAPIView(TracerAccessMixin, View):
    def get(self, request):
        return _success(PermissionAnalyzer().analyze())


class PermissionTraceView(TracerAccessMixin, View):
    def get(self, request):
        store = storage.get_store()
        traces = store.list(conf.get("MAX_TRACES"))

        trace_id = request.GET.get("id")
        if trace_id:
            for index, trace in enumerate(traces):
                if trace_id in (trace.get("id"), str(index)):
                    return _success(trace)
            return _error("Trace not found", status=404)

        if request.GET.get("denied"):
            traces = [t for t in traces if t.get("denied_by") or t.get("status_code") in (401, 403)]
        return _success(traces[:20], total=store.count())

    def delete(self, request):
        storage.get_store().clear()
        return _success(None)


class PermissionGraphView(TracerAccessMixin, View):
    def get(self, request):
        analyzer = PermissionAnalyzer()
        analyzer.analyze()
        return _success(analyzer.get_permission_graph())


class PermissionSearchView(TracerAccessMixin, View):
    def get(self, request):
        query = request.GET.get("q", "").strip().lower()
        search_type = request.GET.get("type", "all")
        if not query:
            return _error("Query parameter required", status=400)

        analysis = PermissionAnalyzer().analyze()
        results = {"permissions": [], "endpoints": []}
        if search_type in ("permission", "all"):
            results["permissions"] = [
                {"name": name, "usage_count": len(endpoints), "endpoints": endpoints}
                for name, endpoints in analysis["permission_endpoints"].items()
                if query in name.lower()
            ]
        if search_type in ("endpoint", "all"):
            results["endpoints"] = [
                {
                    "path": info["path"],
                    "view_class": info["view_class"],
                    "permissions": info["permissions"],
                    "expression": info["expression"],
                    "methods": info["methods"],
                }
                for info in analysis["endpoint_permissions"].values()
                if query in info["path"].lower() or query in info["view_class"].lower()
            ]
        return _success(results, query=query)


class PermissionDetailView(TracerAccessMixin, View):
    def get(self, request, permission_name):
        analysis = PermissionAnalyzer().analyze()
        permission_name = unquote(permission_name)
        # Only permissions found by the analyzer, so this can't import arbitrary modules.
        if permission_name not in analysis["permission_endpoints"]:
            return _error("Unknown permission", status=404)

        endpoints = analysis["permission_endpoints"][permission_name]
        return _success(
            {
                "permission": permission_name,
                "usage_count": len(endpoints),
                "endpoints": endpoints,
                "implementation": inspection.summarize(permission_name),
            }
        )


class EndpointDetailView(TracerAccessMixin, View):
    def get(self, request, endpoint_path):
        analysis = PermissionAnalyzer().analyze()
        stripped = unquote(endpoint_path).strip("/")
        candidates = {stripped, f"/{stripped}", f"/{stripped}/"}
        for info in analysis["endpoint_permissions"].values():
            if info["path"] in candidates:
                return _success(info)
        return _error("Endpoint not found", status=404)
