import sys
import time
import random

from main_app.models import Feast, Genre, Office, Source, Chant
from django.core.management.base import BaseCommand
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.core.validators import URLValidator
import requests, json
import lxml.html as lh

# The reason that we’re not using CSV export is that it lacks information.
# There’s no proofread information, no content structure, no chant range...
# The json export is more complete

CHANT_ID_FILE = "chant_list.txt"
USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_11_6) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/11.1.2 Safari/605.1.15",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_5) AppleWebKit/603.3.8 (KHTML, like Gecko) Version/10.1.2 Safari/603.3.8",
]


def get_chant_list(chant_id_file):
    chant_list = []
    file = open(chant_id_file, "r")
    for line in file:
        line = line.strip("\n")
        chant_list.append(line)
    file.close()
    return chant_list


def get_office(office_id):
    # address the missing "unknown" office 4166, we name it AD (à déterminer)
    if office_id == "4166":
        office = Office.objects.create(
            id=office_id, name="AD", description="Unknown Office (à déterminer)"
        )
    else:
        url = "https://cantus.uwaterloo.ca/office/{}".format(office_id)
        response = requests.get(url)
        doc = lh.fromstring(response.content)
        office_name = doc.xpath("//h2")[0].text_content()
        office_description = doc.xpath("//p")[0].text_content()
        print(office_name)
        print(office_id)
        office = Office.objects.create(
            id=office_id, name=office_name, description=office_description
        )
    return office


def get_new_chant(chant_id):
    url = f"http://cantus.uwaterloo.ca/json-node/{chant_id}"
    headers = {"User-Agent": USER_AGENTS[0]}
    print(f"getting {chant_id}")
    try:
        response = requests.get(url, headers, timeout=20)
    except:
        print(f"retrying: {chant_id}")
        headers = {"User-Agent": USER_AGENTS[1]}
        response = requests.get(url, headers, timeout=20)
    print(f"got json for {chant_id}")
    json_response = json.loads(response.content)

    # mysterious field, status 0 for unpublished source (visible in db, denied entry on web), status 1 for published
    try:
        status = json_response["status"]
        if status != "1":
            with open("error_log.txt", "a") as error_file:
                error_file.write(f"chant {chant_id} STATUS {status} ")
                error_file.write("\n")
            # print(f"STATUS {status} at chant {chant_id}")
    except TypeError:
        assert json_response == False
        with open("error_log.txt", "a") as error_file:
            error_file.write(f"chant {chant_id} json not found")
            error_file.write("\n")
        return
    try:
        incipit = json_response["title"]
    except KeyError:
        incipit = None
        with open("error_log.txt", "a") as error_file:
            error_file.write(f"chant {chant_id} missing incipit")
            error_file.write("\n")
        # print(f"chant {chant_id} missing incipit")
    try:
        marginalia = json_response["field_marginalia"]["und"][0]["value"]
    # also except TypeError here, in case chant["field_marginalia"] is an empty list
    except (KeyError, TypeError):
        marginalia = None
    try:
        folio = json_response["field_folio"]["und"][0]["value"]
    except (KeyError, TypeError):
        folio = None
    try:
        sequence_number = int(json_response["field_sequence"]["und"][0]["value"])
    except (KeyError, TypeError):
        sequence_number = None
    try:
        position = json_response["field_position"]["und"][0]["value"]
    except (KeyError, TypeError):
        position = None
    try:
        cantus_id = json_response["field_cantus_id"]["und"][0]["value"]
    except (KeyError, TypeError):
        cantus_id = None
    try:
        mode = json_response["field_mode"]["und"][0]["value"]
    except (KeyError, TypeError):
        mode = None
    try:
        differentia = json_response["field_differentia"]["und"][0]["value"]
    except (KeyError, TypeError):
        differentia = None
    try:
        finalis = json_response["field_finalis"]["und"][0]["value"]
    except (KeyError, TypeError):
        finalis = None
    try:
        extra = json_response["field_extra"]["und"][0]["value"]
    except (KeyError, TypeError):
        extra = None
    try:
        chant_range = json_response["field_range"]["und"][0]["value"]
    except (KeyError, TypeError):
        chant_range = None
    try:
        addendum = json_response["field_addendum"]["und"][0]["value"]
    except (KeyError, TypeError):
        addendum = None

    try:
        fulltext_std = json_response["body"]["und"][0]["value"]
    except (KeyError, TypeError):
        fulltext_std = None
    try:
        fulltext_std_proofread = int(
            json_response["field_fulltext_proofread"]["und"][0]["value"]
        )
    except (KeyError, TypeError):
        fulltext_std_proofread = None

    try:
        fulltext_ms = json_response["field_full_text_ms"]["und"][0]["value"]
    except (KeyError, TypeError):
        fulltext_ms = None
    try:
        fulltext_ms_proofread = int(
            json_response["field_ms_fulltext_proofread"]["und"][0]["value"]
        )
    except (KeyError, TypeError):
        fulltext_ms_proofread = None

    try:
        fulltext_syllabized = json_response["field_syllabized_full_text"]["und"][0][
            "value"
        ]
    except (KeyError, TypeError):
        fulltext_syllabized = None

    try:
        volpiano = json_response["field_volpiano"]["und"][0]["value"]
    except:
        volpiano = None
    try:
        volpiano_proofread = int(
            json_response["field_volpiano_proofread"]["und"][0]["value"]
        )
    except (KeyError, TypeError):
        volpiano_proofread = None

    try:
        concordances = json_response["field_cao_concordances"]["und"][0]["value"]
    except (KeyError, TypeError):
        concordances = None
    try:
        melody_id = json_response["field_melody_id"]["und"][0]["value"]
    except (KeyError, TypeError):
        melody_id = None
    try:
        image_link = json_response["field_image_link_chant"]["und"][0]["value"]
        validate = URLValidator()
        validate(image_link)
    except (KeyError, TypeError):
        image_link = None
    except ValidationError:
        image_link = None
        print(f"chant {chant_id} invalid image link")
    try:
        indexing_notes = json_response["field_indexing_notes"]["und"][0]["value"]
    except (KeyError, TypeError):
        indexing_notes = None
    try:
        content_structure = json_response["field_content_structure"]["und"][0]["value"]
    except (KeyError, TypeError):
        content_structure = None

    try:
        source_id = json_response["field_source"]["und"][0]["target_id"]
        source = Source.objects.get(id=source_id)
    except (KeyError, TypeError):
        with open("error_log.txt", "a") as error_file:
            error_file.write(f"Chant {chant_id} empty source")
            error_file.write("\n")
        source = None
        # raise Exception(f"Chant {chant_id} Missing source")
    except ObjectDoesNotExist:
        # before running this script, we should have run sync_sources, so we should have all sources by now
        # if some chants have unknown source, write those to log
        with open("error_log.txt", "a") as error_file:
            error_file.write(f"Chant {chant_id} Unknown source {source_id}")
            error_file.write("\n")
        source = None
        # raise Exception(f"Chant {chant_id} Unknown source {source_id}")

    try:
        office_id = json_response["field_office"]["und"][0]["target_id"]
        office = Office.objects.get(id=office_id)
    except (KeyError, TypeError):
        office = None
    except ObjectDoesNotExist:
        office = get_office(office_id)
        print(f"Created new office {office_id} for chant {chant_id}")

    try:
        genre_id = json_response["field_mc_genre"]["und"][0]["tid"]
        # run this after running sync_genres
        genre = Genre.objects.get(id=genre_id)
    except (KeyError, TypeError):
        genre = None

    try:
        feast_id = json_response["field_mc_feast"]["und"][0]["tid"]
        # run sync_feasts before running this, so we should already have all feasts
        feast = Feast.objects.get(id=feast_id)
    except (KeyError, TypeError):
        feast = None

    chant_obj, created = Chant.objects.update_or_create(
        id=chant_id,
        defaults={
            "incipit": incipit,
            "visible_status": status,
            "source": source,
            "marginalia": marginalia,
            "folio": folio,
            "sequence_number": sequence_number,
            "office": office,
            "genre": genre,
            "position": position,
            "cantus_id": cantus_id,
            "feast": feast,
            "mode": mode,
            "differentia": differentia,
            "finalis": finalis,
            "extra": extra,
            "chant_range": chant_range,
            "addendum": addendum,
            "manuscript_full_text_std_spelling": fulltext_std,
            "manuscript_full_text_std_proofread": fulltext_std_proofread,
            "manuscript_full_text": fulltext_ms,
            "manuscript_full_text_proofread": fulltext_ms_proofread,
            "manuscript_syllabized_full_text": fulltext_syllabized,
            "volpiano": volpiano,
            "volpiano_proofread": volpiano_proofread,
            "image_link": image_link,
            "cao_concordances": concordances,
            # proofread_by is User, not Indexer
            # "proofread_by": proofread_by,
            "melody_id": melody_id,
            "indexing_notes": indexing_notes,
            "content_structure": content_structure,
            "json_info": json_response,
        },
    )
    if created:
        print(f"Created new chant {chant_id}")


def remove_extra():
    waterloo_ids = get_chant_list(CHANT_ID_FILE)
    our_ids = list(Chant.objects.all().values_list("id", flat=True))
    our_ids = [str(id) for id in our_ids]
    waterloo_ids = set(waterloo_ids)
    print(f"Our count: {len(our_ids)}")
    print(f"Waterloo count: {len(waterloo_ids)}")
    extra_ids = [id for id in our_ids if id not in waterloo_ids]
    for id in extra_ids:
        Chant.objects.get(id=id).delete()
        print(f"Extra item removed: {id}")


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument(
            "id",
            type=str,
            help="update one chant (<chant_id>)) or update all chants ('all')",
        )
        parser.add_argument(
            "--remove_extra",
            action="store_true",
            help="add this flag to remove the chants in our database that are no longer present in waterloo database",
        )

    def handle(self, *args, **options):
        # before running this, run sync_indexers, sync_sources, sync_genres, and sync_feasts first
        id = options["id"]
        if id == "all":
            all_chants = get_chant_list(CHANT_ID_FILE)
            # random_ids = random.sample(all_chants, 5)
            # print(random_ids)
            # length = len(all_chants)
            for i, chant_id in enumerate(all_chants):
                # print(chant_id)
                get_new_chant(chant_id)
                # if i % 100 == 0:
                # sleep_time = random.randrange(5, 10)
                # sleep_time = random.randrange(1, 2)
                # print(f"sleeping...{sleep_time}")
                # time.sleep(sleep_time)
                # percent_done = round(((i / length) * 100), 4)
                # sys.stdout.write(f"\r{percent_done} %")
        else:
            get_new_chant(id)

        if options["remove_extra"]:
            remove_extra()
