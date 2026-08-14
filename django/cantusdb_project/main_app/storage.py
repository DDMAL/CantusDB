from django.conf import settings
from django.core.files.storage import FileSystemStorage
from django.utils.functional import cached_property


class PrivateMediaStorage(FileSystemStorage):
    """FileSystemStorage rooted at PRIVATE_MEDIA_ROOT instead of MEDIA_ROOT.

    Files saved here are never reachable through nginx's public /media
    alias, unlike the default storage. base_location/location must stay
    lazy (not resolved at __init__ time) so tests can redirect them with
    override_settings(PRIVATE_MEDIA_ROOT=...).
    """

    @cached_property
    def base_location(self) -> str:
        return self._value_or_setting(self._location, settings.PRIVATE_MEDIA_ROOT)

    def _clear_cached_properties(self, setting: str, **kwargs) -> None:
        if setting == "PRIVATE_MEDIA_ROOT":
            self.__dict__.pop("base_location", None)
            self.__dict__.pop("location", None)
        else:
            super()._clear_cached_properties(setting, **kwargs)


def private_media_storage() -> PrivateMediaStorage:
    return PrivateMediaStorage()
