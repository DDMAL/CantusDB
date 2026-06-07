from django.conf import settings


def determine_project_environment(request) -> dict:
    return {
        "PROJECT_ENVIRONMENT": settings.PROJECT_ENVIRONMENT,
    }


def site_banner(request) -> dict:
    # Local import to avoid app-loading order issues.
    from main_app.models import SiteBanner

    banner = SiteBanner.load()
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
    return {"SITE_BANNER": None, "SITE_BANNER_IS_PREVIEW": False}
