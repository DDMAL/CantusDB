from django.conf import settings


def determine_project_environment(request) -> str:
    """_summary_

    Args:
        request: a request.

    Returns:
        str: A string indicating the current value of the
        PROJECT_ENVIRONMENT variable, which is read from an environment
        variable in settings.py.

    """
    return {
        "PROJECT_ENVIRONMENT": settings.PROJECT_ENVIRONMENT,
    }
