from django.urls import path, include
from main_app.views import *
from main_app.views import views
from main_app.views.source import SourceCreateView, SourceEditView
from main_app.views.chant import ChantEditVolpianoView
from django.contrib.auth import views as auth_views
from main_app.views.user import UserDetailView, UserSourceListView

urlpatterns = [
    path("indexers/", IndexerListView.as_view(), name="indexer-list"),
    path("indexer/<int:pk>", IndexerDetailView.as_view(), name="indexer-detail"),
    path("feasts/", FeastListView.as_view(), name="feast-list"),
    path("feast/<int:pk>", FeastDetailView.as_view(), name="feast-detail"),
    path("genres/", GenreListView.as_view(), name="genre-list"),
    path("genre/<int:pk>", GenreDetailView.as_view(), name="genre-detail"),
    path("offices/", OfficeListView.as_view(), name="office-list"),
    path("office/<int:pk>", OfficeDetailView.as_view(), name="office-detail"),
    path("sources/", SourceListView.as_view(), name="source-list"),
    path("source/<int:pk>", SourceDetailView.as_view(), name="source-detail"),
    path("chants/", ChantListView.as_view(), name="chant-list"),
    path("chant/<int:pk>", ChantDetailView.as_view(), name="chant-detail"),
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
    path("sequence/<int:pk>", SequenceDetailView.as_view(), name="sequence-detail",),
    path(
        "id/<str:cantus_id>", ChantByCantusIDView.as_view(), name="chant-by-cantus-id"
    ),
    path("chant-delete/<int:pk>", ChantDeleteView.as_view(), name="chant-delete"),
    path("ci-search/<str:search_term>", CISearchView.as_view(), name="ci-search"),
    path("content-statistics", views.items_count, name="items-count"),
    path(
        "ajax/concordance/<str:cantus_id>",
        views.ajax_concordance_list,
        name="ajax_concordance",
    ),
    path("ajax/melody/<str:cantus_id>", views.ajax_melody_list, name="ajax-melody"),
    path("ajax/melody-search/", views.ajax_melody_search, name="ajax-melody-search",),
    path("csv/<str:source_id>", views.csv_export, name="csv-export"),
    path(
        "json-melody/<str:cantus_id>",
        views.json_melody_export,
        name="json-melody-export",
    ),
    path("index/", FullIndexView.as_view(), name="chant-index"),
    path("contact/", views.contact_us, name="contact"),
    path(
        "ajax/search-bar/<str:search_term>",
        views.ajax_search_bar,
        name="ajax-search-bar",
    ),
    path("json-sources/", views.json_sources_export, name="json-sources-export"),
    path("json-node/<str:id>", views.json_node_export, name="json-node-export"),
    path("json-nextchants/<str:cantus_id>", views.json_nextchants, name="json-nextchants"),
    path(
        "source-create/", 
        SourceCreateView.as_view(), 
        name="source-create"
    ),
    path(
        "edit-volpiano/<int:source_id>", 
        ChantEditVolpianoView.as_view(), 
        name="source-edit-volpiano"
    ),
    path("users/<int:user_id>", UserDetailView.as_view(), name="user-detail"),
    path("my-sources/", UserSourceListView.as_view(), name="my-sources"),
    path('login/', auth_views.LoginView.as_view(redirect_authenticated_user=True), name="login"),
    path('logout/', views.CustomLogoutView.as_view(), name="logout"),
    path(
        "edit-source/<int:source_id>", 
        SourceEditView.as_view(), 
        name="source-edit"
    ),
]

handler404 = 'main_app.views.views.handle404'
