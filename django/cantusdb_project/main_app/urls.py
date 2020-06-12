from django.urls import path
from main_app.views import IndexerDetailView
from main_app.views import IndexerListView

urlpatterns = [
    path("indexers/", IndexerListView.as_view(), name="indexer-list"),
    path("indexers/<int:pk>", IndexerDetailView.as_view(), name="indexer-detail"),
]
