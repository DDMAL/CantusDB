from django.urls import include, path
from django.conf import settings
from django.contrib.auth.views import (
    LoginView,
    PasswordResetView,
    PasswordResetDoneView,
    PasswordResetConfirmView,
    PasswordResetCompleteView,
)
from main_app.views import views
from main_app.views import redirect
from main_app.views.century import (
    CenturyDetailView,
)
from main_app.views.chant import (
    ChantByCantusIDView,
    ChantCreateView,
    ChantDeleteView,
    ChantDetailView,
    ChantEditSyllabificationView,
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
    SourceBrowseChantsView,
    SourceCreateView,
    SourceDetailView,
    SourceEditView,
    SourceListView,
    SourceDeleteView,
    SourceInventoryView,
)
from main_app.views.user import (
    CustomLogoutView,
    IndexerListView,
    UserDetailView,
    UserListView,
    UserSourceListView,
)
from main_app.views.autocomplete import (
    CurrentEditorsAutocomplete,
    AllUsersAutocomplete,
    CenturyAutocomplete,
    FeastAutocomplete,
    OfficeAutocomplete,
    GenreAutocomplete,
    DifferentiaAutocomplete,
    ProvenanceAutocomplete,
    ProofreadByAutocomplete,
    HoldingAutocomplete,
)
from main_app.views.auth import change_password

urlpatterns = [
    path(
        "contact/",
        views.contact,
        name="contact",
    ),
    # login/logout/user
    path(
        "login/",
        LoginView.as_view(redirect_authenticated_user=True),
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
        change_password,
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
        "chant/<int:pk>/delete",
        ChantDeleteView.as_view(),
        name="chant-delete",
    ),
    path(
        "edit-chants/<int:source_id>",
        SourceEditChantsView.as_view(),
        name="source-edit-chants",
    ),
    path(
        "edit-syllabification/<int:chant_id>",
        ChantEditSyllabificationView.as_view(),
        name="source-edit-syllabification",
    ),
    path(
        "chants/",
        redirect.redirect_chants,
        name="redirect-chants",
    ),  # /chants/?source={source id}
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
    path(
        "genre/",
        redirect.redirect_genre,
        name="redirect-genre",
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
    path(
        "office/",
        redirect.redirect_office,
        name="redirect-office",
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
        "source/<int:source_id>/chants/",
        SourceBrowseChantsView.as_view(),
        name="browse-chants",
    ),
    path(
        "source/<int:source_id>/inventory/",
        SourceInventoryView.as_view(),
        name="source-inventory",
    ),
    path(
        "index/",
        redirect.redirect_source_inventory,
        name="redirect-source-inventory",
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
    path(
        "source/<int:pk>/delete",
        SourceDeleteView.as_view(),
        name="source-delete",
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
    # JSON APIs for returning data on individual objects in the database
    path(
        "json-node/<int:id>",
        views.json_node_export,
        name="json-node-export",
    ),
    path(
        "notation/<int:id>/json",
        views.notation_json_export,
        name="notation-json-export",
    ),
    path(
        "provenance/<int:id>/json",
        views.provenance_json_export,
        name="provenance-json-export",
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
        "search/",
        redirect.redirect_search,
        name="redirect-search",
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
        redirect.csv_export_redirect_from_old_path,
        name="csv-export-old-path",
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
        redirect.redirect_node_url,
        name="redirect-node-url",
    ),
    # /indexer/ url redirects
    path(
        "indexer/<int:pk>",
        redirect.redirect_indexer,
        name="redirect-indexer",
    ),
    # links to APIs that list URLs of all pages that live in the database
    path(
        "articles-list/",
        views.articles_list_export,
        name="articles-list-export",
    ),
    path(
        "flatpages-list/",
        views.flatpages_list_export,
        name="flatpages-list-export",
    ),
    # redirects for static files present on OldCantus
    path(
        "sites/default/files/documents/1. Quick Guide to Liturgy.pdf",
        redirect.redirect_documents,
        name="redirect-quick-guide-to-liturgy",
    ),
    path(
        "sites/default/files/documents/2. Volpiano Protocols.pdf",
        redirect.redirect_documents,
        name="redirect-volpiano-protocols",
    ),
    path(
        "sites/default/files/documents/3. Volpiano Neumes for Review.docx",
        redirect.redirect_documents,
        name="redirect-volpiano-neumes-for-review",
    ),
    path(
        "sites/default/files/documents/4. Volpiano Neume Protocols.pdf",
        redirect.redirect_documents,
        name="redirect-volpiano-neume-protocols",
    ),
    path(
        "sites/default/files/documents/5. Volpiano Editing Guidelines.pdf",
        redirect.redirect_documents,
        name="redirect-volpiano-editing-guidelines",
    ),
    path(
        "sites/default/files/documents/7. Guide to Graduals.pdf",
        redirect.redirect_documents,
        name="redirect-guide-to-graduals",
    ),
    path(
        "sites/default/files/HOW TO - manuscript descriptions-Nov6-20.pdf",
        redirect.redirect_documents,
        name="redirect-how-to-manuscript-descriptions",
    ),
    path(
        "current-editors-autocomplete/",
        CurrentEditorsAutocomplete.as_view(),
        name="current-editors-autocomplete",
    ),
    path(
        "all-users-autocomplete/",
        AllUsersAutocomplete.as_view(),
        name="all-users-autocomplete",
    ),
    path(
        "century-autocomplete/",
        CenturyAutocomplete.as_view(),
        name="century-autocomplete",
    ),
    path(
        "feast-autocomplete/",
        FeastAutocomplete.as_view(),
        name="feast-autocomplete",
    ),
    path(
        "proofread-by-autocomplete/",
        ProofreadByAutocomplete.as_view(),
        name="proofread-by-autocomplete",
    ),
    path(
        "holding-autocomplete",
        HoldingAutocomplete.as_view(),
        name="holding-autocomplete",
    ),
    path(
        "provenance-autocomplete/",
        ProvenanceAutocomplete.as_view(),
        name="provenance-autocomplete",
    ),
    path(
        "office-autocomplete/",
        OfficeAutocomplete.as_view(),
        name="office-autocomplete",
    ),
    path(
        "genre-autocomplete/",
        GenreAutocomplete.as_view(),
        name="genre-autocomplete",
    ),
    path(
        "differentia-autocomplete/",
        DifferentiaAutocomplete.as_view(),
        name="differentia-autocomplete",
    ),
]

if settings.DEBUG:
    import debug_toolbar

    urlpatterns.append(path("__debug__/", include(debug_toolbar.urls)))
