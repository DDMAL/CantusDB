from django.urls import path

from main_app.views import (
    ChantCreateView,
    ChantDetailView,
    ChantListView,
    ChantSearchView,
    ChantUpdateView,
    FeastDetailView,
    FeastListView,
    GenreDetailView,
    GenreListView,
    IndexerDetailView,
    IndexerListView,
    OfficeDetailView,
    OfficeListView,
    SequenceDetailView,
    SequenceListView,
    SourceDetailView,
    SourceListView,
)

urlpatterns = [
    path("indexers/", IndexerListView.as_view(), name="indexer-list"),
    path(
        "indexers/<int:pk>", IndexerDetailView.as_view(), name="indexer-detail"
    ),
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
    path("chant-create/", ChantCreateView.as_view(), name="chant-create"),
    path(
        "chant-update/<int:pk>", ChantUpdateView.as_view(), name="chant-update"
    ),
    path("sequences/", SequenceListView.as_view(), name="sequence-list"),
    path(
        "sequences/<int:pk>",
        SequenceDetailView.as_view(),
        name="sequence-detail",
    ),
]
