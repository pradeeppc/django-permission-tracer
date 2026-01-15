# Quick Start Guide

Get up and running with Django Permission Tracer in 5 minutes!

## 1. Install

```bash
pip install django-permission-tracer
```

## 2. Configure Django

Add to `settings.py`:

```python
INSTALLED_APPS = [
    # ... your apps
    'permission_tracer',
]

MIDDLEWARE = [
    # ... your middleware
    'permission_tracer.middleware.PermissionTracerMiddleware',
]
```

Add to `urls.py`:

```python
urlpatterns = [
    # ... your URLs
    path('_permission-tracer/', include('permission_tracer.urls')),
]
```

## 3. Run Server

```bash
python manage.py runserver
```

## 4. Open Browser

Visit: `http://localhost:8000/_permission-tracer/`

## 5. Analyze Your Permissions

Run the CLI command:

```bash
python manage.py permission_tracer_analyze
```

## That's It! 🎉

You now have:
- ✅ Permission tracing enabled
- ✅ Web interface for exploration
- ✅ CLI tool for analysis
- ✅ Reverse lookup (permission → endpoints)
- ✅ Forward lookup (endpoint → permissions)

## Next Steps

- Explore the web interface tabs
- Search for specific permissions or endpoints
- View the permission graph
- Check request traces

## Example Use Cases

### Find where a permission is used:
1. Go to "Permissions" tab
2. Click on a permission
3. See all endpoints using it

### See what protects an API:
1. Go to "Endpoints" tab
2. Click on an endpoint
3. See all permissions protecting it

### Debug a denied request:
1. Make the request
2. Go to "Trace" tab
3. See which permissions were checked and why it failed

