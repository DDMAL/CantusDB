import calendar
from typing import Union, Optional
from django.utils.http import urlencode
from django import template
from main_app.models import Source
from articles.models import Article
from django.utils.safestring import mark_safe
from django.urls import reverse

register = template.Library()


@register.simple_tag(takes_context=False)
def recent_articles():
    articles = Article.objects.order_by("-date_created")[:5]
    list_item_template = '<li style="padding-bottom: 0.5em;"><a href="{url}">{title}</a><br><small>{date}</small></li>'
    list_items = [
        list_item_template.format(
            url=a.get_absolute_url(),
            title=a.title,
            date=a.date_created.strftime("%A %B %-d, %Y"),
        )
        for a
        in articles
    ]
    list_items_string = "".join(list_items)
    recent_articles_string = "<ul>{lis}</ul>".format(lis=list_items_string)
    return mark_safe(recent_articles_string)


@register.simple_tag(takes_context=False)
def my_sources(user):
    def make_source_detail_link_with_siglum(source):
        id = source.id
        siglum = source.rism_siglum
        url = reverse("source-detail", args=[id])
        link = '<a href="{}">{}</a>'.format(url, siglum)
        return link
    def make_source_detail_link_with_title(source):
        id = source.id
        title = source.title
        url = reverse("source-detail", args=[id])
        link = '<a href="{}">{}</a>'.format(url, title) 
        return link
    def make_add_new_chants_link(source):
        id = source.id
        url = reverse("chant-create", args=[id])
        link = '<a href="{}">+ Add new chant</a>'.format(url) 
        return link
    def make_edit_chants_link(source):
        id = source.id
        url = reverse("source-edit-chants", args=[id])
        link = '<a href="{}">Edit chants (Fulltext & Volpiano editor)</a>'.format(url) 
        return link
    def make_links_for_source(source):
        link_with_siglum = make_source_detail_link_with_siglum(source)
        link_with_title = make_source_detail_link_with_title(source)
        add_new_chants_link = make_add_new_chants_link(source)
        edit_chants_link = make_edit_chants_link(source)
        template = """{sigl}<br>
        <small>
            <b>{title}</b><br>
            {add}<br>
            {edit}<br>
        </small>
        """
        links_string = template.format(
            sigl=link_with_siglum,
            title=link_with_title,
            add=add_new_chants_link,
            edit=edit_chants_link,
        )
        return links_string
    MAX_SOURCES_TO_DISPLAY = 6
    sources = list(user.sources_user_can_edit.all())[:MAX_SOURCES_TO_DISPLAY]
    source_links = [make_links_for_source(source) for source in sources]
    list_items = ["<li>{}</li>".format(link) for link in source_links]
    joined_list_items = "".join(list_items)
    links_ul = "<ul>{}</ul>".format(joined_list_items)
    return mark_safe(links_ul)

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
    # accounts for the situations where there may be two paginations in one page
    if "page" in kwargs:
        query.pop("page", None)
    if "page2" in kwargs:
        query.pop("page2", None)
    query.update(kwargs)
    return query.urlencode()


@register.simple_tag(takes_context=False)
def source_links():
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
    """
    return obj.__class__.__name__

@register.filter
def admin_url_name(class_name, action):
    """
    Accepts the name of a class in "main_app", and an action (either "change" or "delete") as arguments.
    Returns the name of the URL for changing/deleting an object in the admin interface.
    """
    class_name = class_name.lower()
    action = action.lower()

    return f"admin:main_app_{class_name}_{action}"

@register.filter(name='has_group') 
def has_group(user, group_name):
    return user.groups.filter(name=group_name).exists() 
