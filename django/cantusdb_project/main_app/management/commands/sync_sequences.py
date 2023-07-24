from main_app.models import Genre, Source, Sequence
from django.core.management.base import BaseCommand
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.core.validators import URLValidator
import requests, json
from django.contrib.auth import get_user_model

SEQUENCE_ID_FILE = "sequence_list.txt"
USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_11_6) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/11.1.2 Safari/605.1.15",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_5) AppleWebKit/603.3.8 (KHTML, like Gecko) Version/10.1.2 Safari/603.3.8",
]


def get_seq_list(seq_id_file):
    seq_list = []
    file = open(seq_id_file, "r")
    for line in file:
        line = line.strip("\n")
        seq_list.append(line)
    file.close()
    return seq_list


def get_new_sequence(seq_id):
    url = f"http://cantus.uwaterloo.ca/json-node/{seq_id}"
    headers = {"User-Agent": USER_AGENTS[0]}
    print(f"getting {seq_id}")

    try:
        response = requests.get(url, headers, timeout=20)
    except:
        print(f"retrying: {seq_id}")
        headers = {"User-Agent": USER_AGENTS[1]}
        response = requests.get(url, headers, timeout=20)
    print(f"got json for {seq_id}")
    json_response = json.loads(response.content)

    # mysterious field, status 0 for unpublished source (visible in db, denied entry on web), status 1 for published
    try:
        status = json_response["status"]
        if status != "1":
            with open("error_log.txt", "a") as error_file:
                error_file.write(f"sequence {seq_id} STATUS {status} ")
                error_file.write("\n")
    except TypeError:
        assert json_response == False
        with open("error_log.txt", "a") as error_file:
            error_file.write(f"sequence {seq_id} json not found")
            error_file.write("\n")
        return

    try:
        author_id = json_response["uid"]
        author = get_user_model().objects.get(id=author_id)
    except (KeyError, TypeError, ObjectDoesNotExist):
        author = None

    try:
        title = json_response["title"]
    except KeyError:
        title = None
        with open("error_log.txt", "a") as error_file:
            error_file.write(f"sequence {seq_id} missing title")
            error_file.write("\n")

    try:
        incipit = json_response["field_incipit"]["und"][0]["value"]
    except (KeyError, TypeError):
        incipit = None
        with open("error_log.txt", "a") as error_file:
            error_file.write(f"sequence {seq_id} missing incipit")
            error_file.write("\n")

    try:
        siglum = json_response["field_siglum_chant"]["und"][0]["value"]
    except (KeyError, TypeError):
        siglum = None

    try:
        folio = json_response["field_folio"]["und"][0]["value"]
    except (KeyError, TypeError):
        folio = None

    try:
        s_sequence = json_response["field_sequence_text"]["und"][0]["value"]
    except (KeyError, TypeError):
        s_sequence = None

    try:
        genre_id = json_response["field_mc_genre"]["und"][0]["tid"]
        genre = Genre.objects.get(id=genre_id)
    except (KeyError, TypeError):
        genre = None

    try:
        rubrics = json_response["field_rubrics"]["und"][0]["value"]
    except (KeyError, TypeError):
        rubrics = None

    try:
        analecta_hymnica = json_response["field_analecta_hymnica"]["und"][0]["value"]
    except (KeyError, TypeError):
        analecta_hymnica = None

    try:
        indexing_notes = json_response["field_indexing_notes"]["und"][0]["value"]
    except (KeyError, TypeError):
        indexing_notes = None

    try:
        date = json_response["field_date"]["und"][0]["value"]
    except (KeyError, TypeError):
        date = None

    try:
        col1 = json_response["field_col1"]["und"][0]["value"]
    except (KeyError, TypeError):
        col1 = None

    try:
        col2 = json_response["field_col2"]["und"][0]["value"]
    except (KeyError, TypeError):
        col2 = None

    try:
        col3 = json_response["field_col3"]["und"][0]["value"]
    except (KeyError, TypeError):
        col3 = None

    try:
        ah_volume = json_response["field_ah_vol"]["und"][0]["value"]
    except (KeyError, TypeError):
        ah_volume = None

    try:
        source_id = json_response["field_source"]["und"][0]["target_id"]
        source = Source.objects.get(id=source_id)
    except (KeyError, TypeError):
        with open("error_log.txt", "a") as error_file:
            error_file.write(f"Sequence {seq_id} empty source")
            error_file.write("\n")
        source = None
    except ObjectDoesNotExist:
        # before running this script, we should have run sync_sources, so we should have all sources by now
        # if some chants have unknown source, write those to log
        with open("error_log.txt", "a") as error_file:
            error_file.write(f"Sequence {seq_id} Unknown source {source_id}")
            error_file.write("\n")
        source = None

    try:
        cantus_id = json_response["field_cantus_id"]["und"][0]["value"]
    except (KeyError, TypeError):
        cantus_id = None

    try:
        image_link = json_response["field_image_link_chant"]["und"][0]["value"]
        validate = URLValidator()
        validate(image_link)
    except (KeyError, TypeError):
        image_link = None
    except ValidationError:
        image_link = None
        print(f"sequence {seq_id} invalid image link")

    seq_obj, created = Sequence.objects.update_or_create(
        id=seq_id,
        defaults={
            "visible_status": status,
            "created_by": author,
            "title": title,
            "siglum": siglum,
            "incipit": incipit,
            "folio": folio,
            "s_sequence": s_sequence,
            "genre": genre,
            "rubrics": rubrics,
            "analecta_hymnica": analecta_hymnica,
            "indexing_notes": indexing_notes,
            "date": date,
            "col1": col1,
            "col2": col2,
            "col3": col3,
            "ah_volume": ah_volume,
            "source": source,
            "cantus_id": cantus_id,
            "image_link": image_link,
            "json_info": json_response,
        },
    )
    if created:
        print(f"Created new sequence {seq_id}")


def remove_extra():
    waterloo_ids = get_seq_list(SEQUENCE_ID_FILE)
    our_ids = list(Sequence.objects.all().values_list("id", flat=True))
    our_ids = [str(id) for id in our_ids]
    waterloo_ids = set(waterloo_ids)
    print(f"Our count: {len(our_ids)}")
    print(f"Waterloo count: {len(waterloo_ids)}")
    extra_ids = [id for id in our_ids if id not in waterloo_ids]
    for id in extra_ids:
        Sequence.objects.get(id=id).delete()
        print(f"Extra item removed: {id}")


def make_dummy_sequence() -> None:
    """
    creates a dummy seqence with an ID of 1_000_000. This ensures that all new sequences
    created in NewCantus have IDs greater than 1_000_000. This, in turn, ensures that
    requests to /node/<id> URLS can be redirected to their proper chant/source/article
    detail page (all objects originally created in OldCantus have unique IDs, so there
    is no ambiguity as to which page a /node/ URL should lead.)
    """
    try:
        Sequence.objects.get(id=1_000_000)
        print(
            "Tried to create a dummy sequence with id=1000000. "
            "A sequence with id=1000000 already exists. "
            "Aborting attempt to create a new dummy sequence."
        )
        return
    except Source.DoesNotExist:
        pass

    dummy_source = Source.objects.get(id=1_000_000, published=False)
    Sequence.objects.create(
        title="DUMMY",
        source=dummy_source,
        manuscript_full_text_std_spelling=(
            "This unpublished dummy sequence exists in order that all newly created "
            "sequences have IDs greater than 1,000,000 (which ensures that requests "
            "made to /node/<id> URLs can be redirected to their proper "
            "chant/sequence/article detail page). Once a sequence with an ID greater than "
            "1,000,000 has been created, this dummy sequence may be safely deleted."
        ),
    )
    dummy_sequence = Sequence.objects.filter(title="DUMMY")
    dummy_sequence.update(id=1_000_000)
    return dummy_sequence


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument(
            "id",
            type=str,
            help="update one sequence (<seq_id>)) or update all sequences ('all')",
        )
        parser.add_argument(
            "--remove_extra",
            action="store_true",
            help="add this flag to remove the sequences in our database that are no longer present in waterloo database",
        )

    def handle(self, *args, **options):
        # before running this, run sync_indexers, sync_sources, sync_genres, sync_feasts, and sync_chants first
        id = options["id"]
        if id == "all":
            all_seqs = get_seq_list(SEQUENCE_ID_FILE)
            total = len(all_seqs)
            counter = 0
            for i, seq_id in enumerate(all_seqs):
                # print(seq_id)
                get_new_sequence(seq_id)
                if counter % 500 == 0:
                    print(
                        f"---------------- {counter} of {total} chants synced --------------"
                    )
                counter += 1
        else:
            get_new_sequence(id)

        if options["remove_extra"]:
            remove_extra()
