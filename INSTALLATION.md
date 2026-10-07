# Installation Guide

## Prerequisites

- Python 3.9 or higher
- Django 4.2 or higher
- Django REST Framework 3.14 or higher (optional, but recommended)

## Installation Steps

### 1. Install the Package

```bash
pip install "django-permission-tracer[drf]"
```

Or install from source:

```bash
git clone https://github.com/pradeeppc/django-permission-tracer.git
cd django-permission-tracer
pip install -e .
```

### 2. Add to INSTALLED_APPS

Add `permission_tracer` to your `INSTALLED_APPS` in `settings.py`:

```python
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    # ... your other apps
    "permission_tracer",
]
```

### 3. Add Middleware

Add the middleware to your `MIDDLEWARE` list. It should be near the top, but after security middleware:

```python
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "permission_tracer.middleware.PermissionTracerMiddleware",  # Add this
    "django.contrib.sessions.middleware.SessionMiddleware",
    # ... your other middleware
]
```

### 4. Add URLs

Include the permission tracer URLs in your main `urls.py`:

```python
from django.urls import path, include

urlpatterns = [
    # ... your other URL patterns
    path("_permission-tracer/", include("permission_tracer.urls")),
]
```

**Note:** The `/_permission-tracer/` path is recommended, but you can use any path you prefer.

### 5. Configure Settings (Optional)

The defaults are safe: tracing is on only when `DEBUG = True`, and only active staff users can open
the dashboard. To change that, see the Configuration section of the [README](README.md#configuration):

```python
PERMISSION_TRACER = {
    "ENABLED": None,  # None follows settings.DEBUG
    "ACCESS_CHECK": "permission_tracer.conf.staff_only",
    "STORAGE_BACKEND": "memory",  # or 'cache' to share traces between workers
    "MAX_TRACES": 100,
    "EXCLUDE_PATHS": ["/admin/", "/static/", "/media/"],
}
```

No migrations are needed; the tracer has no database models.

### 6. Test Installation

Start your Django development server:

```bash
python manage.py runserver
```

Log in as a staff user (for example via `/admin/`), then visit `http://localhost:8000/_permission-tracer/`.

## Verify Installation

Run the analysis command to verify everything is working:

```bash
python manage.py permission_tracer_analyze
```

This should output information about your permissions and endpoints.

## Troubleshooting

### Permission Tracer page shows 404

- The tracer is disabled when `DEBUG = False` unless you set `PERMISSION_TRACER['ENABLED'] = True`
- Make sure you've added the URLs correctly
- Check that `permission_tracer` is in `INSTALLED_APPS`
- Verify the URL path matches what you configured

### No permissions are being traced

- Ensure the middleware is added and enabled
- Check that `DEBUG = True`, or that `PERMISSION_TRACER['ENABLED']` is `True`
- Restart the server after changing `ENABLED`; tracing is installed at startup
- Views that override `check_permissions()` themselves are not traced

### Permission Tracer returns 403

- Only active staff users can use it by default. Log in as staff, or set `ACCESS_CHECK`
- Verify your views are using permission classes

### Analysis command shows no results

- Make sure your URLs are properly configured
- Check that your views inherit from DRF viewsets or APIView
- Verify permission classes are defined on your views

## Next Steps

- Read the [README.md](README.md) for usage examples
- Explore the web interface at `/_permission-tracer/`
- Run `python manage.py permission_tracer_analyze` to see your permission mappings

