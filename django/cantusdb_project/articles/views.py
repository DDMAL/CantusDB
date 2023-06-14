from django.shortcuts import render, redirect
from django.urls.base import reverse
from django.views.generic import DetailView, ListView
from articles.models import Article


class ArticleDetailView(DetailView):
    model = Article
    context_object_name = "article"
    template_name = "article_detail.html"


class ArticleListView(ListView):
    model = Article
    queryset = Article.objects.order_by("-date_created")
    paginate_by = 10
    context_object_name = "articles"
    template_name = "article_list.html"


def article_list_redirect_from_old_path(request):
    return redirect(reverse("article-list"))
