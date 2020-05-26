from django.core.management.base import BaseCommand, CommandError
from xml.etree import ElementTree as ET
import re
from datetime import datetime
from main_app.models import Genre


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument("xml_file", type=str)

    def handle(self, *args, **options):
        file_path = options["xml_file"]
        root = ET.parse(file_path).getroot()

        for feast in root.findall("genre"):
            name, description, mass_office = (None, None, None)
            for element in feast:
                element_name = element.tag
                element_value = feast.find(element.tag).text
                cleanr = re.compile("<.*?>")
                element_value = re.sub(cleanr, "", element_value)

                if element_name == "name":
                    name = element_value
                if element_name == "description":
                    description = element_value
                if element_name == "mass_or_office":
                    mass_office = element_value.split(", ")
                    mass_office = [
                        "Hispanic" if value == "Old Hispanic" else value
                        for value in mass_office
                    ]
                if element_name == "id":
                    genre_id = int(element_value)
            genre_obj, created = Genre.objects.get_or_create(
                id=genre_id, name=name, description=description, mass_office=mass_office
            )
            genre_obj.save()
            print(f"{genre_obj.name} saved on the database!")
