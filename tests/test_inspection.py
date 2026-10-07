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
