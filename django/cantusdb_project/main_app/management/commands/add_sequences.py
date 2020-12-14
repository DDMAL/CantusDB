import json
import sys
from pprint import pprint

import ijson
from django.core.exceptions import ObjectDoesNotExist
from django.core.management.base import BaseCommand, CommandError
from django.core.validators import URLValidator

from main_app.models import Sequence, Genre, Source


class Command(BaseCommand):
    def add_arguments(self, parser):
        pass

    def handle(self, *args, **options):
        file_path = "/code/django/cantusdb_project/sequences.json"
        json_file = open(file_path, "r")
        objects = ijson.items(json_file, "item")
        sequences = (sequence for sequence in objects)
        no_of_seqs = 17281
        i = 0
        for sequence in sequences:
            try:
                seq_id = int(sequence["nid"])
                if Sequence.objects.filter(id=seq_id).exists():
                    i += 1
                    percent_done = round(((i / no_of_seqs) * 100), 6)
                    sys.stdout.write(f"\r{percent_done} %")
                    continue
            except Exception as e:
                print(e)
                print(f"Could not load sequence {sequence}")
                continue
            try:
                source_id = int(sequence["field_source"]["und"][0]["target_id"])
                source = Source.objects.get(id=source_id)
            except (KeyError, TypeError, ObjectDoesNotExist) as e:
                if type(e) == ObjectDoesNotExist:
                    print("\n")
                    print(e)
                    print(f"{sequence.id} with source {source_id}")
            try:
                title = sequence["title"]
            except (KeyError, TypeError):
                title = None
                print(f"sequence {seq_id} missing title")
            try:
                siglum = sequence["field_siglum_chant"]["und"][0]["value"]
            except (KeyError, TypeError):
                siglum = None
            try:
                incipit = sequence["field_incipit"]["und"][0]["value"]
            except (KeyError, TypeError):
                incipit = None
            try:
                folio = sequence["field_folio"]["und"][0]["value"]
            except (KeyError, TypeError):
                folio = None
            try:
                sequence = sequence["field_sequence_text"]["und"][0]["value"]
            except (KeyError, TypeError):
                sequence = None
            try:
                genre_id = int(sequence["field_mc_genre"]["und"][0]["tid"])
                genre = Genre.objects.get(id=genre_id)
            except (KeyError, TypeError, ObjectDoesNotExist) as e:
                if type(e) == ObjectDoesNotExist:
                    print("\n")
                    print(e)
                    print(f"{sequence.id} with genre {genre_id}")
                genre = None
            try:
                rubric = sequence["field_rubrics"]["und"][0]["value"]
            except (KeyError, TypeError):
                rubric = None
            try:
                analecta_hymnica = sequence["field_analecta_hymnica"]["und"][0]["value"]
            except (KeyError, TypeError):
                analecta_hymnica = None
            try:
                indexing_notes = sequence["field_indexing_notes"]["und"][0]["value"]
            except (KeyError, TypeError):
                indexing_notes = None
            try:
                date = sequence["field_date"]["und"][0]["value"]
            except (KeyError, TypeError):
                date = None
            try:
                ah_volume = sequence["field_ah_vol"]["und"][0]["value"]
            except (KeyError, TypeError):
                ah_volume = None
            try:
                cantus_id = sequence["field_cantus_id"]["und"][0]["value"]
            except (KeyError, TypeError):
                cantus_id = None
            try:
                image_link = sequence["field_image_link_chant"]["und"][0]["value"]
                validate = URLValidator()
                validate(image_link)
            except:
                image_link = None
            obj, created = Sequence.objects.get_or_create(
                id=seq_id,
                title=title,
                siglum=siglum,
                incpit=incipit,
                folio=folio,
                genre=genre,
                rubric=rubric,
                analecta_hymnica=analecta_hymnica,
                indexing_notes=indexing_notes,
                date=date,
                ah_volume=ah_volume,
                source=source,
                cantus_id=cantus_id,
                image_link=image_link,
            )

            i += 1
            percent_done = round(((i / no_of_seqs) * 100), 6)
            sys.stdout.write(f"\r{percent_done} %")

    print("\n")