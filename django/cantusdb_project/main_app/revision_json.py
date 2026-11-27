"""Read institution revisions recorded before country became a foreign key."""

from django.core.exceptions import ValidationError
from django.core.serializers.json import Deserializer as JSONDeserializer
from django.core.serializers.json import Serializer as Serializer
from reversion.errors import RevertError

from main_app.countries import import_country


class Deserializer(JSONDeserializer):
    def _handle_object(self, obj):
        # django-reversion passes both options when reading its stored JSON.
        # Ordinary fixtures use Django's usual foreign-key deserialization.
        if (
            self.ignorenonexistent
            and "use_natural_foreign_keys" in self.options
            and isinstance(obj, dict)
            and obj.get("model") == "main_app.institution"
            and isinstance(fields := obj.get("fields"), dict)
        ):
            if "country_id" in fields:
                fields["country"] = fields.pop("country_id")
            elif isinstance(label := fields.get("country"), str):
                try:
                    country = import_country(label, create_unknown=False)
                except ValidationError as exc:
                    raise RevertError(" ".join(exc.messages)) from exc
                fields["country"] = country.pk if country else None
        yield from super()._handle_object(obj)
