import pytest
from django.test import Client

from tests.conftest import traces

pytestmark = pytest.mark.django_db

API = "/devtools/permissions/api/"


@pytest.mark.parametrize(
    "url", [API, API + "graph/", API + "trace/", API + "debug/", API + "search/?q=a"]
)
def test_anonymous_and_non_staff_are_refused(client, django_user_model, url):
    assert client.get(url).status_code == 403
    client.force_login(django_user_model.objects.create_user("joe", password="pw"))
    assert client.get(url).status_code == 403


def test_index_redirects_anonymous_to_login(client):
    response = client.get("/devtools/permissions/")
    assert response.status_code == 302
    assert "login" in response["Location"]


def test_index_uses_mount_prefix(staff_client):
    response = staff_client.get("/devtools/permissions/")
    assert response.status_code == 200
    html = response.content.decode()
    assert 'const BASE_URL = "/devtools/permissions/";' in html
    assert "/_permission-tracer/" not in html


def test_disabled_returns_404(staff_client, settings):
    settings.PERMISSION_TRACER = {"ENABLED": False}
    assert staff_client.get(API).status_code == 404


def test_enabled_follows_debug_by_default(staff_client, settings):
    settings.PERMISSION_TRACER = {}
    settings.DEBUG = False
    assert staff_client.get(API).status_code == 404
    settings.DEBUG = True
    assert staff_client.get(API).status_code == 200


def test_custom_access_check(client, settings):
    settings.PERMISSION_TRACER = {"ENABLED": True, "ACCESS_CHECK": lambda request: True}
    assert client.get(API).status_code == 200


def test_staff_gets_analysis(staff_client):
    data = staff_client.get(API).json()["data"]
    assert "/api/articles/" in data["endpoint_permissions"]


def test_trace_endpoint_and_filters(staff_client):
    other = Client()
    other.get("/api/articles/")
    other.get("/api/articles/public/")
    all_traces = staff_client.get(API + "trace/").json()
    assert all_traces["total"] == 2
    denied = staff_client.get(API + "trace/?denied=1").json()["data"]
    assert [t["path"] for t in denied] == ["/api/articles/"]
    one = staff_client.get(API + "trace/?id=" + denied[0]["id"]).json()["data"]
    assert one["path"] == "/api/articles/"


def test_tracer_requests_are_not_traced(staff_client):
    staff_client.get(API)
    assert traces() == []


def test_permission_detail_only_for_known_permissions(staff_client):
    ok = staff_client.get(API + "permission/tests.views.IsSelf/")
    assert ok.status_code == 200
    assert "has_object_permission" in ok.json()["data"]["implementation"]["source_code"]
    assert staff_client.get(API + "permission/os.system/").status_code == 404


def test_endpoint_detail(staff_client):
    data = staff_client.get(API + "endpoint/api/dynamic/").json()["data"]
    assert data["methods"]["POST"]["expression"] == "IsAdminUser"


def test_errors_do_not_leak_tracebacks(staff_client, monkeypatch):
    from permission_tracer import analyzer

    def boom(self, use_cache=True):
        raise RuntimeError("secret detail")

    monkeypatch.setattr(analyzer.PermissionAnalyzer, "analyze", boom)
    response = staff_client.get(API)
    assert response.status_code == 500
    assert "secret detail" not in response.content.decode()
    assert "Traceback" not in response.content.decode()


def test_clearing_traces_requires_csrf(staff):
    client = Client(enforce_csrf_checks=True)
    client.force_login(staff)
    assert client.delete(API + "trace/").status_code == 403
