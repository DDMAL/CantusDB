from django.core.management.base import BaseCommand, CommandError
from xml.etree import ElementTree as ET
from main_app.models import Siglum


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument("xml_file", type=str)

    def handle(self, *args, **options):
        file_path = options["xml_file"]
        root = ET.parse(file_path).getroot()

        for siglum in root.findall("siglum"):
            name, description = (None, None)
            for element in siglum:
                element_name = element.tag
                element_value = siglum.find(element.tag).text

                if element_name == "name":
                    name = element_value
                if element_name == "description":
                    description = element_value
                if element_name == "id":
                    siglum_id = int(element_value)

            siglum_obj, created = Siglum.objects.get_or_create(
                id=siglum_id, name=name, description=description
            )
            siglum_obj.save()
            print(f"{siglum_obj.name} saved on the database!")
