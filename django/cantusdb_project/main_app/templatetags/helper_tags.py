import calendar
from typing import Union, Optional
from django.utils.http import urlencode
from django import template
from main_app.models import Source
from articles.models import Article
from django.utils.safestring import mark_safe

register = template.Library()


@register.simple_tag(takes_context=False)
def recent_articles():
    articles = Article.objects.order_by("-date_created")[:5]
    list_item_template = '<li><a href="{url}">{title}</a><br><small>{date}</small></li>'
    list_items = [
        list_item_template.format(
            url=a.get_absolute_url(),
            title=a.title,
            date=a.date_created.strftime("%x"),
        )
        for a
        in articles
    ]
    list_items_string = "".join(list_items)
    recent_articles_string = "<ul>{lis}</ul>".format(lis=list_items_string)
    return mark_safe(recent_articles_string)


@register.filter(name="month_to_string")
def month_to_string(value: Optional[Union[str, int]]) -> Optional[Union[str, int]]:
    """Converts month number to textual representation, 3 letters (Jan, Mar, etc)"""
    if type(value) == int and value in range(1, 13):
        return calendar.month_abbr[value]
    else:
        return value


@register.simple_tag(takes_context=True)
def url_add_get_params(context, **kwargs):
    query = context["request"].GET.copy()
    query.pop("page", None)
    query.update(kwargs)
    return query.urlencode()


@register.simple_tag(takes_context=False)
def source_links():
    sources = (
        Source.objects.filter(public=True, visible=True, segment__id=4063)
        .exclude(siglum=None)
        .values("siglum", "id")
        .order_by("siglum")
    )
    options = ""
    # <option value="source1">Source 1</option>
    # <option value="source2">Source 2</option>
    # <option value="source3">Source 3</option>
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
    """
    return obj.__class__.__name__

@register.filter
def admin_url_name(class_name, action):
    """
    Accepts a class name and an action (either "change" or "delete") as arguments.
    Returns the name of the URL for changing/deleting an object in the admin interface.
    """
    class_name = class_name.lower()
    action = action.lower()

    return f"admin:main_app_{class_name}_{action}"

@register.filter(name='has_group') 
def has_group(user, group_name):
    return user.groups.filter(name=group_name).exists() 
