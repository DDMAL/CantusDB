from django.urls import include, path, reverse
from django.contrib.auth.views import (
    PasswordResetView,
    PasswordResetDoneView,
    PasswordResetConfirmView,
    PasswordResetCompleteView,
)
from main_app.views import views
import debug_toolbar
from main_app.views.century import (
    CenturyDetailView,
)
from main_app.views.chant import (
    ChantByCantusIDView,
    ChantCreateView,
    ChantDeleteView,
    ChantDetailView,
    ChantEditSyllabificationView,
    ChantIndexView,
    ChantListView,
    ChantProofreadView,
    ChantSearchView,
    ChantSearchMSView,
    CISearchView,
    MelodySearchView,
    SourceEditChantsView,
)
from main_app.views.feast import (
    FeastDetailView,
    FeastListView,
)
from main_app.views.genre import (
    GenreDetailView,
    GenreListView,
)
from main_app.views.notation import (
    NotationDetailView,
)
from main_app.views.office import (
    OfficeListView,
    OfficeDetailView,
)
from main_app.views.provenance import (
    ProvenanceDetailView,
)
from main_app.views.sequence import (
    SequenceDetailView,
    SequenceEditView,
    SequenceListView,
)
from main_app.views.source import (
    SourceCreateView,
    SourceDetailView,
    SourceEditView,
    SourceListView,
)
from main_app.views.user import (
    CustomLoginView,
    CustomLogoutView,
    IndexerListView,
    UserDetailView,
    UserListView,
    UserSourceListView,
)

urlpatterns = [
    path("__debug__/", include(debug_toolbar.urls)),
    path(
        "contact/",
        views.contact,
        name="contact",
    ),
    # login/logout/user
    path(
        "login/",
        CustomLoginView.as_view(redirect_authenticated_user=True),
        name="login",
    ),
    path(
        "logout/",
        CustomLogoutView.as_view(),
        name="logout",
    ),
    path(
        "my-sources/",
        UserSourceListView.as_view(),
        name="my-sources",
    ),
    path(
        "user/<int:pk>",
        UserDetailView.as_view(),
        name="user-detail",
    ),
    path(
        "users/",
        UserListView.as_view(),
        name="user-list",
    ),
    path(
        "change-password/",
        views.change_password,
        name="change-password",
    ),
    # password reset views
    path(
        # here, user can initiate a request to send a password reset email
        "reset-password/",
        PasswordResetView.as_view(
            template_name="registration/reset_password.html",
            email_template_name="registration/reset_password_email.html",
            success_url="/reset-password-sent/",
        ),
        name="reset_password",
    ),
    path(
        # we display this page once the password reset email has been sent
        "reset-password-sent/",
        PasswordResetDoneView.as_view(
            template_name="registration/reset_password_sent.html",
        ),
        name="reset_password_done",
    ),
    path(
        # here, the user can specify their new password
        "reset/<uidb64>/<token>",
        PasswordResetConfirmView.as_view(
            template_name="registration/reset_password_confirm.html",
            success_url="/reset-password-complete/",
        ),
        name="reset_password_confirm",
    ),
    path(
        # we display this page once a user has completed a password reset
        # depending on whether their attempt was successful, this page either shows
        # a success message or a non-success message.
        "reset-password-complete/",
        PasswordResetCompleteView.as_view(
            template_name="registration/reset_password_complete.html"
        ),
        name="reset_password_complete",
    ),
    # century
    path("century/<int:pk>", CenturyDetailView.as_view(), name="century-detail"),
    # chant
    path(
        "chants/",
        ChantListView.as_view(),
        name="chant-list",
    ),  # /chants/?source={source id}
    path(
        "chant/<int:pk>",
        ChantDetailView.as_view(),
        name="chant-detail",
    ),
    path(
        "chant-search/",
        ChantSearchView.as_view(),
        name="chant-search",
    ),
    path(
        "chant-create/<int:source_pk>",
        ChantCreateView.as_view(),
        name="chant-create",
    ),
    path(
        "id/<str:cantus_id>",
        ChantByCantusIDView.as_view(),
        name="chant-by-cantus-id",
    ),
    path(
        "chant-delete/<int:pk>",
        ChantDeleteView.as_view(),
        name="chant-delete",
    ),
    path(
        "edit-chants/<int:source_id>",
        SourceEditChantsView.as_view(),
        name="source-edit-chants",
    ),
    path(
        "proofread-chant/<int:source_id>",
        ChantProofreadView.as_view(),
        name="chant-proofread",
    ),
    path(
        "edit-syllabification/<int:chant_id>",
        ChantEditSyllabificationView.as_view(),
        name="source-edit-syllabification",
    ),
    path(
        "index/",
        ChantIndexView.as_view(),
        name="chant-index",
    ),  # /index/?source={source id}
    # feast
    path(
        "feasts/",
        FeastListView.as_view(),
        name="feast-list",
    ),
    path(
        "feast/<int:pk>",
        FeastDetailView.as_view(),
        name="feast-detail",
    ),
    # genre
    path(
        "genres/",
        GenreListView.as_view(),
        name="genre-list",
    ),
    path(
        "genre/<int:pk>",
        GenreDetailView.as_view(),
        name="genre-detail",
    ),
    # indexer
    path(
        "indexers/",
        IndexerListView.as_view(),
        name="indexer-list",
    ),
    # notation
    path(
        "notation/<int:pk>",
        NotationDetailView.as_view(),
        name="notation-detail",
    ),
    # office
    path(
        "offices/",
        OfficeListView.as_view(),
        name="office-list",
    ),
    path(
        "office/<int:pk>",
        OfficeDetailView.as_view(),
        name="office-detail",
    ),
    # provenance
    path(
        "provenance/<int:pk>",
        ProvenanceDetailView.as_view(),
        name="provenance-detail",
    ),
    # sequence
    path(
        "sequences/",
        SequenceListView.as_view(),
        name="sequence-list",
    ),
    path(
        "sequence/<int:pk>",
        SequenceDetailView.as_view(),
        name="sequence-detail",
    ),
    path(
        "edit-sequence/<int:sequence_id>",
        SequenceEditView.as_view(),
        name="sequence-edit",
    ),
    # source
    path(
        "sources/",
        SourceListView.as_view(),
        name="source-list",
    ),
    path(
        "source/<int:pk>",
        SourceDetailView.as_view(),
        name="source-detail",
    ),
    path(
        "source-create/",
        SourceCreateView.as_view(),
        name="source-create",
    ),
    path(
        "edit-source/<int:source_id>",
        SourceEditView.as_view(),
        name="source-edit",
    ),
    # melody
    path(
        "melody/",
        MelodySearchView.as_view(),
        name="melody-search",
    ),
    path(
        "ajax/melody/<str:cantus_id>",
        views.ajax_melody_list,
        name="ajax-melody",
    ),
    path(
        "ajax/melody-search/",
        views.ajax_melody_search,
        name="ajax-melody-search",
    ),
    # json api
    path(
        "json-sources/",
        views.json_sources_export,
        name="json-sources-export",
    ),
    path(
        "json-node/<str:id>",
        views.json_node_export,
        name="json-node-export",
    ),
    path(
        "json-nextchants/<str:cantus_id>",
        views.json_nextchants,
        name="json-nextchants",
    ),
    path(
        "json-melody/<str:cantus_id>",
        views.json_melody_export,
        name="json-melody-export",
    ),
    path(
        "json-cid/<str:cantus_id>",
        views.json_cid_export,
        name="json-cid-export",
    ),
    # misc search
    path(
        "searchms/<int:source_pk>",
        ChantSearchMSView.as_view(),
        name="chant-search-ms",
    ),
    path(
        "ci-search/<str:search_term>",
        CISearchView.as_view(),
        name="ci-search",
    ),
    path(
        "ajax/search-bar/<str:search_term>",
        views.ajax_search_bar,
        name="ajax-search-bar",
    ),
    # misc
    path(
        "content-statistics",
        views.items_count,
        name="items-count",
    ),
    path(
        "source/<str:source_id>/csv/",
        views.csv_export,
        name="csv-export",
    ),
    path(
        "sites/default/files/csv/<str:source_id>.csv",
        views.csv_export_redirect_from_old_path,
        name="csv-export-old-path",
    ),
    path(
        "ajax/concordance/<str:cantus_id>",
        views.ajax_concordance_list,
        name="ajax-concordance",
    ),
    # content overview (for project managers)
    path(
        "content-overview/",
        views.content_overview,
        name="content-overview",
    ),
    # /node/ url redirects
    path(
        "node/<int:pk>",
        views.redirect_node_url,
        name="redirect-node-url",
    ),
    # /indexer/ url redirects
    path(
        "indexer/<int:pk>",
        views.redirect_indexer,
        name="redirect-indexer",
    ),
]

handler404 = "main_app.views.views.handle404"
