from django.urls import path

from main_app.views import *
from main_app.views import views

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
    path("melody/", MelodySearchView.as_view(), name="melody-search"),
    path(
        "chant-search-ms/<int:source_pk>",
        ChantSearchMSView.as_view(),
        name="chant-search-ms",
    ),
    path(
        "chant-create/<int:source_pk>", ChantCreateView.as_view(), name="chant-create"
    ),
    path("chant-update/<int:pk>", ChantUpdateView.as_view(), name="chant-update"),
    path("sequences/", SequenceListView.as_view(), name="sequence-list"),
    path("sequences/<int:pk>", SequenceDetailView.as_view(), name="sequence-detail",),
    path(
        "id/<str:cantus_id>", ChantByCantusIDView.as_view(), name="chant-by-cantus-id"
    ),
    path("chants/<int:pk>/delete/", ChantDeleteView.as_view(), name="chant-delete"),
    path("ci-search/<str:search_term>", CISearchView.as_view(), name="ci-search"),
    path("content-statistics", views.items_count, name="items-count"),
    path(
        "ajax/concordance/<str:cantus_id>",
        views.ajax_concordance_list,
        name="ajax_concordance",
    ),
    path("ajax/melody/<str:cantus_id>", views.ajax_melody_list, name="ajax_melody"),
    path("ajax/melody-search/", views.ajax_melody_search, name="ajax_melody_search",),
    path("csv/<str:source_id>", views.csv_export, name="csv-export"),
    path(
        "json-melody/<str:cantus_id>",
        views.json_melody_export,
        name="json_melody_export",
    ),
    path("index/", FullIndexView.as_view(), name="chant-index"),
    path("contact/", views.contact_us, name="contact"),
    path(
        "ajax/search-bar/<str:search_term>",
        views.ajax_search_bar,
        name="ajax_search_bar",
    ),
]
