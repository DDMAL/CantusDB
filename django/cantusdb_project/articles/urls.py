from django.urls import path
from articles.views import (
    ArticleDetailView,
    ArticleListView,
    article_list_redirect_from_old_path,
)

urlpatterns = [
    path("articles/", ArticleListView.as_view(), name="article-list"),
    path("article/<int:pk>", ArticleDetailView.as_view(), name="article-detail"),
    path("news/", article_list_redirect_from_old_path),
]
