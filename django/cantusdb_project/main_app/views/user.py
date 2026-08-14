from typing import Dict, Any

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import LogoutView
from django.core.paginator import Paginator
from django.db.models import Q, QuerySet
from django.db.models.aggregates import Count
from django.views.generic import DetailView
from django.views.generic import ListView
from extra_views import SearchableListMixin

from main_app.models import Source
from main_app.permissions import CustomAccessMixin
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

    def get_queryset(self) -> QuerySet[Source]:
        return (
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
        user_created_sources = (
            Source.objects.filter(created_by=user)
            .order_by("-date_created")
            .select_related("holding_institution")
            .distinct()
        )
        user_created_paginator = Paginator(user_created_sources, 6)
        user_created_page_num = self.request.GET.get("page2")
        user_created_page_obj = user_created_paginator.get_page(user_created_page_num)

        context["user_created_sources_page_obj"] = user_created_page_obj
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
