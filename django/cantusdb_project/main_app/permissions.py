from typing import Optional, Union, Any, Dict
from functools import cached_property
from collections.abc import Callable
from datetime import date


from django.contrib.auth.models import AnonymousUser
from django.contrib.auth.mixins import AccessMixin
from django.core.exceptions import ImproperlyConfigured
from django.http import HttpRequest, HttpResponse
from django.db.models import Q, QuerySet

from main_app.models import Source
from users.models import User


def get_user_groups(user: Union[User, AnonymousUser]) -> Dict[str, Optional[date]]:
    """
    Gets a dictionary of user groups and the expiration date
    of the user's membership in the group.

    :param user: User or AnonymousUser. If user is an AnonymousUser,
                an empty dictionary is returned.

    :return: Dictionary of user groups and expiration dates in the form
                {group_name: expiration_date}
    """
    if user.is_anonymous:
        return {}
    groups_set = user.groups_new.all().values_list(
        "name", "groupmembership__expiration"
    )
    return {group[0]: group[1] for group in groups_set}


def get_user_assigned_sources(user: Union[User, AnonymousUser]) -> QuerySet[Source]:
    """
    Get a QuerySet of sources that the user is assigned to.
    If the user is anonymous, an empty QuerySet is returned.

    :param user: User or AnonymousUser.

    :return: QuerySet of sources that the user is assigned to.
    """
    if user.is_anonymous:
        return Source.objects.none()
    assigned_sources: QuerySet[Source] = user.sources_user_can_edit.all()
    return assigned_sources


def user_group_valid(group: str, user_groups: Dict[str, Optional[date]]) -> bool:
    """
    Returns True if the user is a member of the group and the
    membership has not expired.

    :param group: Name of the group.
    :param user_groups: Dictionary of user groups and expiration dates (as retuned by
                    get_user_groups()).

    :return: True if the user is a member of the group and the
            membership has not expired, False otherwise.
    """
    if group not in user_groups:
        return False
    expiration = user_groups[group]
    if expiration is not None and expiration < date.today():
        return False
    return True


class CustomAccessMixin(AccessMixin):
    """
    A custom mixin for class-based views to manage access permissions.
    The mixin relies on the fact that in CantusDB, permissions to access
    views are based on a user's group membership and the user's assignment
    to sources. Access to views of non-Source objects (eg. Chants, Sequences)
    is nontheless based on the user's assignment to the relevant Source.

    The mixin overrides the setup and dispatch methods of a view to
    initialize the following attributes:
    - user: The user accessing the view.
    - src_perm_cache: A dictionary to cache the results of checks for
        whether a given user is assigned to a source.

    Views inheriting from this mixin must implement a test_func method
    that returns True if the user is allowed to access the view and False
    otherwise. If any user is allowed to access the view, the inheriting
    view must set test_req to False. This will skip the test_func check
    and allow all users to access the view. When superuser's access a view,
    the test_func method is not called, and the user is always allowed
    access.

    The mixin also overrides the get_object method to cache the object
    in the view's object attribute. Some subclassing views (eg. ListView)
    will not use this method.

    The mixin also provides the following properties:
    - user_groups: A dictionary of the user's groups and their expiration dates.
    - user_is_editor: True if the user is a member of the "editor" group
        and the membership has not expired. A superuser is always considered
        an editor.
    - user_is_global_viewer: True if the user is a member of the "global viewer" group
        and the membership has not expired. A superuser is always considered
        a global viewer.
    - user_assigned_sources: A QuerySet of sources that the user is assigned to.
    - published_and_assigned_sources: A QuerySet of sources that the user can view
        (either because the source is published or the user is assigned to it).
    """

    src_perm_cache: Dict[int, bool]
    test_req = True
    test_func: Optional[Callable[[], bool]] = None

    def setup(self, request: HttpRequest, *args: Any, **kwargs: Any) -> None:
        """
        Overrides the default setup method to initialize the user
        and the source permission cache. This method is called
        before the dispatch method in generic views.
        """
        super().setup(request, *args, **kwargs)
        self.user = request.user
        self.src_perm_cache = {}

    def dispatch(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        """
        Overrides the default dispatch method to check if the user
        is allowed to access the view. Follows the logic of Django's
        built-in UserPassesTestMixin.
        """
        user_test_result = self.run_test_func()
        if not user_test_result:
            return self.handle_no_permission()
        return super().dispatch(request, *args, **kwargs)

    def get_object(self, queryset=None):
        """
        Overrides the default get_object method to cache the object
        in the view's object attribute. This way, we can use the
        object to check for permissions (before the object is usually
        available in the view) without duplicating the query.
        """
        if hasattr(self, "object"):
            return self.object
        obj = super().get_object(queryset)
        self.object = obj
        return obj

    def user_assigned_to_source(self, source: Source) -> bool:
        """
        Returns True if the user is  explicitly assigned to a source
        or is a superuser. Caches the lookup in the view's src_perm_cache
        attribute to avoid repeated database lookups.

        :param source: Source object to check if the user is assigned to.

        :return: True if the user is assigned to the source, False otherwise.
        """
        if self.user.is_superuser:
            return True
        if self.src_perm_cache.get(source.id) is not None:
            return self.src_perm_cache.get(source.id)
        return self.check_user_assignment(source)

    def user_created_source(self, source: Source) -> bool:
        if source.created_by == self.user:
            return True
        return False

    def check_user_assignment(self, source: Source) -> bool:
        """
        Runs a database query to check if the user is assigned to a source.
        This method is called by user_assigned_to_source() if the result
        is not already cached.

        :param source: Source object to check if the user is assigned to.
        :return: True if the user is assigned to the source, False otherwise.
        """
        check_result = self.user_assigned_sources.contains(source)
        self.src_perm_cache[source.id] = check_result
        return check_result

    def run_test_func(self) -> bool:
        """
        Run's the test function (test_func) implemented by the views
        inheriting from this class.

        If the inheriting view sets test_req to False, no test function
        is required.

        Otherwise, the inheriting view must implement a test_func method,
        which is run by this method and whose result is returned.
        """
        if self.test_req and not callable(self.test_func):
            raise ImproperlyConfigured(
                (
                    f"{self.__class__.__name__} must implement a "
                    "test_func method or set test_req to False."
                )
            )
        if not self.test_req:
            return True
        return self.test_func()

    @cached_property
    def user_groups(self) -> Dict[str, Optional[date]]:
        """
        Returns a user's groups. See get_user_groups.
        """
        return get_user_groups(self.user)

    @cached_property
    def user_is_editor(self) -> bool:
        """
        Returns True if user has unexpired membership in the "editor" group.
        """
        return self.user.is_superuser or user_group_valid("editor", self.user_groups)

    @cached_property
    def user_is_global_viewer(self) -> bool:
        """
        Returns True if user has unexpired membership in the "global viewer" group.
        """
        return self.user.is_superuser or user_group_valid(
            "global viewer", self.user_groups
        )

    @cached_property
    def user_assigned_sources(self) -> QuerySet[Source]:
        """
        Returns a QuerySet of sources that the user is assigned to.
        If the user is a superuser, all sources are returned.
        Otherwise, only sources to which the user is assigned are returned.
        """
        return get_user_assigned_sources(self.user)

    @cached_property
    def published_and_assigned_sources(self) -> QuerySet[Source]:
        """
        Returns a QuerySet of sources that the user can view.
        If the user is a superuser or a global viewer, all sources are returned.
        Otherwise, published sources and any sources to which the user is assigned
        are returned. For unauthenticated users, only published sources are returned.
        """
        published_sources = Source.objects.filter(published=True)
        return published_sources | self.user_assigned_sources


def get_sources_visible_to_user(view_function):
    """
    Decorator to restrict access of a function-based view to a subset
    of sources. Accessible sources include published sources, sources to which
    the user is added as an editor, and sources created by the user. Superusers
    are given access to all sources.

    This queryset of sources if passed to the view function as a keyword argument
    `sources_visible_to_user`.
    """

    def wrapper(request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        user_groups = get_user_groups(request.user)
        user_is_global_viewer = user_group_valid("global viewer", user_groups)
        if request.user.is_superuser or user_is_global_viewer:
            sources_visible_to_user = Source.objects.all()
        else:
            user_assigned_sources = get_user_assigned_sources(request.user)
            sources_visible_to_user = Source.objects.filter(
                Q(id__in=user_assigned_sources) | Q(published=True),
            )
        return view_function(
            request,
            *args,
            sources_visible_to_user=sources_visible_to_user,
            **kwargs,
        )

    return wrapper
