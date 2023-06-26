from django.urls import reverse
from django.db.models.aggregates import Count
from django.views.generic import DetailView
from django.contrib.auth import get_user_model, login as auth_login
from main_app.models import Source
from django.views.generic import ListView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q
from django.core.paginator import Paginator
from django.contrib.auth.views import LogoutView, LoginView
from django.contrib import messages
from extra_views import SearchableListMixin
from django.http import HttpResponseRedirect
from django.core.exceptions import PermissionDenied


class UserDetailView(DetailView):
    """Detail view for User model

    Accessed by /users/<pk>
    """

    model = get_user_model()
    context_object_name = "user"
    template_name = "user_detail.html"

    def get_context_data(self, **kwargs):
        user = self.get_object()
        # to begin, if the person viewing the site is not logged in,
        # they should only be able to view the detail pages of indexers,
        # and not the detail pages of run-of-the-mill users
        viewing_user = self.request.user
        if not (viewing_user.is_authenticated or user.is_indexer):
            raise PermissionDenied()

        context = super().get_context_data(**kwargs)
        display_unpublished = viewing_user.is_authenticated
        sort_by_siglum = lambda source: source.siglum
        if display_unpublished:
            context["inventoried_sources"] = sorted(
                user.inventoried_sources.all(), key=sort_by_siglum
            )
            context["full_text_sources"] = sorted(
                user.entered_full_text_for_sources.all(), key=sort_by_siglum
            )
            context["melody_sources"] = sorted(
                user.entered_melody_for_sources.all(), key=sort_by_siglum
            )
            context["proofread_sources"] = sorted(
                user.proofread_sources.all(), key=sort_by_siglum
            )
            context["edited_sources"] = sorted(
                user.edited_sources.all(), key=sort_by_siglum
            )
        else:
            context["inventoried_sources"] = sorted(
                user.inventoried_sources.all().filter(published=True),
                key=sort_by_siglum,
            )
            context["full_text_sources"] = sorted(
                user.entered_full_text_for_sources.all().filter(published=True),
                key=sort_by_siglum,
            )
            context["melody_sources"] = sorted(
                user.entered_melody_for_sources.all().filter(published=True),
                key=sort_by_siglum,
            )
            context["proofread_sources"] = sorted(
                user.proofread_sources.all().filter(published=True), key=sort_by_siglum
            )
            context["edited_sources"] = sorted(
                user.edited_sources.all().filter(published=True), key=sort_by_siglum
            )

        return context


class UserSourceListView(LoginRequiredMixin, ListView):
    model = Source
    context_object_name = "sources"
    template_name = "user_source_list.html"
    paginate_by = 100

    def get_queryset(self):
        return (
            Source.objects.filter(
                Q(current_editors=self.request.user)
                | Q(created_by=self.request.user)
                # | Q(inventoried_by=self.request.user)
                # | Q(full_text_entered_by=self.request.user)
                # | Q(melodies_entered_by=self.request.user)
                # | Q(proofreaders=self.request.user)
                # | Q(other_editors=self.request.user)
            )
            .order_by("-date_created")
            .distinct()
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        user_created_sources = (
            Source.objects.filter(created_by=self.request.user)
            .order_by("-date_created")
            .distinct()
        )
        paginator = Paginator(user_created_sources, 10)
        page_number = self.request.GET.get("page2")
        page_obj = paginator.get_page(page_number)

        context["user_created_sources_page_obj"] = page_obj
        return context


class CustomLogoutView(LogoutView):
    def get_next_page(self):
        next_page = super().get_next_page()
        messages.success(self.request, "You have successfully logged out!")
        return next_page


class UserListView(LoginRequiredMixin, SearchableListMixin, ListView):
    """A list of all User objects

    This view is equivalent to the user list view on the old Cantus.
    This includes all User objects on the old Cantus.
    When passed a `?q=<query>` argument in the GET request, it will filter users
    based on the fields defined in `search_fields` with the `icontains` lookup.

    Accessed by /users/
    """

    model = get_user_model()
    ordering = "full_name"
    search_fields = ["full_name", "institution", "city", "country"]
    paginate_by = 100
    template_name = "user_list.html"
    context_object_name = "users"


class IndexerListView(SearchableListMixin, ListView):
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

    def get_queryset(self):
        all_users = super().get_queryset()
        indexers = all_users.filter(is_indexer=True)
        display_unpublished = self.request.user.is_authenticated
        if display_unpublished:
            indexers = indexers.annotate(source_count=Count("inventoried_sources"))
            # display those who have at least one source
            return indexers.filter(source_count__gte=1)
        else:
            indexers = indexers.annotate(
                source_count=Count(
                    "inventoried_sources", filter=Q(inventoried_sources__published=True)
                )
            )
            # display those who have at least one published source
            return indexers.filter(source_count__gte=1)


class CustomLoginView(LoginView):
    def form_valid(self, form):
        auth_login(self.request, form.get_user())
        # if the user has not yet changed the initial password that was assigned to them,
        # redirect them to the change-password page everytime they log in
        # with warning messages prompting them to change their password
        if form.get_user().changed_initial_password == False:
            return HttpResponseRedirect(reverse("change-password"))
        return HttpResponseRedirect(self.get_success_url())
