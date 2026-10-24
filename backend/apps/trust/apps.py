from django.apps import AppConfig


class TrustConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.trust"
    verbose_name = "Trusted community voices"

    def ready(self):
        from . import signals  # noqa: F401  (keeps scores current when members act)
