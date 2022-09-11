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

class UserDetailView(DetailView):
    """Detail view for User model

    Accessed by /users/<pk>
    """

    model = get_user_model()
    context_object_name = "user"
    template_name = "user_detail.html"

class UserSourceListView(LoginRequiredMixin, ListView):
    model = Source
    context_object_name = "sources"
    template_name = "user_source_list.html"
    paginate_by = 100

    def get_queryset(self):
        return Source.objects.filter(
            Q(current_editors=self.request.user)
            | Q(created_by=self.request.user)
            # | Q(inventoried_by=self.request.user)
            # | Q(full_text_entered_by=self.request.user)
            # | Q(melodies_entered_by=self.request.user)
            # | Q(proofreaders=self.request.user)
            # | Q(other_editors=self.request.user) 
        ).order_by("-date_created").distinct()
        
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        user_created_sources = Source.objects.filter(created_by=self.request.user).order_by("-date_created").distinct()
        paginator = Paginator(user_created_sources, 10)
        page_number = self.request.GET.get('page2')
        page_obj = paginator.get_page(page_number)

        context["user_created_sources_page_obj"] = page_obj
        return context

class CustomLogoutView(LogoutView):
    def get_next_page(self):
        next_page = super().get_next_page()
        messages.success(
            self.request, 
            'You have successfully logged out!'
        )
        return next_page

class UserListView(SearchableListMixin, ListView):
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

class IndexerListView(UserListView):
    """A list of User objects shown to the public

    This view replaces the indexer list view on the old Cantus. 
    The indexers are considered a subset of all User objects, the subset shown to the public.
    This includes the User objects corresponding to Indexer objects on the old Cantus.   
    When passed a `?q=<query>` argument in the GET request, it will filter users
    based on the fields defined in `search_fields` with the `icontains` lookup.

    Accessed by /indexers/
    """
    template_name = "indexer_list.html"
    context_object_name = "indexers"

    def get_queryset(self):
        all_users = super().get_queryset()
        indexers = all_users.filter(show_in_list=True)
        # indexers = indexers.annotate(
        #     source_count=Count("inventoried_sources", filter=Q(sources_inventoried__published=True))
        # )
        return indexers

class CustomLoginView(LoginView):
    def form_valid(self, form):
        auth_login(self.request, form.get_user())
        # if the user has not yet changed the initial password that was assigned to them,
        # redirect them to the change-password page everytime they log in
        # with warning messages prompting them to change their password
        if form.get_user().changed_initial_password == False:
            return HttpResponseRedirect(reverse("change-password"))
        return HttpResponseRedirect(self.get_success_url())