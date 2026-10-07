import pytest

from permission_tracer.analyzer import PermissionAnalyzer, _readable

pytestmark = pytest.mark.django_db

IS_AUTH = "rest_framework.permissions.IsAuthenticated"
IS_ADMIN = "rest_framework.permissions.IsAdminUser"
ALLOW_ANY = "rest_framework.permissions.AllowAny"


@pytest.fixture
def endpoints():
    return PermissionAnalyzer().analyze()["endpoint_permissions"]


def test_paths_are_readable_and_deduplicated(endpoints):
    assert "/api/articles/" in endpoints
    assert "/api/articles/{pk}/" in endpoints
    assert "/api/users/{pk}/" in endpoints
    assert not any("format" in p or "^" in p or "(?P" in p for p in endpoints)


def test_tracer_does_not_list_itself(endpoints):
    assert not any(p.startswith("/devtools/") for p in endpoints)


def test_composed_permissions_do_not_crash(endpoints):
    detail = endpoints["/api/articles/"]["methods"]["GET"]
    assert detail["action"] == "list"
    assert detail["expression"] == "IsAuthenticated | HasAllowHeader"
    assert detail["permissions"] == [IS_AUTH, "tests.views.HasAllowHeader"]


def test_methods_come_from_router_actions(endpoints):
    assert set(endpoints["/api/articles/"]["methods"]) == {"GET", "POST"}
    assert endpoints["/api/articles/"]["methods"]["POST"]["action"] == "create"
    assert set(endpoints["/api/articles/{pk}/"]["methods"]) == {"GET"}


def test_extra_action_permissions(endpoints):
    public = endpoints["/api/articles/public/"]["methods"]["GET"]
    assert public["action"] == "public"
    assert public["permissions"] == [ALLOW_ANY]
    publish = endpoints["/api/articles/{pk}/publish/"]["methods"]["POST"]
    assert publish["permissions"] == [IS_ADMIN]


def test_get_permissions_override_is_evaluated_per_method(endpoints):
    info = endpoints["/api/dynamic/"]
    assert info["dynamic"] is True
    assert info["methods"]["GET"]["permissions"] == [ALLOW_ANY]
    assert info["methods"]["POST"]["permissions"] == [IS_ADMIN]
    assert info["expression"] == "varies by method"


def test_not_and_function_views(endpoints):
    assert endpoints["/api/guests-only/"]["expression"] == "~IsAuthenticated"
    assert endpoints["/api/admin-only/"]["methods"]["GET"]["permissions"] == [IS_ADMIN]


def test_django_auth_mixins(endpoints):
    info = endpoints["/secret/"]
    assert info["framework"] == "django"
    assert info["permissions"] == [
        "django.contrib.auth.mixins.LoginRequiredMixin",
        "django.contrib.auth.mixins.PermissionRequiredMixin",
    ]
    assert info["methods"]["GET"]["django_permissions"] == ["auth.view_user"]


def test_anonymous_access(endpoints):
    assert endpoints["/api/articles/public/"]["methods"]["GET"]["anonymous_allowed"] is True
    assert endpoints["/api/articles/"]["methods"]["GET"]["anonymous_allowed"] is False
    assert endpoints["/api/dynamic/"]["methods"]["GET"]["anonymous_allowed"] is True
    assert endpoints["/api/dynamic/"]["methods"]["POST"]["anonymous_allowed"] is False


def test_unprotected_endpoints():
    analyzer = PermissionAnalyzer()
    analyzer.analyze()
    found = {(u["method"], u["path"]) for u in analyzer.unprotected_endpoints()}
    assert ("GET", "/api/articles/public/") in found
    assert ("GET", "/api/dynamic/") in found
    assert ("GET", "/api/guests-only/") in found
    assert ("GET", "/api/articles/") not in found
    assert ("POST", "/api/dynamic/") not in found


def test_reverse_mapping_and_graph():
    analyzer = PermissionAnalyzer()
    analysis = analyzer.analyze()
    usages = {u["path"]: u["methods"] for u in analysis["permission_endpoints"][IS_ADMIN]}
    assert usages["/api/dynamic/"] == ["POST"]
    graph = analyzer.get_permission_graph()
    assert graph["stats"]["total_endpoints"] == analysis["total_endpoints"]


def test_result_is_cached():
    first = PermissionAnalyzer().analyze()
    assert PermissionAnalyzer().analyze() is first


@pytest.mark.parametrize(
    "regex, expected",
    [
        (r"^articles/$", "articles/"),
        (r"^articles/(?P<pk>[^/.]+)/$", "articles/{pk}/"),
        (r"^articles/(?P<pk>[^/.]+)/?$", "articles/{pk}/"),
        (r"^files/(?P<name>(foo|bar)\.txt)$", "files/{name}"),
        (r"^v1\.0/$", "v1.0/"),
    ],
)
def test_readable_regex(regex, expected):
    from django.urls.resolvers import RegexPattern

    assert _readable(RegexPattern(regex)) == expected
