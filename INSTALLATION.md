# Installation Guide

## Prerequisites

- Python 3.8 or higher
- Django 3.2 or higher
- Django REST Framework 3.12 or higher (optional, but recommended)

## Installation Steps

### 1. Install the Package

```bash
pip install django-permission-tracer
```

Or install from source:

```bash
git clone https://github.com/yourusername/django-permission-tracer.git
cd django-permission-tracer
pip install -e .
```

### 2. Add to INSTALLED_APPS

Add `permission_tracer` to your `INSTALLED_APPS` in `settings.py`:

```python
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    # ... your other apps
    'permission_tracer',
]
```

### 3. Add Middleware

Add the middleware to your `MIDDLEWARE` list. It should be near the top, but after security middleware:

```python
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'permission_tracer.middleware.PermissionTracerMiddleware',  # Add this
    'django.contrib.sessions.middleware.SessionMiddleware',
    # ... your other middleware
]
```

### 4. Add URLs

Include the permission tracer URLs in your main `urls.py`:

```python
from django.urls import path, include

urlpatterns = [
    # ... your other URL patterns
    path('_permission-tracer/', include('permission_tracer.urls')),
]
```

**Note:** The `/_permission-tracer/` path is recommended, but you can use any path you prefer.

### 5. Configure Settings (Optional)

Add configuration to your `settings.py`:

```python
PERMISSION_TRACER = {
    'ENABLED': True,  # Set to False to disable tracing
    'STORAGE_BACKEND': 'memory',  # 'memory', 'database', or 'cache'
    'MAX_TRACES': 100,  # Maximum number of traces to keep
    'EXCLUDE_PATHS': [
        '/_permission-tracer/',
        '/admin/',
        '/static/',
        '/media/',
    ],  # Paths to exclude from tracing
}
```

### 6. Run Migrations (Optional)

If you plan to use database storage:

```bash
python manage.py migrate permission_tracer
```

### 7. Test Installation

Start your Django development server:

```bash
python manage.py runserver
```

Visit `http://localhost:8000/_permission-tracer/` in your browser. You should see the Permission Tracer interface.

## Verify Installation

Run the analysis command to verify everything is working:

```bash
python manage.py permission_tracer_analyze
```

This should output information about your permissions and endpoints.

## Troubleshooting

### Permission Tracer page shows 404

- Make sure you've added the URLs correctly
- Check that `permission_tracer` is in `INSTALLED_APPS`
- Verify the URL path matches what you configured

### No permissions are being traced

- Ensure the middleware is added and enabled
- Check that `PERMISSION_TRACER['ENABLED']` is `True`
- Verify your views are using permission classes

### Analysis command shows no results

- Make sure your URLs are properly configured
- Check that your views inherit from DRF viewsets or APIView
- Verify permission classes are defined on your views

## Next Steps

- Read the [README.md](README.md) for usage examples
- Explore the web interface at `/_permission-tracer/`
- Run `python manage.py permission_tracer_analyze` to see your permission mappings

