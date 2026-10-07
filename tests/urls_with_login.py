from django.http import HttpResponse
from django.urls import path

from .urls import urlpatterns as base_urlpatterns

urlpatterns = [
    *base_urlpatterns,
    path("accounts/login/", lambda request: HttpResponse("login")),
]
