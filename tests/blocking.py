from django.http import HttpResponse
from django.utils.deprecation import MiddlewareMixin

from permission_tracer.middleware import tracer_exempt


class TokenRequiredMiddleware:
    """Rejects requests without a token, like a project's JWT middleware."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if "HTTP_AUTHORIZATION" not in request.META:
            return HttpResponse("access token is required", status=401)
        return self.get_response(request)

    def process_view(self, request, view_func, view_args, view_kwargs):
        if request.META.get("HTTP_AUTHORIZATION") != "Bearer good":
            return HttpResponse("upstream token failed", status=401)
        return None


class LegacyTokenRequiredMiddleware(MiddlewareMixin):
    def process_request(self, request):
        if "HTTP_AUTHORIZATION" not in request.META:
            return HttpResponse("access token is required", status=401)
        return None


TracerExemptToken = tracer_exempt(TokenRequiredMiddleware)
TracerExemptLegacyToken = tracer_exempt(LegacyTokenRequiredMiddleware)
