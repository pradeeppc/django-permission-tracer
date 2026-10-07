# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project uses
[Semantic Versioning](https://semver.org/).

## [0.1.0] - Unreleased

First release.

### Added

- Static analysis of every DRF endpoint, per HTTP method and viewset action. It understands
  `@action(permission_classes=...)`, `get_permissions()` overrides and composed permissions
  (`&`, `|`, `~`), plus Django's `LoginRequiredMixin` / `PermissionRequiredMixin`.
- Anonymous-access check for each endpoint method.
- Runtime tracing of `has_permission` and `has_object_permission`, recording which permission
  denied a request and, for composed permissions, which operand failed.
- `permission_tracer_analyze` management command with text, JSON, Markdown and CSV output, and
  `--fail-on-unprotected` / `--allow` for CI.
- Staff-only web dashboard, enabled only when `DEBUG = True` by default.

[0.1.0]: https://github.com/pradeeppc/django-permission-tracer/releases/tag/v0.1.0
