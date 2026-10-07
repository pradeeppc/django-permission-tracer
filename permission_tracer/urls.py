from django.urls import path

from . import views

app_name = "permission_tracer"

urlpatterns = [
    path("", views.PermissionTracerIndexView.as_view(), name="index"),
    path("api/", views.PermissionTracerAPIView.as_view(), name="api"),
    path("api/graph/", views.PermissionGraphView.as_view(), name="graph"),
    path("api/search/", views.PermissionSearchView.as_view(), name="search"),
    path("api/trace/", views.PermissionTraceView.as_view(), name="trace"),
    path("api/debug/", views.PermissionTracerDebugView.as_view(), name="debug"),
    path(
        "api/permission/<str:permission_name>/",
        views.PermissionDetailView.as_view(),
        name="permission_detail",
    ),
    path(
        "api/endpoint/<path:endpoint_path>/",
        views.EndpointDetailView.as_view(),
        name="endpoint_detail",
    ),
]
