from django.core.management.base import BaseCommand, CommandError
from xml.etree import ElementTree as ET
import re
from datetime import datetime
from main_app.models import Source, Century, Notation, Provenance, Segment


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument("xml_file", type=str)

    def handle(self, *args, **options):
        file_path = options["xml_file"]
        root = ET.parse(file_path).getroot()
        i = 1
        print(i)
        for source in root.findall("source"):
            (
                source_id,
                title,
                rism_siglum,
                provenance_id,
                provenance_notes,
                source_status,
                date,
                century_id,
                notation_id,
                segment_id,
                summary,
                liturgical_occasions,
                description,
                image_link,
                indexing_notes,
                indexing_date,
            ) = (
                None,
                None,
                None,
                None,
                None,
                None,
                None,
                None,
                None,
                None,
                None,
                None,
                None,
                None,
                None,
                None,
            )
            for element in source:
                element_name = element.tag
                element_value = source.find(element.tag).text
                if element_value:
                    cleanr = re.compile("<.*?>")
                    element_value = re.sub(cleanr, "", element_value)
                    if element_name == "id":
                        source_id = int(element_value)
                    elif element_name == "title":
                        title = element_value
                    elif element_name == "rism":
                        rism_siglum = element_value
                    elif element_name == "provenance_id":
                        provenance_id = int(element_value)
                    elif element_name == "provenance_notes":
                        provenance_notes = element_value
                    elif element_name == "source_status_id":
                        source_status_id = int(element_value)
                        if source_status_id == 4212:
                            source_status = "Published / Complete"
                        elif source_status_id == 4208:
                            source_status = "Unpublished / Indexing process"
                    elif element_name == "date":
                        date = element_value
                    elif element_name == "century_id":
                        century_id = int(element_value)
                    elif element_name == "notation_style_id":
                        notation_id = int(element_value)
                    elif element_name == "segment_id":
                        segment_id = int(element_value)
                    elif element_name == "summary":
                        summary = element_value
                    elif element_name == "liturgical_occasions":
                        liturgical_occasions = element_value
                    elif element_name == "description":
                        description = element_value
                    elif element_name == "image_link":
                        image_link = element_value
                    elif element_name == "indexing_notes":
                        indexing_notes = element_value
                    elif element_name == "indexing_date":
                        indexing_date = element_value

                try:
                    provenance = Provenance.objects.get(id=provenance_id)
                except:
                    provenance = None
                try:
                    century = Century.objects.get(id=century_id)
                except:
                    century = None
                try:
                    segment = Segment.objects.get(id=segment_id)
                except:
                    segment = None
            print(source_id)
            if not Source.objects.filter(id=source_id).exists():
                source_obj = Source(
                    id=source_id,
                    title=title,
                    siglum=siglum,
                    rism_siglum=rism_siglum,
                    provenance=provenance,
                    provenance_notes=provenance_notes,
                    source_status=source_status,
                    date=date,
                    century=century,
                    segment=segment,
                    summary=summary,
                    liturgical_occasions=liturgical_occasions,
                    description=description,
                    image_link=image_link,
                    indexing_notes=indexing_notes,
                    indexing_date=indexing_date,
                )
                source_obj.save()
                if notation_id:
                    source_obj.notation.add(notation_id)
                    source_obj.save()
                print(f"{source_obj.title} added to database! ID: {source_obj.id}")
