import calendar
from typing import Union, Optional
from django.utils.http import urlencode
from django import template

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
