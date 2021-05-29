from django.core.management.base import BaseCommand
import requests
import lxml.html as lh
from main_app.models import Genre


class Command(BaseCommand):
    def add_arguments(self, parser):
        pass

    def handle(self, *args, **options):
        url = "https://cantus.uwaterloo.ca/genre"
        response = requests.get(url)
        doc = lh.fromstring(response.content)
        tr_elements = doc.xpath("//tr")
        for row in tr_elements[1:]:
            name = row[0].text_content().strip()
            description = row[1].text_content().strip()
            mass_office = row[2].text_content().strip()
            href = row.xpath("td/h3/a/@href")[0]
            id = href.split("/")[-1]
            print("{}-{}-{}-{}".format(id, name, description, mass_office))
            genre_obj, created = Genre.objects.update_or_create(
                id=id,
                defaults={
                    "name": name,
                    "description": description,
                    "mass_office": mass_office,
                },
            )
            if created:
                print(f"Created new genre: {id}")
