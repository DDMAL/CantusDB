import calendar
from typing import Union, Optional
from django.utils.http import urlencode
from django import template
from main_app.models import Source
from django.utils.safestring import mark_safe

register = template.Library()


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
        Source.objects.filter(public=True, visible=True)
        .exclude(siglum=None)
        .values("siglum", "id")
        .order_by("siglum")
    )
    options = ""
    # <option value="source1">Source 1</option>
    #                         <option value="source2">Source 2</option>
    #                         <option value="source3">Source 3</option>
    for source in sources:
        option_str = (
            f"<option value=sources/{source['id']}>{source['siglum']}</option>\n"
        )
        options += option_str

    return mark_safe(options)
