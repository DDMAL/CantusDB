import json
import sys
from pprint import pprint

import ijson
from django.core.exceptions import ObjectDoesNotExist
from django.core.management.base import BaseCommand, CommandError
from django.core.validators import URLValidator

from main_app.models import Chant, Feast, Genre, Office, Source


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument("json_file", type=str)

    def handle(self, *args, **options):
        file_path = options["json_file"]
        json_file = open(file_path, "r")
        objects = ijson.items(json_file, "item")
        chants = (chant for chant in objects)
        no_of_chants = 492902
        i = 0
        for chant in chants:
            try:
                chant_id = int(chant["nid"])
                if Chant.objects.filter(id=chant_id).exists():
                    i += 1
                    percent_done = round(((i / no_of_chants) * 100), 6)
                    sys.stdout.write(f"\r{percent_done} %")
                    continue
            except Exception as e:
                print(e)
                print(f"Could not load chant {chant}")
                continue
            try:
                source_id = int(chant["field_source"]["und"][0]["target_id"])
                source = Source.objects.get(id=source_id)
            except (KeyError, TypeError, ObjectDoesNotExist) as e:
                if type(e) == ObjectDoesNotExist:
                    print("\n")
                    print(e)
                    print(f"{chant.id} with source {source_id}")
            try:
                incipit = chant["title"]
            except (KeyError, TypeError):
                incipit = None
                print(f"chant {chant_id} missing title")
            try:
                marginalia = chant["field_marginalia"]["und"][0]["value"]
            except (KeyError, TypeError):
                marginalia = None
            try:
                folio = chant["field_folio"]["und"][0]["value"]
            except (KeyError, TypeError):
                folio = None
            try:
                sequence_number = int(chant["field_sequence"]["und"][0]["value"])
            except (KeyError, TypeError):
                sequence_number = None
            try:
                office_id = int(chant["field_office"]["und"][0]["target_id"])
                office = Office.objects.get(id=office_id)
            except (KeyError, TypeError, ObjectDoesNotExist) as e:
                if type(e) == ObjectDoesNotExist:
                    print("\n")
                    print(e)
                    print(f"{chant.id} with office {office_id}")
                office = None
            try:
                genre_id = int(chant["field_mc_genre"]["und"][0]["tid"])
                genre = Genre.objects.get(id=genre_id)
            except (KeyError, TypeError, ObjectDoesNotExist) as e:
                if type(e) == ObjectDoesNotExist:
                    print("\n")
                    print(e)
                    print(f"{chant.id} with genre {genre_id}")
                genre = None
            try:
                position = chant["field_position"]["und"][0]["value"]
            except (KeyError, TypeError):
                position = None
            try:
                cantus_id = chant["field_cantus_id"]["und"][0]["value"]
            except (KeyError, TypeError):
                cantus_id = None
            try:
                feast_id = int(chant["field_mc_feast"]["und"][0]["tid"])
                feast = Feast.objects.get(id=feast_id)
            except (KeyError, TypeError, ObjectDoesNotExist) as e:
                if type(e) == ObjectDoesNotExist:
                    print("\n")
                    print(e)
                    print(f"{chant.id} with feast {feast_id}")
                feast = None
            try:
                mode = chant["field_mode"]["und"][0]["value"]
            except (KeyError, TypeError):
                mode = None
            try:
                differentia = chant["field_differentia"]["und"][0]["value"]
            except (KeyError, TypeError):
                differentia = None
            try:
                finalis = chant["field_finalis"]["und"][0]["value"]
            except (KeyError, TypeError):
                finalis = None
            try:
                extra = chant["field_extra"]["und"][0]["value"]
            except (KeyError, TypeError):
                extra = None
            try:
                addendum = chant["field_addendum"]["und"][0]["value"]
            except (KeyError, TypeError):
                addendum = None
            try:
                manuscript_full_text_std_spelling = chant["field_full_text_ms"]["und"][
                    0
                ]["value"]
            except (KeyError, TypeError):
                manuscript_full_text_std_spelling = None
            try:
                manuscript_full_text_proofread = int(
                    chant["field_fulltext_proofread"]["und"][0]["value"]
                )
            except (KeyError, TypeError):
                manuscript_full_text_proofread = None
            try:
                finalis = chant["field_finalis"]["und"][0]["value"]
            except (KeyError, TypeError):
                finalis = None
            try:
                manuscript_full_text_proofread = int(
                    chant["field_ms_fulltext_proofread"]["und"][0]["value"]
                )
            except (KeyError, TypeError):
                manuscript_full_text_proofread = None
            try:
                manuscript_syllabized_full_text = chant["field_syllabized_full_text"][
                    "und"
                ][0]["value"]
            except (KeyError, TypeError):
                manuscript_syllabized_full_text = None
            try:
                volpiano = chant["field_volpiano"]["und"][0]["value"]
            except:
                volpiano = None
            try:
                volpiano_proofread = int(
                    chant["field_volpiano_proofread"]["und"][0]["value"]
                )
            except (KeyError, TypeError):
                volpiano_proofread = None
            try:
                concordances = chant["field_cao_concordances"]["und"][0]["value"]
            except (KeyError, TypeError):
                concordances = None
            try:
                volpiano_proofread = int(
                    chant["field_volpiano_proofread"]["und"][0]["value"]
                )
            except (KeyError, TypeError):
                volpiano_proofread = None
            try:
                melody_id = chant["field_melody_id"]["und"][0]["value"]
            except (KeyError, TypeError):
                melody_id = None
            try:
                image_link = chant["field_image_link_chant"]["und"][0]["value"]
                validate = URLValidator()
                validate(image_link)
            except:
                image_link = None
            try:
                indexing_notes = chant["field_indexing_notes"]["und"][0]["value"]
            except (KeyError, TypeError):
                indexing_notes = None
            obj, created = Chant.objects.get_or_create(
                id=chant_id,
                source=source,
                incipit=incipit,
                marginalia=marginalia,
                folio=folio,
                sequence_number=sequence_number,
                office=office,
                genre=genre,
                position=position,
                cantus_id=cantus_id,
                feast=feast,
                mode=mode,
                differentia=differentia,
                finalis=finalis,
                extra=extra,
                addendum=addendum,
                manuscript_full_text_std_spelling=manuscript_full_text_std_spelling,
                manuscript_full_text_proofread=manuscript_full_text_proofread,
                manuscript_syllabized_full_text=manuscript_syllabized_full_text,
                volpiano=volpiano,
                volpiano_proofread=volpiano_proofread,
                cao_concordances=concordances,
                melody_id=melody_id,
                image_link=image_link,
                indexing_notes=indexing_notes,
                json_info=chant,
            )

            i += 1
            percent_done = round(((i / no_of_chants) * 100), 6)
            sys.stdout.write(f"\r{percent_done} %")

    print("\n")
