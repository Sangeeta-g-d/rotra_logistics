from django.apps import AppConfig


class ApiAppConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'api_app'

    def ready(self):
        # Import and connect signals
        import api_app.signals