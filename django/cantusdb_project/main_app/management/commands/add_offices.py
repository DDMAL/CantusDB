from django.core.management.base import BaseCommand, CommandError
from xml.etree import ElementTree as ET
from main_app.models import Office


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument("xml_file", type=str)

    def handle(self, *args, **options):
        file_path = options["xml_file"]
        root = ET.parse(file_path).getroot()

        for office in root.findall("office"):
            name, description, mass_office = (None, None, None)
            for element in office:
                element_name = element.tag
                element_value = office.find(element.tag).text

                if element_name == "name":
                    name = element_value
                if element_name == "description":
                    description = element_value
                if element_name == "id":
                    office_id = int(element_value)
           
            office_obj, created = Office.objects.get_or_create(
                id=office_id, name=name, description=description
            )
            office_obj.save()
            print(f"{office_obj.name} saved on the database!")
