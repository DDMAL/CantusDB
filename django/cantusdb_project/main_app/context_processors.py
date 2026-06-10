from django.conf import settings
from django.db import DatabaseError


def determine_project_environment(request) -> dict:
    return {
        "PROJECT_ENVIRONMENT": settings.PROJECT_ENVIRONMENT,
    }


def site_banner(request) -> dict:
    # Local import to avoid app-loading order issues.
    from main_app.models import SiteBanner

    no_banner = {"SITE_BANNER": None, "SITE_BANNER_IS_PREVIEW": False}
    try:
        banner = SiteBanner.load()
    except DatabaseError:
        # The deploy starts new code serving traffic before `migrate` runs
        # (the ansible cantusdb-app role applies migrations last), so the
        # table may not exist yet mid-rollout. This runs on every request, so
        # fail closed rather than 500 every page site-wide.
        return no_banner
    if banner.is_displayable():
        return {"SITE_BANNER": banner, "SITE_BANNER_IS_PREVIEW": False}
    user = getattr(request, "user", None)
    if (
        user is not None
        and user.is_authenticated
        and user.is_superuser
        and banner.has_content()
    ):
        return {"SITE_BANNER": banner, "SITE_BANNER_IS_PREVIEW": True}
    return no_banner
