from django.urls import path
from main_app.views import IndexerDetailView
from main_app.views import IndexerListView
from main_app.views import FeastListView
from main_app.views import FeastDetailView
from main_app.views import GenreDetailView
from main_app.views import GenreListView
from main_app.views import OfficeListView
from main_app.views import OfficeDetailView
from main_app.views import SourceListView
from main_app.views import SourceDetailView
from main_app.views import ChantListView
from main_app.views import ChantDetailView
from main_app.views import ChantSearchView
from main_app.views import ChantCreateView
from main_app.views import ChantUpdateView

urlpatterns = [
    path("indexers/", IndexerListView.as_view(), name="indexer-list"),
    path("indexers/<int:pk>", IndexerDetailView.as_view(), name="indexer-detail"),
    path("feasts/", FeastListView.as_view(), name="feast-list"),
    path("feasts/<int:pk>", FeastDetailView.as_view(), name="feast-detail"),
    path("genres/", GenreListView.as_view(), name="genre-list"),
    path("genres/<int:pk>", GenreDetailView.as_view(), name="genre-detail"),
    path("offices/", OfficeListView.as_view(), name="office-list"),
    path("offices/<int:pk>", OfficeDetailView.as_view(), name="office-detail"),
    path("sources/", SourceListView.as_view(), name="source-list"),
    path("sources/<int:pk>", SourceDetailView.as_view(), name="source-detail"),
    path("chants/", ChantListView.as_view(), name="chant-list"),
    path("chants/<int:pk>", ChantDetailView.as_view(), name="chant-detail"),
    path("chant-search/", ChantSearchView.as_view(), name="chant-search"),
    path("chant-create/<int:source_pk>", ChantCreateView.as_view(), name="chant-create"),
    path("chant-update/<int:pk>", ChantUpdateView.as_view(), name="chant-update"),
]
