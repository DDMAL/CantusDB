from django.core.management.base import BaseCommand, CommandError
from xml.etree import ElementTree as ET
from main_app.models import Indexer


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument("xml_file", type=str)

    def handle(self, *args, **options):
        file_path = options["xml_file"]
        root = ET.parse(file_path).getroot()

        for indexer in root.findall("indexer"):
            first_name, family_name, institution, city, country, indexer_id = (
                None,
                None,
                None,
                None,
                None,
                None,
            )
            display_name = None

            for element in indexer:
                element_name = element.tag
                element_value = indexer.find(element.tag).text

                if element_name == "given_name":
                    first_name = element_value
                if element_name == "family_name":
                    family_name = element_value
                if element_name == "city":
                    city = element_value
                if element_name == "country":
                    country = element_value
                if element_name == "institution":
                    institution = element_value
                if element_name == "id":
                    indexer_id = int(element_value)

                if element_name == "display_name":
                    display_name = element_value

            indexer_obj = Indexer(
                first_name=first_name,
                family_name=family_name,
                institution=institution,
                city=city,
                country=country,
                id=indexer_id,
            )
            indexer_obj.save()
            print(
                f"{indexer_obj.first_name} {indexer_obj.family_name} saved on the database!"
            )
