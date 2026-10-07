from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register("articles", views.ArticleViewSet, basename="article")

urlpatterns = [
    path("api/", include(router.urls)),
    path("api/dynamic/", views.DynamicView.as_view()),
    path("api/users/<int:pk>/", views.UserDetailView.as_view()),
    path("api/guests-only/", views.NotAuthenticatedView.as_view()),
    path("api/admin-only/", views.admin_only),
    path("secret/", views.SecretPage.as_view()),
    # Deliberately not the default prefix, to check the UI doesn't hardcode it.
    path("devtools/permissions/", include("permission_tracer.urls")),
]
