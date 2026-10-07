import pytest

from tests.blocking import TokenRequiredMiddleware, TracerExemptToken

pytestmark = pytest.mark.django_db

DASHBOARD = "/devtools/permissions/"
API = "/devtools/permissions/api/"
APP_ENDPOINT = "/api/articles/public/"


@pytest.fixture
def middleware(settings):
    def use(path):
        settings.MIDDLEWARE = [path, *settings.MIDDLEWARE]

    return use


def test_auth_middleware_blocks_dashboard_without_exemption(staff_client, middleware):
    middleware("tests.blocking.TokenRequiredMiddleware")
    assert staff_client.get(DASHBOARD).status_code == 401


@pytest.mark.parametrize(
    "path", ["tests.blocking.TracerExemptToken", "tests.blocking.TracerExemptLegacyToken"]
)
def test_exempt_middleware_lets_only_tracer_urls_through(staff_client, middleware, path):
    middleware(path)
    assert staff_client.get(DASHBOARD).status_code == 200
    assert staff_client.get(API).status_code == 200
    assert staff_client.get(APP_ENDPOINT).status_code == 401


def test_exempt_middleware_still_runs_its_hooks_for_other_urls(client, middleware):
    middleware("tests.blocking.TracerExemptToken")
    assert client.get(APP_ENDPOINT, HTTP_AUTHORIZATION="Bearer bad").status_code == 401
    assert client.get(APP_ENDPOINT, HTTP_AUTHORIZATION="Bearer good").status_code == 200


def test_no_exemption_when_tracer_is_disabled(staff_client, middleware, settings):
    middleware("tests.blocking.TracerExemptToken")
    settings.PERMISSION_TRACER = {"ENABLED": False}
    assert staff_client.get(DASHBOARD).status_code == 401


def test_wrapped_class_is_a_subclass():
    assert issubclass(TracerExemptToken, TokenRequiredMiddleware)
    assert TracerExemptToken.__name__ == "TracerExemptTokenRequiredMiddleware"
