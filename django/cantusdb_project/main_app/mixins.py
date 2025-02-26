from typing import Any
from django.http.response import JsonResponse, HttpResponse
from django.http.request import HttpRequest
from django.core.exceptions import ImproperlyConfigured
from django.template.response import TemplateResponse


class JSONResponseMixin:
    """
    Mixin to negotiate content type. Designed for use with
    DetailView and ListView classes only.

    If the request contains an `Accept` header with the value
    `application/json`, the response will be a JSON object.
    Otherwise, the response will render the HTML template as
    usual.

    The parent view must define an attribute "json_fields" that
    lists the fields to be included in the JSON response.
    """

    def _get_field(self, obj: Any, field: str) -> Any:
        """
        Returns the value of a field on an object, allowing
        for "double underscore" notation to access related
        fields.

        Returns the value specified by the double underscore
        lookup. If this lookup fails, return the object as
        far down the lookup chain as possible.
        """
        split_field = field.split("__")
        temp_obj = obj
        for part in split_field:
            try:
                temp_obj = getattr(temp_obj, part)
            except AttributeError:
                return temp_obj
        return temp_obj

    def render_to_response(
        self, context: dict[Any, Any], **response_kwargs: dict[Any, Any]
    ) -> HttpResponse:
        """
        Returns a JSON response if the request accepts JSON.
        Otherwise, returns the default response.
        """
        try:
            request: HttpRequest = self.request  # type: ignore[attr-defined]
        except AttributeError as exc:
            raise ImproperlyConfigured(
                "A JSONResponseMixin must be used with a DetailView or ListView."
            ) from exc
        try:
            json_fields = self.json_fields  # type: ignore[attr-defined]
        except AttributeError as exc:
            raise ImproperlyConfigured(
                "A JSONResponseMixin must define a json_fields attribute."
            ) from exc
        if "application/json" in request.META.get("HTTP_ACCEPT", ""):
            obj = context.get("object")
            if obj:
                obj_json = {}
                for field in json_fields:
                    obj_json[field] = self._get_field(obj, field)
                return JsonResponse({obj.get_verbose_name(): obj_json})
            q_s = self.object_list.values(*json_fields)  # type: ignore[attr-defined]
            q_s_name = str(q_s.model.get_verbose_name_plural())
            return JsonResponse({q_s_name: list(q_s)})
        try:
            template_response: TemplateResponse = super().render_to_response(  # type: ignore[misc]
                context, **response_kwargs
            )
        except AttributeError as exc:
            raise ImproperlyConfigured(
                "A JSONResponseMixin must be used with a DetailView or ListView."
            ) from exc
        return template_response
