from django.apps import AppConfig


class PermissionTracerConfig(AppConfig):
    name = "permission_tracer"
    verbose_name = "Permission Tracer"

    def ready(self):
        from . import conf, tracing

        if conf.get("ENABLED"):
            tracing.install()
