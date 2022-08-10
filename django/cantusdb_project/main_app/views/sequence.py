from django.views.generic import DetailView, ListView, UpdateView
from main_app.models import Sequence
from django.db.models import Q
from main_app.forms import SequenceEditForm
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.contrib.auth.mixins import UserPassesTestMixin
from django.core.exceptions import PermissionDenied
from django.http import Http404



class SequenceDetailView(DetailView):
    """
    Displays a single Sequence object. Accessed with ``sequences/<int:pk>``
    """

    model = Sequence
    context_object_name = "sequence"
    template_name = "sequence_detail.html"

    def get_context_data(self, **kwargs):

        # if the sequence's source isn't published, only logged-in users should be able to view the sequence's detail page
        sequence = self.get_object()
        source = sequence.source
        if (source.published is False) and (not self.request.user.is_authenticated):
            raise PermissionDenied()
        
        context = super().get_context_data(**kwargs)
        context["concordances"] = Sequence.objects.filter(
            cantus_id=self.get_object().cantus_id
        ).order_by("siglum")
        return context


class SequenceListView(ListView):
    """
    Displays a list of Sequence objects. Accessed with ``sequences/``
    """

    model = Sequence
    paginate_by = 100
    context_object_name = "sequences"
    template_name = "sequence_list.html"

    def get_queryset(self):
        queryset = super().get_queryset()
        q_obj_filter = Q(source__published=True)

        if self.request.GET.get("incipit"):
            incipit = self.request.GET.get("incipit")
            q_obj_filter &= Q(incipit__icontains=incipit)
        if self.request.GET.get("siglum"):
            siglum = self.request.GET.get("siglum")
            q_obj_filter &= Q(siglum__icontains=siglum)
        if self.request.GET.get("cantus_id"):
            cantus_id = self.request.GET.get("cantus_id")
            q_obj_filter &= Q(cantus_id__icontains=cantus_id)

        return queryset.filter(q_obj_filter).order_by("siglum", "sequence")

class SequenceEditView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    template_name = "sequence_edit.html"
    model = Sequence
    form_class = SequenceEditForm
    pk_url_kwarg = "sequence_id"

    def form_valid(self, form):
        messages.success(
            self.request,
            "Sequence updated successfully!",
        )
        return super().form_valid(form)

    def test_func(self):
        user = self.request.user
        # checks if the user is a project manager (they should have the privilege to edit any sequence)
        is_project_manager = user.groups.filter(name="project manager").exists()

        if is_project_manager:
            return True
        else:
            return False
