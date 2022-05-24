from django.views.generic import DetailView
from django.contrib.auth import get_user_model

class UserDetailView(DetailView):
    """Detail view for User model

    Accessed by /users/<user_id>
    """

    model = get_user_model()
    context_object_name = "user"
    template_name = "user_detail.html"
    pk_url_kwarg = 'user_id'	
