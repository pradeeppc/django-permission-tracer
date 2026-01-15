# Django Permission Tracer

🔍 **Trace and visualize Django permissions** - See which permissions protect your APIs and discover where permissions are used across your codebase.

A plug-and-play Django library that helps developers understand complex permission structures in Django REST Framework applications through static analysis and runtime tracing.

## Features

- 🎯 **Permission Discovery**: See which permissions protect each API endpoint
- 🔄 **Reverse Lookup**: Find all endpoints using a specific permission
- 📊 **Visualization**: Interactive graph showing permission-to-API mappings
- 🐛 **Permission Debugging**: Trace why a request was denied
- 📝 **Auto-Documentation**: Generate permission documentation automatically
- 🔌 **Plug & Play**: Easy integration with any Django project

## Quickstart

### Installation

```bash
pip install django-permission-tracer
```

### Setup

1. Add `permission_tracer` to your `INSTALLED_APPS`:

```python
INSTALLED_APPS = [
    # ... your other apps
    'permission_tracer',
]
```

2. Add the middleware to your `MIDDLEWARE` (should be near the top):

```python
MIDDLEWARE = [
    'permission_tracer.middleware.PermissionTracerMiddleware',
    # ... your other middleware
]
```

3. Include the permission tracer URLs in your main `urls.py`:

```python
from django.urls import path, include

urlpatterns = [
    # ... your other URLs
    path('_permission-tracer/', include('permission_tracer.urls')),
]
```

4. Run migrations (if using database storage):

```bash
python manage.py migrate permission_tracer
```

5. Start your Django server and visit `http://localhost:8000/_permission-tracer/` 🚀

## Usage

### View Permission Mappings

Navigate to `/_permission-tracer/` to see:
- **API Explorer**: Browse all your APIs and their associated permissions
- **Permission Explorer**: See where each permission is used
- **Graph View**: Visual representation of permission-to-API relationships

### Trace a Request

1. Make a request to any API endpoint
2. Go to `/_permission-tracer/trace/` to see the latest traced request
3. View which permissions were checked and their results

### Static Analysis

Run the management command to analyze your codebase:

```bash
python manage.py permission_tracer_analyze
```

This will discover all permission classes and their mappings to endpoints.

## Configuration

Add to your `settings.py`:

```python
PERMISSION_TRACER = {
    'ENABLED': True,  # Set to False to disable tracing
    'STORAGE_BACKEND': 'memory',  # 'memory' or 'database'
    'MAX_TRACES': 100,  # Maximum number of traces to keep in memory
    'EXCLUDE_PATHS': ['/_permission-tracer/', '/admin/'],  # Paths to exclude
}
```

## How It Works

1. **Middleware**: Intercepts requests and tracks permission checks in real-time
2. **Static Analysis**: Automatically discovers permission classes from your viewsets and URL patterns
3. **Visualization**: Provides an intuitive web interface to explore and understand permission mappings

<img width="1877" height="594" alt="image" src="https://github.com/user-attachments/assets/597dbc3a-5eb1-4416-8439-2b18ba647c24" />




