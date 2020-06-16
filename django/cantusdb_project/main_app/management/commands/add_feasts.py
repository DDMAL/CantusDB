from django.core.management.base import BaseCommand, CommandError
from xml.etree import ElementTree as ET
import re
from datetime import datetime
from main_app.models import Feast


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument("xml_file", type=str)

    def handle(self, *args, **options):
        file_path = options["xml_file"]
        root = ET.parse(file_path).getroot()

        for feast in root.findall("feast"):
            name, description, day, month, feast_code, feast_id, notes = (
                None,
                None,
                None,
                None,
                None,
                None,
                None,
            )
            for element in feast:
                element_name = element.tag
                element_value = feast.find(element.tag).text
                if element_value:
                    cleanr = re.compile("<.*?>")
                    element_value = re.sub(cleanr, "", element_value)

                    if element_name == "name":
                        name = element_value
                    elif element_name == "description":
                        description = element_value
                    elif element_name == "date":
                        split_str = element_value.split(".")
                        if len(split_str) > 1:
                            day = int(split_str[1])
                            month = int(datetime.strptime(split_str[0], "%b").month)
                    elif element_name == "feast_code":
                        if element_value != "xxx":
                            feast_code = int(element_value)
                    elif element_name == "id":
                        feast_id = int(element_value)
                    elif element_name == "notes":
                        notes = element_value
            feast_obj = Feast(
                id=feast_id,
                name=name,
                description=description,
                feast_code=feast_code,
                month=month,
                day=day,
                notes=notes,
            )
            feast_obj.save()
            print(f"{feast_obj.name} saved on the database!")
