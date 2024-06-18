import calendar
from typing import Union, Optional

from django import template
from django.core.paginator import Paginator
from django.db.models import Q
from django.template.defaultfilters import stringfilter
from django.utils.safestring import mark_safe

from articles.models import Article
from main_app.models import Source

register = template.Library()


@register.simple_tag(takes_context=False)
def recent_articles():
    """
    Generates a html unordered list of recent articles for display on the homepage

    Used in:
        templates/flatpages/default.html
    """
    articles = Article.objects.order_by("-date_created")[:5]
    list_item_template = '<li style="padding-bottom: 0.5em;"><a href="{url}">{title}</a><br><small>{date}</small></li>'
    list_items = [
        list_item_template.format(
            url=a.get_absolute_url(),
            title=a.title,
            date=a.date_created.strftime("%A %B %-d, %Y"),
        )
        for a in articles
    ]
    list_items_string = "".join(list_items)
    recent_articles_string = "<ul>{lis}</ul>".format(lis=list_items_string)
    return mark_safe(recent_articles_string)


@register.filter(name="month_to_string")
def month_to_string(value: Optional[Union[str, int]]) -> Optional[Union[str, int]]:
    """
    Converts month number to textual representation, 3 letters (Jan, Mar, etc)

    used in:
        main_app/templates/feast_detail.html
        main_app/templates/feast_list.html
    """
    if type(value) == int and value in range(1, 13):
        return calendar.month_abbr[value]
    else:
        return value


@register.simple_tag(takes_context=True)
def url_add_get_params(context, **kwargs):
    """
    accounts for the situations where there may be two paginations in one page

    Used in:
        main_app/templates/pagination.html
        main_app/templates/user_source_list.html
    """
    query = context["request"].GET.copy()
    if "page" in kwargs:
        query.pop("page", None)
    if "page2" in kwargs:
        query.pop("page2", None)
    query.update(kwargs)
    return query.urlencode()


@register.simple_tag(takes_context=False)
def source_links():
    """
    Generates a series of html option tags linking to sources in Cantus Dabase, for display on the homepage

    Used in:
        templates/flatpages/default.html
    """
    sources = (
        Source.objects.filter(published=True, segment__id=4063)
        .exclude(siglum=None)
        .values("siglum", "id")
        .order_by("siglum")
    )
    options = ""
    for source in sources:
        option_str = (
            f"<option value=source/{source['id']}>{source['siglum']}</option>\n"
        )
        options += option_str

    return mark_safe(options)


@register.filter
def classname(obj):
    """
    Returns the name of the object's class
    A use-case is: {% if object|classname == "Notation" %}

    Used in:
        main_app/templates/content_overview.html
    """
    return obj.__class__.__name__


@register.filter
def admin_url_name(class_name, action):
    """
    Accepts the name of a class in "main_app", and an action (either "change" or "delete") as arguments.
    Returns the name of the URL for changing/deleting an object in the admin interface.

    Used in:
        main_app/templates/content_overview.html
    """
    class_name = class_name.lower()
    action = action.lower()

    return f"admin:main_app_{class_name}_{action}"


@register.filter(name="has_group")
def has_group(user, group_name):
    """
    Used in:
        templates/base.html
    """
    return user.groups.filter(name=group_name).exists()


@register.filter(name='split')
@stringfilter
def split(value: str, key: str) -> list[str]:
    """
        Returns the value turned into a list.
    """
    return value.split(key)


@register.simple_tag(takes_context=True)
def get_user_source_pagination(context):
    user_created_sources = (
        Source.objects.filter(
            Q(current_editors=context["user"]) | Q(created_by=context["user"])
        )
        .order_by("-date_updated")
        .distinct()
    )
    paginator = Paginator(user_created_sources, 6)
    page_number = context["request"].GET.get("page")
    user_sources_page_obj = paginator.get_page(page_number)
    return user_sources_page_obj


@register.simple_tag(takes_context=True)
def get_user_created_source_pagination(context):
    user_created_sources = (
        Source.objects.filter(created_by=context["user"])
        .order_by("-date_created")
        .distinct()
    )
    paginator = Paginator(user_created_sources, 6)
    page_number = context["request"].GET.get("page2")
    user_created_sources_page_obj = paginator.get_page(page_number)
    return user_created_sources_page_obj
