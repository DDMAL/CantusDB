from urllib import request
from django.views.generic import DetailView
from django.contrib.auth import get_user_model
from main_app.models import Source
from django.views.generic import ListView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q

class UserDetailView(DetailView):
    """Detail view for User model

    Accessed by /users/<user_id>
    """

    model = get_user_model()
    context_object_name = "user"
    template_name = "user_detail.html"
    pk_url_kwarg = 'user_id'	

class UserSourceListView(LoginRequiredMixin, ListView):
    model = Source
    context_object_name = "sources"
    template_name = "user_source_list.html"

    def get_queryset(self):
        return Source.objects.filter(
            Q(current_editors=self.request.user) 
            # |
            # Q(inventoried_by=self.request.user) |
            # Q(full_text_entered_by=self.request.user) |
            # Q(melodies_entered_by=self.request.user) |
            # Q(proofreaders=self.request.user) |
            # Q(other_editors=self.request.user) 
        ).order_by("title")
