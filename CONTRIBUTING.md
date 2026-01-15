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

4. Install development dependencies:
   ```bash
   pip install -r requirements-dev.txt
   pip install -e .
   ```

## Development Setup

1. Create a test Django project to develop against:
   ```bash
   django-admin startproject test_project
   cd test_project
   ```

2. Add `permission_tracer` to `INSTALLED_APPS` and configure as per installation guide

3. Run tests:
   ```bash
   pytest
   ```

## Code Style

- Follow PEP 8 style guidelines
- Use Black for code formatting: `black .`
- Use isort for import sorting: `isort .`
- Maximum line length: 100 characters

## Testing

- Write tests for new features
- Ensure all tests pass: `pytest`
- Aim for good test coverage

## Submitting Changes

1. Create a feature branch: `git checkout -b feature/your-feature-name`
2. Make your changes
3. Write or update tests
4. Ensure tests pass and code is formatted
5. Commit your changes: `git commit -m "Add feature: description"`
6. Push to your fork: `git push origin feature/your-feature-name`
7. Create a Pull Request

## Pull Request Guidelines

- Provide a clear description of changes
- Reference any related issues
- Ensure all tests pass
- Update documentation if needed

## Reporting Issues

When reporting issues, please include:
- Django version
- Python version
- Steps to reproduce
- Expected vs actual behavior
- Any error messages

Thank you for contributing! 🎉

