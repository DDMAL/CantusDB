from django.core.management.base import BaseCommand, CommandError
from xml.etree import ElementTree as ET
from main_app.models import Provenance


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument("xml_file", type=str)

    def handle(self, *args, **options):
        file_path = options["xml_file"]
        root = ET.parse(file_path).getroot()

        for provenance in root.findall("provenance"):
            name, description, mass_provenance = (None, None, None)
            for element in provenance:
                element_name = element.tag
                element_value = provenance.find(element.tag).text

                if element_name == "name":
                    name = element_value
                if element_name == "id":
                    provenance_id = int(element_value)

            provenance_obj, created = Provenance.objects.get_or_create(
                id=provenance_id, name=name
            )
            provenance_obj.save()
            print(f"{provenance_obj.name} saved on the database!")
