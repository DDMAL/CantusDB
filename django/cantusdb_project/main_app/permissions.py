from typing import Optional, Union
from django.db.models import Q
from django.core.exceptions import PermissionDenied
from django.contrib.auth.models import AnonymousUser
from main_app.models import (
    Source,
    Chant,
    Sequence,
)
from users.models import User


def user_can_edit_chants_in_source(
    user: Union[User, AnonymousUser], source: Optional[Source]
) -> bool:
    """
    Checks if the user can edit Chants in a given Source.
    Used in ChantDetail, ChantList, ChantCreate, ChantDelete, ChantEdit,
    ChantEditSyllabification, and SourceDetail views.
    """
    if user.is_superuser:
        return True

    if user.is_anonymous or source is None:
        return False

    source_id = source.id
    user_is_assigned_to_source = user.sources_user_can_edit.filter(  # type: ignore[attr-defined]
        id=source_id
    ).exists()

    user_groups = user.groups.all().values_list("name", flat=True)
    user_is_pm = "project manager" in user_groups
    user_is_editor = "editor" in user_groups
    user_is_contributor = "contributor" in user_groups

    return (
        user_is_pm
        or (user_is_editor and user_is_assigned_to_source)
        or (user_is_editor and source.created_by == user)
        or (user_is_contributor and user_is_assigned_to_source)
        or (user_is_contributor and source.created_by == user)
    )


def user_can_proofread_chant(user: User, chant: Chant) -> bool:
    """
    Checks if the user can access the proofreading page of a given Source.
    Used in SourceEditChantsView.
    """
    if user.is_superuser:
        return True

    if user.is_anonymous:
        return False

    source = chant.source
    return user_can_proofread_source(user, source)


def user_can_proofread_source(user: Union[User, AnonymousUser], source: Source) -> bool:
    """
    Checks if the user can access the proofreading page of a given Source.
    Used in SourceBrowseChantsView.
    """
    if user.is_superuser:
        return True

    if user.is_anonymous:
        return False

    source_id = source.id
    user_is_assigned_to_source: bool = user.sources_user_can_edit.filter(  # type: ignore[attr-defined]
        id=source_id
    ).exists()

    user_groups = user.groups.all().values_list("name", flat=True)
    user_is_pm: bool = "project manager" in user_groups
    user_is_editor: bool = "editor" in user_groups

    return user_is_pm or (user_is_editor and user_is_assigned_to_source)


def user_can_view_source(user: Union[User, AnonymousUser], source: Source) -> bool:
    """
    Checks if the user can view an unpublished Source on the site.
    Used in ChantDetail, SequenceDetail, and SourceDetail views.
    """
    return source.published or user.is_authenticated


def user_can_view_chant(user: User, chant: Chant) -> bool:
    """
    Checks if the user can view a Chant belonging to an unpublished Source on the site.
    Used in ChantDetail, SequenceDetail, and SourceDetail views.
    """
    source = chant.source
    return (source is not None) and (source.published or user.is_authenticated)


def user_can_view_sequence(user: User, sequence: Sequence) -> bool:
    """
    Checks if the user can view a Sequence belonging to an unpublished Source on the site.
    Used in ChantDetail, SequenceDetail, and SourceDetail views.
    """
    source = sequence.source
    return (source is not None) and (source.published or user.is_authenticated)


def user_can_edit_sequences(user: User, sequence: Sequence) -> bool:
    """
    Checks if the user has permission to edit a Sequence object.
    Used in SequenceDetail and SequenceEdit views.
    """
    if user.is_superuser:
        return True

    source = sequence.source
    if user.is_anonymous or source is None:
        return False

    source_id = source.id
    user_is_assigned_to_source = user.sources_user_can_edit.filter(  # type: ignore[attr-defined]
        id=source_id
    ).exists()

    user_groups = user.groups.all().values_list("name", flat=True)
    user_is_pm = "project manager" in user_groups
    user_is_editor = "editor" in user_groups
    user_is_contributor = "contributor" in user_groups

    return (
        user_is_pm
        or (user_is_editor and user_is_assigned_to_source)
        or (user_is_editor and source.created_by == user)
        or (user_is_contributor and user_is_assigned_to_source)
        or (user_is_contributor and source.created_by == user)
    )


def user_can_create_sources(user: User) -> bool:
    """
    Checks if the user has permission to create a Source object.
    Used in SourceCreateView.
    """

    return user.groups.filter(
        Q(name="project manager") | Q(name="editor") | Q(name="contributor")
    ).exists()


def user_can_edit_source(user: Union[User, AnonymousUser], source: Source) -> bool:
    """
    Checks if the user has permission to edit a Source object.
    Used in SourceDetail, SourceEdit, and SourceDelete views.
    """
    if user.is_anonymous:
        return False
    source_id = source.id
    assigned_to_source = user.sources_user_can_edit.filter(  # type: ignore[attr-defined]
        id=source_id
    )

    user_groups = user.groups.all().values_list("name", flat=True)
    is_project_manager: bool = "project manager" in user_groups
    is_editor: bool = "editor" in user_groups
    is_contributor: bool = "contributor" in user_groups

    return (
        is_project_manager
        or (is_editor and assigned_to_source)
        or (is_editor and source.created_by == user)
        or (is_contributor and source.created_by == user)
    )


def user_can_view_user_detail(viewing_user: User, user: User) -> bool:
    """
    Checks if the user can view the user detail pages of regular users in
    the database or just indexers. Used in UserDetailView.
    """
    return viewing_user.is_authenticated or user.is_indexer


def user_can_manage_source_editors(user: Union[User, AnonymousUser]) -> bool:
    """
    Checks if the user has permission to change the editors assigned to a Source.
    Used in SourceDetailView.
    """
    return (
        user.is_superuser
        or user.is_staff
        or user.groups.filter(name="project manager").exists()
    )


def user_is_project_manager(user: User) -> bool:
    """
    A callback function that will be called by the user_passes_test decorator of content_overview.

    Takes in a logged-in user as an argument.
    Returns True if they are in a "project manager" group, raises PermissionDenied otherwise.
    """
    if user.groups.filter(name="project manager").exists():
        return True
    raise PermissionDenied
