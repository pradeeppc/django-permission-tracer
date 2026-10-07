# Contributing to Django Permission Tracer

Thank you for your interest in contributing! This document provides guidelines and instructions for contributing.

## Getting Started

1. Fork the repository
2. Clone your fork:
   ```bash
   git clone https://github.com/YOUR_USERNAME/django-permission-tracer.git
   cd django-permission-tracer
   ```
   
   Replace `YOUR_USERNAME` with your GitHub username.

3. Create a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

4. Install the package with development dependencies:
   ```bash
   pip install -e ".[dev]"
   ```

## Running Tests

The test suite includes a small Django project (`tests/`), so no separate project is needed:

```bash
pytest
```

## Code Style

Code is formatted and linted with [Ruff](https://docs.astral.sh/ruff/) (configured in `pyproject.toml`):

```bash
ruff format .
ruff check --fix .
```

CI runs both, plus the test suite on every supported Python/Django/DRF combination.

## Submitting Changes

1. Create a feature branch: `git checkout -b feature/your-feature-name`
2. Make your changes
3. Write or update tests
4. Ensure tests pass and `ruff check` / `ruff format --check` are clean
5. Add an entry to `CHANGELOG.md`
6. Commit your changes: `git commit -m "Add feature: description"`
7. Push to your fork: `git push origin feature/your-feature-name`
8. Create a Pull Request

## Pull Request Guidelines

- Provide a clear description of changes
- Reference any related issues
- Ensure all tests pass
- Update documentation if needed

## Releasing

1. Update `__version__` in `permission_tracer/__init__.py` and the `CHANGELOG.md` entry
2. Commit, then create a GitHub release with a `vX.Y.Z` tag
3. The `publish` workflow builds the package and uploads it to PyPI

## Reporting Issues

When reporting issues, please include:
- Django version
- Python version
- Steps to reproduce
- Expected vs actual behavior
- Any error messages

Thank you for contributing! 🎉

