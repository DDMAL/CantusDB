from django.views.generic import TemplateView


class CcdbTeamView(TemplateView):
    """Project Team page for the Canadian Chant Database."""

    template_name = "ccdb_team.html"


class CcdbMapView(TemplateView):
    """Map of Sources page for the Canadian Chant Database."""

    template_name = "ccdb_map.html"
