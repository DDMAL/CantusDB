from django.conf import settings
from typing import Any, Dict

from django.db.models import Subquery, OuterRef, F, Func, QuerySet
from django.views.generic import DetailView, ListView

from main_app.models import Institution, Segment, InstitutionIdentifier, Source
from main_app.permissions import CustomAccessMixin


class InstitutionListView(CustomAccessMixin, ListView):  # type: ignore[type-arg]
    model = Institution
    context_object_name = "institutions"
    paginate_by = 100
    template_name = "institution_list.html"
    test_req = False

    def get_queryset(self) -> QuerySet[Institution]:

        # uses a subquery to get a count of the sources, filtering by published
        # sources only it the user is not logged in.
        qargs = {"holding_institution": OuterRef("pk")}

        if self.user.is_superuser or self.user_is_global_viewer:
            allowed_sources = Source.objects.all()
        else:
            allowed_sources = self.published_and_assigned_sources
        sources = (
            allowed_sources.filter(**qargs)
            .annotate(c=Func(F("id"), function="COUNT"))
            .values("c")
        )

        # Only display institution records if they have sources in them that the user
        # can access.
        qset = Institution.objects.annotate(num_sources=Subquery(sources)).filter(
            num_sources__gt=0
        )
        return qset


class InstitutionDetailView(CustomAccessMixin, DetailView):  # type: ignore[type-arg]
    model = Institution
    context_object_name = "institution"
    template_name = "institution_detail.html"
    test_req = False

    def get_context_data(self, **kwargs: Any) -> Dict[str, Any]:
        context = super().get_context_data(**kwargs)
        institution = context["institution"]

        # Show the Cantus and Bower sources in separate tables, and pre-format
        # the external authority links.
        cantus_segment = Segment.objects.get(id=settings.CANTUS_SEGMENT_ID)
        bower_segment = Segment.objects.get(id=settings.BOWER_SEGMENT_ID)
        if self.user.is_superuser or self.user_is_global_viewer:
            allowed_sources = Source.objects.all()
        else:
            allowed_sources = self.published_and_assigned_sources
        cantus_sources = allowed_sources.filter(
            holding_institution=institution, segment_m2m=cantus_segment
        ).select_related("holding_institution")
        bower_sources = allowed_sources.filter(
            holding_institution=institution, segment_m2m=bower_segment
        ).select_related("holding_institution")
        institution_authorities = InstitutionIdentifier.objects.filter(
            institution=institution
        )

        formatted_authorities = []
        for authority in institution_authorities:
            formatted_authorities.append(
                (authority.identifier_label, authority.identifier_url)
            )

        context["cantus_sources"] = cantus_sources
        context["num_cantus_sources"] = cantus_sources.count()
        context["bower_sources"] = bower_sources
        context["num_bower_sources"] = bower_sources.count()
        context["institution_authorities"] = formatted_authorities

        return context
