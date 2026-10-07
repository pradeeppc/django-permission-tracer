import csv
import io

import pytest
from django.core.management import CommandError, call_command

pytestmark = pytest.mark.django_db


def run(*args):
    out = io.StringIO()
    call_command("permission_tracer_analyze", *args, stdout=out, stderr=io.StringIO())
    return out.getvalue()


def test_text_report():
    out = run()
    assert "/api/articles/public/" in out
    assert "IsAuthenticated | HasAllowHeader" in out


def test_markdown_matrix():
    out = run("--format", "markdown")
    assert "| POST | `/api/dynamic/` |  | `IsAdminUser` | no |" in out
    assert "`IsAuthenticated \\| HasAllowHeader`" in out


def test_csv_matrix():
    rows = list(csv.DictReader(io.StringIO(run("--format", "csv"))))
    public = next(r for r in rows if r["path"] == "/api/articles/public/")
    assert public == {
        "path": "/api/articles/public/",
        "method": "GET",
        "action": "public",
        "permissions": "AllowAny",
        "anonymous": "yes",
        "view": "tests.views.ArticleViewSet",
    }


def test_fail_on_unprotected():
    with pytest.raises(CommandError) as exc:
        run("--fail-on-unprotected")
    message = str(exc.value)
    assert "/api/articles/public/" in message
    assert "/api/dynamic/" in message


def test_allow_list_silences_expected_public_endpoints():
    run(
        "--fail-on-unprotected",
        "--allow",
        "/api/",  # DefaultRouter's API root
        "--allow",
        "/api/articles/public/",
        "--allow",
        "GET /api/dynamic/",
        "--allow",
        "/api/guests-only/",
    )


def test_method_scoped_allow_does_not_cover_other_methods():
    with pytest.raises(CommandError):
        run("--fail-on-unprotected", "--allow", "POST /api/*")
