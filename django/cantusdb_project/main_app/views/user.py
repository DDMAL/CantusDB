from typing import Dict, Any

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import LogoutView
from django.core.paginator import Paginator
from django.db.models import BooleanField, Case, Q, QuerySet, Value, When
from django.db.models.aggregates import Count
from django.views.generic import DetailView
from django.views.generic import ListView
from extra_views import SearchableListMixin

from main_app.models import Source
from main_app.permissions import (
    CustomAccessMixin,
    get_user_groups,
    user_group_valid,
)
from users.models import User as UserType


class UserDetailView(CustomAccessMixin, DetailView):  # type: ignore
    """Detail view for User model

    Accessed by /users/<pk>
    """

    model = get_user_model()
    context_object_name = "user"
    template_name = "user_detail.html"

    def test_func(self) -> bool:
        user = self.get_object()
        viewing_user = self.request.user
        return viewing_user.is_superuser or user.is_indexer or viewing_user == user

    def get_context_data(self, **kwargs: Any) -> Dict[str, Any]:
        context = super().get_context_data(**kwargs)
        user = context["user"]

        viewing_user = self.request.user
        if viewing_user.is_superuser or self.user_is_global_viewer:
            base_source_set = Source.objects.all()
        else:
            base_source_set = self.published_and_assigned_sources

        context["inventoried_sources"] = (
            base_source_set.filter(inventoried_by=user)
            .select_related("holding_institution")
            .all()
            .order_by("holding_institution__siglum")
        )

        context["full_text_sources"] = (
            base_source_set.filter(full_text_entered_by=user)
            .select_related("holding_institution")
            .all()
            .order_by("holding_institution__siglum")
        )

        context["melody_sources"] = (
            base_source_set.filter(melodies_entered_by=user)
            .select_related("holding_institution")
            .all()
            .order_by("holding_institution__siglum")
        )

        context["proofread_sources"] = (
            base_source_set.filter(proofreaders=user)
            .select_related("holding_institution")
            .all()
            .order_by("holding_institution__siglum")
        )

        context["description_sources"] = (
            base_source_set.filter(description_entered_by=user)
            .select_related("holding_institution")
            .all()
            .order_by("holding_institution__siglum")
        )

        context["edited_sources"] = (
            base_source_set.filter(other_editors=user)
            .select_related("holding_institution")
            .all()
            .order_by("holding_institution__siglum")
        )

        context["contributed_data_sources"] = (
            base_source_set.filter(source_data_contributed_by=user)
            .select_related("holding_institution")
            .all()
            .order_by("holding_institution__siglum")
        )

        return context


class UserSourceListView(LoginRequiredMixin, ListView):  # type: ignore [type-arg]
    context_object_name = "sources"
    template_name = "user_source_list.html"
    paginate_by = 3

    @staticmethod
    def annotate_proofreading_lock(queryset: QuerySet[Source]) -> QuerySet[Source]:
        """
        Flag each source that has been submitted for proofreading.

        This page offers chant-editing links, and a submitted source refuses
        them for everyone but editors (issue #1962). Annotating keeps the
        status string out of the template and costs no extra query.

        :param queryset: Sources to annotate.

        :return: The queryset with a `locked_for_proofreading` boolean.
        """
        return queryset.annotate(
            locked_for_proofreading=Case(
                When(source_status=Source.PROOFREAD_PENDING_STATUS, then=Value(True)),
                default=Value(False),
                output_field=BooleanField(),
            )
        )

    def get_queryset(self) -> QuerySet[Source]:
        return self.annotate_proofreading_lock(
            Source.objects.filter(
                Q(current_editors=self.request.user) | Q(created_by=self.request.user)
            )
            .order_by("-date_updated")
            .select_related("holding_institution")
            .distinct()
        )

    def get_context_data(self, **kwargs: Any) -> Dict[str, Any]:
        context = super().get_context_data(**kwargs)
        user: UserType = self.request.user
        user_created_sources = self.annotate_proofreading_lock(
            Source.objects.filter(created_by=user)
            .order_by("-date_created")
            .select_related("holding_institution")
            .distinct()
        )
        user_created_paginator = Paginator(user_created_sources, 6)
        user_created_page_num = self.request.GET.get("page2")
        user_created_page_obj = user_created_paginator.get_page(user_created_page_num)

        context["user_created_sources_page_obj"] = user_created_page_obj
        # Editors proofread submitted sources, so the lock never hides their
        # links. Mirrors CustomAccessMixin.user_is_editor, which this view
        # cannot reach without the whole access mixin.
        context["user_is_editor"] = user.is_superuser or user_group_valid(
            "editor", get_user_groups(user)
        )
        return context


class CustomLogoutView(LogoutView):
    def get_next_page(self):
        next_page = super().get_next_page()
        messages.success(self.request, "You have successfully logged out!")
        return next_page


class IndexerListView(SearchableListMixin, ListView):  # type: ignore[type-arg,misc]
    """A list of User objects shown to the public

    This view replaces the indexer list view on the old Cantus.
    The indexers are considered a subset of all User objects, the subset shown to the public.
    This includes the User objects corresponding to Indexer objects on the old Cantus.
    When passed a `?q=<query>` argument in the GET request, it will filter users
    based on the fields defined in `search_fields` with the `icontains` lookup.

    Accessed by /indexers/
    """

    model = get_user_model()
    ordering = "full_name"
    search_fields = ["full_name", "institution", "city", "country"]
    paginate_by = 100
    template_name = "indexer_list.html"
    context_object_name = "indexers"
    test_req = False

    def get_queryset(self) -> QuerySet[UserType]:
        all_users: QuerySet[UserType] = super().get_queryset()
        all_users = all_users.annotate(
            source_count=Count(
                "inventoried_sources", filter=Q(inventoried_sources__published=True)
            )
        )
        # display those who have at least one published source
        return all_users.filter(source_count__gte=1)
