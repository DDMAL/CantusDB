from django.db.models import Count, Subquery, OuterRef, Aggregate, F, Q, Func
from django.views.generic import DetailView, ListView

from main_app.identifiers import IDENTIFIER_TYPES, TYPE_PREFIX
from main_app.models import Institution, Source, Segment, InstitutionIdentifier


class InstitutionListView(ListView):
    model = Institution
    context_object_name = "institutions"
    paginate_by = 100
    template_name = "institution_list.html"

    def get_queryset(self):
        display_unpublished: bool = self.request.user.is_authenticated

        # uses a subquery to get a count of the sources, filtering by published
        # sources only it the user is not logged in.
        qargs = {"holding_institution": OuterRef("pk")}
        if display_unpublished is False:
            qargs["published"] = True

        sources = (
            Source.objects.filter(**qargs)
            .annotate(c=Func(F("id"), function="COUNT"))
            .values("c")
        )

        # Only display institution records if they have sources in them that the user
        # can access.
        qset = Institution.objects.annotate(num_sources=Subquery(sources)).filter(
            num_sources__gt=0
        )
        return qset


class InstitutionDetailView(DetailView):
    model = Institution
    context_object_name = "institution"
    template_name = "institution_detail.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        institution = self.get_object()

        # Show the Cantus and Bower sources in separate tables, and pre-format
        # the external authority links.
        cantus_segment = Segment.objects.get(id=4063)
        bower_segment = Segment.objects.get(id=4064)
        cantus_sources = Source.objects.filter(
            holding_institution=institution, segment=cantus_segment
        ).select_related("holding_institution")
        bower_sources = Source.objects.filter(
            holding_institution=institution, segment=bower_segment
        ).select_related("holding_institution")
        institution_authorities = InstitutionIdentifier.objects.filter(
            institution=institution
        )

        display_unpublished = self.request.user.is_authenticated
        if display_unpublished is False:
            cantus_sources = cantus_sources.filter(published=True)
            bower_sources = bower_sources.filter(published=True)

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
