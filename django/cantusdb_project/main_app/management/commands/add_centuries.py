from django.core.management.base import BaseCommand, CommandError
from xml.etree import ElementTree as ET
from main_app.models import Century


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument("xml_file", type=str)

    def handle(self, *args, **options):
        file_path = options["xml_file"]
        root = ET.parse(file_path).getroot()

        for century in root.findall("century"):
            name, description = (None, None)
            for element in century:
                element_name = element.tag
                element_value = century.find(element.tag).text
                if element_name == "name":
                    name = element_value
                if element_name == "id":
                    century_id = int(element_value)
            century_obj, created = Century.objects.get_or_create(
                id=century_id, name=name
            )
            century_obj.save()
            print(f"{century_obj.name} saved on the database!")
