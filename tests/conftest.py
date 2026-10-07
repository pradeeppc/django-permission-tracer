import pytest

from permission_tracer import analyzer, storage


@pytest.fixture(autouse=True)
def fresh_state():
    analyzer.clear_cache()
    storage.get_store().clear()
    yield
    storage.get_store().clear()


@pytest.fixture
def staff(django_user_model):
    return django_user_model.objects.create_user("staff", password="pw", is_staff=True)


@pytest.fixture
def staff_client(client, staff):
    client.force_login(staff)
    return client


def traces():
    return storage.get_store().list(1000)
