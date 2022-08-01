from django.urls import path
from articles.views import ArticleDetailView
from articles.views import ArticleListView

urlpatterns = [
    path("articles/", ArticleListView.as_view(), name="article-list"),
    path("article/<int:pk>", ArticleDetailView.as_view(), name="article-detail"),
]