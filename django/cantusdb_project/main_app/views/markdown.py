from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, JsonResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST

from main_app.markdown import render_markdown


@login_required
@require_POST
@never_cache
def markdown_preview(request: HttpRequest) -> JsonResponse:
    """Preview supplied text without reading or changing any source record."""
    return JsonResponse({"html": render_markdown(request.POST.get("text", ""))})
