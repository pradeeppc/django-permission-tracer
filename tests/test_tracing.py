import threading

import pytest
from django.test import Client
from rest_framework.test import APIRequestFactory

from permission_tracer import tracing
from tests.conftest import traces
from tests.views import ArticleViewSet

pytestmark = pytest.mark.django_db


def only_trace():
    found = traces()
    assert len(found) == 1, found
    return found[0]


def test_denied_request_explains_which_permission(client):
    response = client.get("/api/articles/")
    assert response.status_code == 403
    trace = only_trace()
    assert trace["action"] == "list"
    assert trace["view_class"]["full_path"] == "tests.views.ArticleViewSet"
    assert trace["denied_by"]["expression"] == "IsAuthenticated | HasAllowHeader"
    assert trace["denied_by"]["exception"] == "NotAuthenticated"
    breakdown = trace["checks"][0]["breakdown"]
    assert breakdown["op"] == "OR"
    assert [o["allowed"] for o in breakdown["operands"]] == [False, False]
    assert trace["permission_results"] == {
        "rest_framework.permissions.IsAuthenticated": {"allowed": False},
        "tests.views.HasAllowHeader": {"allowed": False},
    }


def test_allowed_request_is_recorded(client):
    response = client.get("/api/articles/", HTTP_X_ALLOW="1")
    assert response.status_code == 200
    trace = only_trace()
    assert trace["denied_by"] is None
    assert trace["checks"][0]["allowed"] is True
    assert trace["permissions_checked"] == [
        "rest_framework.permissions.IsAuthenticated",
        "tests.views.HasAllowHeader",
    ]


def test_custom_permission_overriding_has_permission_is_traced(client):
    client.post("/api/articles/1/publish/")
    trace = traces()[0]
    assert trace["permission_results"] == {
        "rest_framework.permissions.IsAdminUser": {"allowed": False}
    }


def test_object_permission_denial(client, django_user_model):
    alice = django_user_model.objects.create_user("alice", password="pw")
    bob = django_user_model.objects.create_user("bob", password="pw")
    client.force_login(alice)
    assert client.get(f"/api/users/{alice.pk}/").status_code == 200
    assert client.get(f"/api/users/{bob.pk}/").status_code == 403

    denied = traces()[0]
    assert denied["user"]["repr"] == "alice"
    assert denied["user"]["authenticated"] is True
    assert denied["denied_by"]["level"] == "object"
    assert denied["denied_by"]["expression"] == "IsSelf"
    assert denied["denied_by"]["detail"] == "You can only view yourself."
    object_checks = [c for c in denied["checks"] if c["level"] == "object"]
    assert object_checks[-1]["object"] == f"User(pk={bob.pk})"


def test_view_level_checks_still_deny_without_tracing():
    # Outside a traced request the wrapper must behave exactly like DRF.
    assert tracing.current() is None
    view = ArticleViewSet.as_view({"get": "list"})
    assert view(APIRequestFactory().get("/api/articles/")).status_code == 403
    assert view(APIRequestFactory().get("/api/articles/", HTTP_X_ALLOW="1")).status_code == 200


def test_unrouted_and_excluded_requests_are_not_stored(client, settings):
    client.get("/does-not-exist/")
    settings.PERMISSION_TRACER = {"ENABLED": True, "EXCLUDE_PATHS": ["/api/dynamic/"]}
    client.get("/api/dynamic/")
    assert traces() == []


def test_concurrent_requests_keep_their_own_traces():
    # The old implementation patched view classes with closures over the
    # current request, so concurrent requests wrote into each other's traces.
    barrier = threading.Barrier(8)

    def worker(n):
        c = Client()
        barrier.wait()
        for _ in range(5):
            if n % 2:
                c.get("/api/articles/", HTTP_X_ALLOW="1")
            else:
                c.get("/api/articles/")

    threads = [threading.Thread(target=worker, args=(n,)) for n in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    found = traces()
    assert len(found) == 40
    for trace in found:
        assert len(trace["checks"]) == 1
        assert (trace["status_code"] == 200) == (trace["denied_by"] is None)
        assert trace["checks"][0]["allowed"] == (trace["status_code"] == 200)
