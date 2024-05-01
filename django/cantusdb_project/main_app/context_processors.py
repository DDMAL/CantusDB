from django.conf import settings


def determine_project_environment(request):
    return {
        "PROJECT_ENVIRONMENT": settings.PROJECT_ENVIRONMENT,
    }
