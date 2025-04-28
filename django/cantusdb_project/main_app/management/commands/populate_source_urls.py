"""
A command to add the contents of a source's image_link field as a related
SourceURL object.
"""

from django.core.management.base import BaseCommand

from main_app.models import Source, SourceURL


class Command(BaseCommand):
    def handle(self, *args: str, **options: str) -> None:
        # Check that there are no sources with an empty string image_link
        # There shouldn't be and we don't have any at time of writing but
        # just in case.
        sources = Source.objects.filter(image_link="")
        if sources.exists():
            self.stdout.write(
                self.style.ERROR(
                    f"Found {sources.count()} sources with an empty image_link field."
                )
            )
            return
        sources_with_img_links = Source.objects.exclude(
            image_link__isnull=True
        ).iterator()
        counter = 0
        for source in sources_with_img_links:
            SourceURL.objects.create(
                source=source,
                url=source.image_link,
                url_type=SourceURL.URLTypes.EXTERNAL_IMAGES,
            )
            counter += 1
        self.stdout.write(
            self.style.SUCCESS(
                f"Added {counter} SourceURL objects from the image_link field."
            )
        )
