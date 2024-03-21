import os


def determine_project_environment(request):
    project_environment: str = os.getenv("PROJECT_ENVIRONMENT")
    # in cantusdb/settings.py, we've already checked that PROJECT_ENVIRONMENT is
    # either PRODUCTION, STAGING or DEVELOPMENT
    return {
        "PROJECT_ENVIRONMENT": project_environment,
    }
