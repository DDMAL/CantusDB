from django.urls import path
from main_app.views import IndexerDetailView
from main_app.views import IndexerListView
from main_app.views import FeastListView
from main_app.views import FeastDetailView

urlpatterns = [
    path("indexers/", IndexerListView.as_view(), name="indexer-list"),
    path("indexers/<int:pk>", IndexerDetailView.as_view(), name="indexer-detail"),
    path("feasts/", FeastListView.as_view(), name="feast-list"),
    path("feasts/<int:pk>", FeastDetailView.as_view(), name="feast-detail"),
]
