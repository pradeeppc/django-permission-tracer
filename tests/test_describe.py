from rest_framework.permissions import AllowAny, IsAdminUser, IsAuthenticated

from permission_tracer import describe
from tests.views import HasAllowHeader


def test_plain_class():
    d = describe.describe(IsAuthenticated)
    assert d["expression"] == "IsAuthenticated"
    assert d["leaves"] == ["rest_framework.permissions.IsAuthenticated"]


def test_composed_classes_and_instances_match():
    composed = (IsAuthenticated | HasAllowHeader) & ~IsAdminUser
    expected = "(IsAuthenticated | HasAllowHeader) & ~IsAdminUser"
    assert describe.describe(composed)["expression"] == expected
    assert describe.describe(composed())["expression"] == expected
    assert describe.describe(composed)["leaves"] == [
        "rest_framework.permissions.IsAuthenticated",
        "tests.views.HasAllowHeader",
        "rest_framework.permissions.IsAdminUser",
    ]


def test_unresolvable_string_is_kept():
    assert describe.describe("myapp.perms.Missing")["leaves"] == ["myapp.perms.Missing"]


def test_operands():
    assert describe.operands(AllowAny()) == []
    assert len(describe.operands((AllowAny | IsAdminUser)())) == 2
