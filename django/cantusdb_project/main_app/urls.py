from django.urls import path
from main_app.views import IndexerDetailView
from main_app.views import IndexerListView
from main_app.views import FeastListView
from main_app.views import FeastDetailView
from main_app.views import GenreDetailView
from main_app.views import GenreListView
from main_app.views import OfficeListView
from main_app.views import OfficeDetailView


urlpatterns = [
    path("indexers/", IndexerListView.as_view(), name="indexer-list"),
    path("indexers/<int:pk>", IndexerDetailView.as_view(), name="indexer-detail"),
    path("feasts/", FeastListView.as_view(), name="feast-list"),
    path("feasts/<int:pk>", FeastDetailView.as_view(), name="feast-detail"),
    path("genres/", GenreListView.as_view(), name="genre-list"),
    path("genres/<int:pk>", GenreDetailView.as_view(), name="genre-detail"),
    path("offices/", OfficeListView.as_view(), name="office-list"),
    path("offices/<int:pk>", OfficeDetailView.as_view(), name="office-detail"),
]
