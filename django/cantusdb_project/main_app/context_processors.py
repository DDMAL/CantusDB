import os


def determine_project_environment(request):
    project_environment = os.getenv("PROJECT_ENVIRONMENT", None)
    if not (
        project_environment == "DEVELOPMENT"
        or project_environment == "STAGING"
        or project_environment == "PRODUCTION"
    ):
        raise ValueError(
            "The PROJECT_ENVIRONMENT environment variable must be either "
            "DEVELOPMENT, STAGING, or PRODUCTION. "
            f"Its current value is {project_environment}."
        )
    return {
        "PROJECT_ENVIRONMENT": project_environment,
    }
