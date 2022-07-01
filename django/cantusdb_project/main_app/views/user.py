from urllib import request
from django.views.generic import DetailView
from django.contrib.auth import get_user_model
from main_app.models import Source
from django.views.generic import ListView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q
from django.core.paginator import Paginator
from django.contrib.auth.views import LogoutView
from django.contrib import messages
from extra_views import SearchableListMixin

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
        ).order_by("title")
        
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        user_created_sources = Source.objects.filter(created_by=self.request.user)
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

class UserListView(LoginRequiredMixin, SearchableListMixin, ListView):
    """Searchable List view for User model

    Accessed by /users/

    When passed a ``?q=<query>`` argument in the GET request, it will filter users
    based on the fields defined in ``search_fields`` with the ``icontains`` lookup
    """

    model = get_user_model()
    search_fields = ["first_name", "last_name", "institution", "city", "country"]
    paginate_by = 100
    template_name = "user_list.html"
    context_object_name = "users"
