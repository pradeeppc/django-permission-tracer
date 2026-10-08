from permission_tracer import inspection


def test_summarize_custom_permission():
    summary = inspection.summarize("tests.views.IsSelf")
    assert summary["class_name"] == "IsSelf"
    assert summary["metadata"]["is_builtin"] is False
    assert "has_object_permission" in summary["metadata"]["methods"]
    assert summary["logic_summary"]["checks_user"] is True
    assert summary["logic_summary"]["class_attributes"]["message"]["value"] == (
        "You can only view yourself."
    )
    assert list(summary["logic_summary"]["method_signatures"]) == ["has_object_permission"]


def test_summarize_builtin_permission():
    summary = inspection.summarize("rest_framework.permissions.IsAuthenticated")
    assert summary["metadata"]["is_builtin"] is True


def test_summarize_unknown_class():
    assert "error" in inspection.summarize("tests.views.DoesNotExist")


def test_method_signature_is_not_counted_as_a_permission_check():
    summary = inspection.summarize("tests.views.HasAllowHeader")["logic_summary"]
    assert summary["checks_permissions"] is False
    assert summary["methods_called"] == ["get"]


def test_is_authenticated_counts_as_an_authentication_check():
    summary = inspection.summarize("tests.views.IsActiveMember")["logic_summary"]
    assert summary["checks_authentication"] is True
    assert summary["checks_permissions"] is False
