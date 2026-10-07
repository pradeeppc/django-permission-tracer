"""Report which permissions protect each endpoint, and optionally fail on public ones."""

import csv
import fnmatch
import io
import json

from django.core.management.base import BaseCommand, CommandError

from permission_tracer.analyzer import PermissionAnalyzer


def _matrix_rows(analysis):
    for info in analysis["endpoint_permissions"].values():
        for method, detail in info["methods"].items():
            anonymous = detail.get("anonymous_allowed")
            yield {
                "path": info["path"],
                "method": method,
                "action": detail.get("action") or "",
                "permissions": detail["expression"],
                "anonymous": {True: "yes", False: "no", None: "?"}[anonymous],
                "view": info["view_class"],
            }


class Command(BaseCommand):
    help = "Analyze the project to discover which permissions protect each endpoint"

    def add_arguments(self, parser):
        parser.add_argument(
            "--output", type=str, help="Write the report to this file instead of stdout"
        )
        parser.add_argument(
            "--format",
            choices=["text", "json", "markdown", "csv"],
            default="text",
            help="Output format (markdown/csv produce a method-by-method permission matrix)",
        )
        parser.add_argument(
            "--fail-on-unprotected",
            action="store_true",
            help="Exit with an error if any DRF endpoint lets anonymous users through (for CI)",
        )
        parser.add_argument(
            "--allow",
            action="append",
            default=[],
            metavar="PATTERN",
            help='Path (glob, e.g. "/api/public/*") that is allowed to be public. Repeatable. '
            'Prefix with a method to scope it, e.g. "GET /api/articles/*"',
        )

    def handle(self, *args, **options):
        analyzer = PermissionAnalyzer()
        analysis = analyzer.analyze(use_cache=False)

        renderer = getattr(self, f"_render_{options['format']}")
        output = renderer(analysis)
        if options["output"]:
            with open(options["output"], "w", encoding="utf-8", newline="") as f:
                f.write(output)
            self.stderr.write(self.style.SUCCESS(f"Results saved to {options['output']}"))
        else:
            self.stdout.write(output)

        if options["fail_on_unprotected"]:
            self._audit(analyzer, options["allow"])

    def _audit(self, analyzer, allowed):
        rules = [p.split(" ", 1) if " " in p else [None, p] for p in allowed]

        def is_allowed(item):
            return any(
                (method is None or method.upper() == item["method"])
                and fnmatch.fnmatch(item["path"], glob)
                for method, glob in rules
            )

        offenders = [item for item in analyzer.unprotected_endpoints() if not is_allowed(item)]
        if not offenders:
            self.stderr.write(self.style.SUCCESS("No unexpected anonymous endpoints."))
            return
        lines = [
            f"  {o['method']:6} {o['path']}  ({o['expression']})  {o['view_class']}"
            for o in offenders
        ]
        raise CommandError(
            f"{len(offenders)} endpoint method(s) allow anonymous access:\n"
            + "\n".join(lines)
            + "\nAdd --allow PATTERN for endpoints that are meant to be public."
        )

    def _render_json(self, analysis):
        return json.dumps(analysis, indent=2)

    def _render_csv(self, analysis):
        buffer = io.StringIO()
        writer = csv.DictWriter(
            buffer, fieldnames=["path", "method", "action", "permissions", "anonymous", "view"]
        )
        writer.writeheader()
        writer.writerows(_matrix_rows(analysis))
        return buffer.getvalue()

    def _render_markdown(self, analysis):
        def cell(value):
            return str(value).replace("|", "\\|")

        lines = [
            "| Method | Path | Action | Permissions | Anonymous |",
            "|---|---|---|---|---|",
        ]
        for row in _matrix_rows(analysis):
            lines.append(
                f"| {row['method']} | `{cell(row['path'])}` | {cell(row['action'])} "
                f"| `{cell(row['permissions'])}` | {row['anonymous']} |"
            )
        return "\n".join(lines) + "\n"

    def _render_text(self, analysis):
        out = [
            "=" * 80,
            "PERMISSION ANALYSIS RESULTS",
            "=" * 80,
            f"Total endpoints:   {analysis['total_endpoints']}",
            f"Total permissions: {analysis['total_permissions']}",
            "",
            "-" * 80,
            "PERMISSIONS AND THEIR USAGE",
            "-" * 80,
        ]
        for perm_name, endpoints in sorted(analysis["permission_endpoints"].items()):
            out.append(f"\n{perm_name}  ({len(endpoints)} endpoint(s))")
            for endpoint in endpoints:
                out.append(f"    {','.join(endpoint['methods']):20} {endpoint['path']}")

        out += ["", "-" * 80, "ENDPOINTS AND THEIR PERMISSIONS", "-" * 80]
        for info in analysis["endpoint_permissions"].values():
            out.append(f"\n{info['path']}  [{info['view_class']}]")
            for method, detail in info["methods"].items():
                action = f" ({detail['action']})" if detail.get("action") else ""
                flag = "  <- anonymous allowed" if detail.get("anonymous_allowed") else ""
                out.append(f"    {method:6}{action:18} {detail['expression']}{flag}")
        return "\n".join(out) + "\n"
