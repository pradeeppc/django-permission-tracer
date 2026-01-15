from django.apps import AppConfig


class PermissionTracerConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'permission_tracer'
    verbose_name = 'Permission Tracer'

    def ready(self):
        # Import signal handlers or other initialization code here
        pass

