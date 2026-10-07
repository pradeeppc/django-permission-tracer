"""Settings, read from ``settings.PERMISSION_TRACER``. See the README for each option."""

from django.conf import settings
from django.utils.module_loading import import_string

DEFAULTS = {
    "ENABLED": None,  # None follows settings.DEBUG
    "ACCESS_CHECK": "permission_tracer.conf.staff_only",
    "STORAGE_BACKEND": "memory",
    "MAX_TRACES": 100,
    "TRACE_TIMEOUT": 3600,
    "EXCLUDE_PATHS": ["/admin/", "/static/", "/media/"],
}


def get(name):
    value = getattr(settings, "PERMISSION_TRACER", {}).get(name, DEFAULTS[name])
    if name == "ENABLED" and value is None:
        return settings.DEBUG
    return value


def staff_only(request):
    user = getattr(request, "user", None)
    return bool(user and user.is_active and user.is_staff)


def allow_in_debug(request):
    """Anyone when DEBUG is on, staff otherwise."""
    return settings.DEBUG or staff_only(request)


def has_access(request):
    check = get("ACCESS_CHECK")
    if isinstance(check, str):
        check = import_string(check)
    return bool(check(request))
