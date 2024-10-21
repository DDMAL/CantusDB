"""
A module containing views for pages that provide general site statistics.
"""

from main_app.models import (
    Chant,
    Sequence,
    Source,
    Feast,
    Service,
    Provenance,
    Genre,
    Notation,
    Century,
)
from main_app.permissions import user_is_project_manager

from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.paginator import Paginator
from django.shortcuts import render


@login_required
def items_count(request):
    """
    Function-based view for the ``items count`` page, accessed with ``content-statistics``

    Update 2022-01-05:
    This page has been changed on the original Cantus. It is now in the private domain

    Args:
        request (request): The request

    Returns:
        HttpResponse: Render the page
    """
    # in items count, the number on old cantus shows the total count of a type of object (chant, seq)
    # no matter published or not
    # but for the count of sources, it only shows the count of published sources
    chant_count = Chant.objects.count()
    sequence_count = Sequence.objects.count()
    source_count = Source.objects.filter(published=True).count()

    context = {
        "chant_count": chant_count,
        "sequence_count": sequence_count,
        "source_count": source_count,
    }
    return render(request, "items_count.html", context)


# first give the user a chance to login
@login_required
# if they're logged in but they're not a project manager, raise 403
@user_passes_test(user_is_project_manager)
def content_overview(request):
    objects = []
    models = [
        Source,
        Chant,
        Feast,
        Sequence,
        Service,
        Provenance,
        Genre,
        Notation,
        Century,
    ]

    model_names = [model._meta.verbose_name_plural for model in models]
    selected_model_name = request.GET.get("model", None)
    selected_model = None
    if selected_model_name in model_names:
        selected_model = models[model_names.index(selected_model_name)]

    objects = []
    if selected_model:
        objects = selected_model.objects.all().order_by("-date_updated")

    paginator = Paginator(objects, 100)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {
        "models": model_names,
        "selected_model_name": selected_model_name,
        "page_obj": page_obj,
    }

    return render(request, "content_overview.html", context)
