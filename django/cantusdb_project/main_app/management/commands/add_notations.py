from django.core.management.base import BaseCommand, CommandError
from xml.etree import ElementTree as ET
from main_app.models import Notation


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument("xml_file", type=str)

    def handle(self, *args, **options):
        file_path = options["xml_file"]
        root = ET.parse(file_path).getroot()

        for notation in root.findall("notation"):
            name, description = (None, None)
            for element in notation:
                element_name = element.tag
                element_value = notation.find(element.tag).text
                if element_name == "name":
                    name = element_value
                if element_name == "id":
                    notation_id = int(element_value)
            notation_obj, created = Notation.objects.get_or_create(
                id=notation_id, name=name
            )
            notation_obj.save()
            print(f"{notation_obj.name} saved on the database!")
