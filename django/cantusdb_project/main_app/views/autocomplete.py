from dal import autocomplete
from django.db.models import Q
from django.contrib.auth import get_user_model

from main_app.models import (
    Century,
    Differentia,
    Feast,
    Genre,
    Service,
    Institution,
    Provenance,
)


class CurrentEditorsAutocomplete(autocomplete.Select2QuerySetView):
    def get_queryset(self):
        if not self.request.user.is_authenticated:
            return get_user_model().objects.none()
        # pylint: disable=unsupported-binary-operation
        qs = (
            get_user_model()
            .objects.filter(
                Q(groups__name="project manager")
                | Q(groups__name="editor")
                | Q(groups__name="contributor")
            )
            .order_by("full_name")
        )
        if self.q:
            qs = qs.filter(
                Q(full_name__istartswith=self.q) | Q(email__istartswith=self.q)
            )
        return qs


class AllUsersAutocomplete(autocomplete.Select2QuerySetView):
    def get_queryset(self):
        if not self.request.user.is_authenticated:
            return get_user_model().objects.none()
        qs = get_user_model().objects.all().order_by("full_name")
        if self.q:
            qs = qs.filter(
                Q(full_name__istartswith=self.q) | Q(email__istartswith=self.q)
            )
        return qs


class CenturyAutocomplete(autocomplete.Select2QuerySetView):
    def get_queryset(self):
        if not self.request.user.is_authenticated:
            return Century.objects.none()
        qs = Century.objects.all().order_by("name")
        if self.q:
            qs = qs.filter(name__istartswith=self.q)
        return qs


class FeastAutocomplete(autocomplete.Select2QuerySetView):
    def get_queryset(self):
        if not self.request.user.is_authenticated:
            return Feast.objects.none()
        qs = Feast.objects.all().order_by("name")
        if self.q:
            qs = qs.filter(name__icontains=self.q)
        return qs


class ServiceAutocomplete(autocomplete.Select2QuerySetView):
    def get_result_label(self, result):
        return f"{result.name} - {result.description}"

    def get_queryset(self):
        if not self.request.user.is_authenticated:
            return Service.objects.none()
        qs = Service.objects.all().order_by("name")
        if self.q:
            qs = qs.filter(
                Q(name__istartswith=self.q) | Q(description__icontains=self.q)
            )
        return qs


class GenreAutocomplete(autocomplete.Select2QuerySetView):
    def get_result_label(self, result):
        return f"{result.name} - {result.description}"

    def get_queryset(self):
        if not self.request.user.is_authenticated:
            return Genre.objects.none()
        qs = Genre.objects.all().order_by("name")
        if self.q:
            qs = qs.filter(
                Q(name__istartswith=self.q) | Q(description__icontains=self.q)
            )
        return qs


class DifferentiaAutocomplete(autocomplete.Select2QuerySetView):
    def get_queryset(self):
        if not self.request.user.is_authenticated:
            return Differentia.objects.none()
        qs = Differentia.objects.all().order_by("differentia_id")
        if self.q:
            qs = qs.filter(differentia_id__istartswith=self.q)
        return qs


class ProvenanceAutocomplete(autocomplete.Select2QuerySetView):
    def get_queryset(self):
        if not self.request.user.is_authenticated:
            return Provenance.objects.none()
        qs = Provenance.objects.all().order_by("name")
        if self.q:
            qs = qs.filter(name__icontains=self.q)
        return qs


class ProofreadByAutocomplete(autocomplete.Select2QuerySetView):
    def get_queryset(self):
        if not self.request.user.is_authenticated:
            return get_user_model().objects.none()
        qs = (
            get_user_model()
            .objects.filter(
                Q(groups__name="project manager") | Q(groups__name="editor")
            )
            .distinct()
            .order_by("full_name")
        )
        if self.q:
            qs = qs.filter(
                Q(full_name__istartswith=self.q) | Q(email__istartswith=self.q)
            )
        return qs


class HoldingAutocomplete(autocomplete.Select2QuerySetView):
    def get_queryset(self):
        if not self.request.user.is_authenticated:
            return Institution.objects.none()

        qs = Institution.objects.all().order_by("name")
        if self.q:
            qs = qs.filter(Q(name__istartswith=self.q) | Q(siglum__istartswith=self.q))
        return qs
