import calendar
from typing import Union, Optional, Any

from django.conf import settings
from django import template
from django.core.paginator import Paginator, Page
from django.db.models import Q
from django.template.defaultfilters import stringfilter
from django.utils.safestring import mark_safe, SafeString
from django.http import HttpRequest, QueryDict
from django.utils.html import format_html_join
from cmarkgfm import github_flavored_markdown_to_html

from articles.models import Article
from main_app.models import Source, BaseModel
from users.models import User

register = template.Library()


@register.simple_tag(takes_context=False)
def recent_articles() -> SafeString:
    """
    Generates a html unordered list of recent articles for display on the homepage

    Used in:
        templates/flatpages/default.html
    """
    articles = Article.objects.order_by("-date_created")[:5]
    list_item_template = (
        '<li style="padding-bottom: 0.5em;">'
        '<a href="{}">{}</a><br><small>{}</small></li>'
    )
    list_items_string = format_html_join(
        sep="",
        format_string=list_item_template,
        args_generator=(
            (a.get_absolute_url(), a.title, a.date_created.strftime("%A %B %-d, %Y"))
            for a in articles
        ),
    )
    recent_articles_string = f"<ul>{list_items_string}</ul>"
    return mark_safe(recent_articles_string)


@register.filter(name="month_to_string")
def month_to_string(value: Optional[Union[str, int]]) -> Optional[Union[str, int]]:
    """
    Converts month number to textual representation, 3 letters (Jan, Mar, etc)

    used in:
        main_app/templates/feast_detail.html
        main_app/templates/feast_list.html
    """
    if isinstance(value, int) and value in range(1, 13):
        return calendar.month_abbr[value]
    return value


@register.simple_tag(takes_context=True)
def url_add_get_params(context: dict[str, Any], **kwargs: str) -> str:
    """
    accounts for the situations where there may be two paginations in one page

    Used in:
        main_app/templates/pagination.html
        main_app/templates/user_source_list.html
    """
    query: QueryDict = context["request"].GET.copy()
    if "page" in kwargs:
        query.pop("page", None)
    if "page2" in kwargs:
        query.pop("page2", None)
    query.update(kwargs)
    return query.urlencode()


@register.simple_tag(takes_context=False)
def source_links() -> SafeString:
    """
    Generates a series of html option tags linking to sources in
    Cantus Database, for display on the homepage

    Used in:
        templates/flatpages/default.html
    """
    sources = (
        Source.objects.filter(
            published=True, segment_m2m__id=settings.CANTUS_SEGMENT_ID
        )
        .select_related("holding_institution")
        .order_by("holding_institution__siglum", "shelfmark")
        .iterator()
    )
    options = format_html_join(
        sep="\n",
        format_string="<option value=source/{0}>{1}</option>",
        args_generator=((source.id, source.short_heading) for source in sources),
    )

    return options


@register.filter(is_safe=True)
def classname(obj: BaseModel) -> str:
    """
    Returns the name of the object's class
    A use-case is: {% if object|classname == "Notation" %}

    Used in:
        main_app/templates/content_overview.html
    """
    return obj.__class__.__name__


@register.filter
def admin_url_name(class_name: str, action: str) -> str:
    """
    Accepts the name of a class in "main_app",
    and an action (either "change" or "delete") as arguments.
    Returns the name of the URL for changing/deleting an
    object in the admin interface.

    Used in:
        main_app/templates/content_overview.html
    """
    class_name = class_name.lower()
    action = action.lower()

    return f"admin:main_app_{class_name}_{action}"


@register.filter(name="has_group")
def has_group(user: User, group_name: str) -> bool:
    """
    Used in:
        templates/base.html
    """
    return user.groups.filter(name=group_name).exists()


@register.filter(name="in_groups")
def in_groups(user: User, groups: str) -> bool:
    """
    Takes a comma-separated string of group names and
    returns True if the user is in those groups.
    """
    grouplist = groups.split(",")
    return user.groups.filter(name__in=grouplist).exists()


@register.filter(name="split")
@stringfilter
def split(value: str, key: str) -> list[str]:
    """
    Returns the value turned into a list.
    """
    return value.split(key)


@register.simple_tag(takes_context=True)
def get_user_source_pagination(context: dict[str, Any]) -> Page[Source]:
    """
    Gets the appropriate `Page` object for the user's sources,
    based on the current page number in the request's GET parameters.
    """
    user_created_sources = (
        Source.objects.filter(
            Q(current_editors=context["user"]) | Q(created_by=context["user"])
        )
        .select_related("holding_institution")
        .order_by("-date_updated")
        .distinct()
        .only(
            "id",
            "holding_institution__id",
            "holding_institution__city",
            "holding_institution__siglum",
            "holding_institution__name",
            "holding_institution__is_private_collector",
            "shelfmark",
        )
    )
    paginator = Paginator(user_created_sources, 6)
    page_number = context["request"].GET.get("page")
    user_sources_page_obj = paginator.get_page(page_number)
    return user_sources_page_obj


@register.simple_tag(takes_context=True)
def get_user_created_source_pagination(context: dict[str, Any]) -> Page[Source]:
    """
    Gets the appropriate `Page` object for the user's created sources,
    based on the current page number in the request's GET parameters.
    """
    user_created_sources = (
        Source.objects.filter(created_by=context["user"])
        .select_related("holding_institution")
        .order_by("-date_created")
        .distinct()
        .only(
            "id",
            "holding_institution__id",
            "holding_institution__city",
            "holding_institution__siglum",
            "holding_institution__name",
            "holding_institution__is_private_collector",
            "shelfmark",
        )
    )
    paginator = Paginator(user_created_sources, 6)
    page_number = context["request"].GET.get("page2")
    user_created_sources_page_obj = paginator.get_page(page_number)
    return user_created_sources_page_obj


@register.inclusion_tag("tag_templates/sortable_header.html")
def sortable_header(
    request: HttpRequest,
    order_attribute: str,
    column_name: Optional[str] = None,
) -> dict[str, Union[str, bool, Optional[str]]]:
    """
    A template tag for use in `ListView` templates or other templates that display
    a table of model instances. This tag generates a table header (<th>) element
    that, when clicked, sorts the table by the specified attribute.

    params:
        context: the current template-rendering context (passed by Django)
        order_attribute: the attribute of the model that clicking the table header
            should sort by
        column_name: the user-facing name of the column (e.g. the text
            of the <th> element). If None, use the camel-case version of
            `sort_attribute`.

    returns:
        a dictionary containing the following
            - order_attribute: the unchanged `order_attribute` parameter
            - column_name: the user-facing name of the column (e.g. the value of `column_name`
                or the camel-case version of `order_attribute`)
            - attr_is_currently_ordering: a boolean indicating whether the table is currently
                ordered by `order_attribute`
            - current_sort_param: the current sort order (either "asc" or "desc")
            - url_wo_sort_params: the current URL without sorting and pagination parameters
    """
    current_order_param = request.GET.get("order")
    current_sort_param = request.GET.get("sort")
    # Remove order, sort, and page parameters from the query string
    query_dict = request.GET.copy()
    for param in ["order", "sort", "page"]:
        if param in query_dict:
            query_dict.pop(param)
    # Create the current URL without sorting and pagination parameters
    url_wo_sort_params = f"{request.path}?{query_dict.urlencode()}"
    if column_name is None:
        column_name = order_attribute.replace("_", " ").title()
    return {
        "order_attribute": order_attribute,
        "column_name": column_name,
        "attr_is_currently_ordering": order_attribute == current_order_param,
        "current_sort_param": current_sort_param,
        "url_wo_sort_params": url_wo_sort_params,
    }


@register.simple_tag(takes_context=False)
def join_absolute_url_links(
    objects: list[BaseModel], display_attr: str, sep: str, newtab: bool = False
) -> SafeString:
    """
    Takes a series of objects and returns an html string of
    links to their absolute urls (i.e. their detail page).

    Additional parameters:
        display_attr: the attribute of the object to display in the link
        sep: the separator between links
    """
    return format_html_join(
        sep,
        '<b><a href="{0}"{2}>{1}</a></b>',
        (
            (
                obj.get_absolute_url(),
                getattr(obj, display_attr),
                ' target="_blank"' if newtab else "",
            )
            for obj in objects
        ),
    )


@register.filter
def render_markdown(value: str) -> SafeString:
    """
    Renders markdown text as HTML.
    """
    html: str = github_flavored_markdown_to_html(value)
    # Generated html is marked safe b/c cmark is run in safe mode in
    # github_flavored_markdown_to_html
    return mark_safe(html)
