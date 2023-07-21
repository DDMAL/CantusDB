from main_app.models import (
    Source,
    Century,
    Notation,
    Provenance,
    RismSiglum,
    Segment,
)
from django.contrib.auth import get_user_model
import lxml.html as lh
from django.core.validators import URLValidator
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.core.management.base import BaseCommand
import requests, json


def get_source_list():
    source_list = []
    file = open("source_list.txt", "r")
    for line in file:
        line = line.strip("\n")
        source_list.append(line)
    file.close()
    return source_list


def get_century_name(century_id):
    assert len(century_id) == 4
    url = "https://cantus.uwaterloo.ca/century/{}".format(century_id)
    response = requests.get(url)
    doc = lh.fromstring(response.content)
    century_name = doc.xpath("//h1")[0].text_content()
    return century_name


# this is used for all 'indexer' fields
def get_indexers(json_response, field_name):
    indexers = []
    if json_response[field_name]:
        for und in json_response[field_name]["und"]:
            indexer_id = und["nid"]
            indexer = get_user_model().objects.get(old_indexer_id=indexer_id)
            indexers.append(indexer)
    return indexers


def get_new_source(source_id):
    url = f"http://cantus.uwaterloo.ca/json-node/{source_id}"
    response = requests.get(url)
    json_response = json.loads(response.content)
    title = json_response["title"]

    try:
        author_id = json_response["uid"]
        author = get_user_model().objects.get(id=author_id)
    except (KeyError, TypeError, ObjectDoesNotExist):
        author = None

    try:
        siglum = json_response["field_siglum"]["und"][0]["value"]
    except (KeyError, TypeError):
        siglum = None

    try:
        rism_id = json_response["field_rism"]["und"][0]["tid"]
        # rism_name = ""
        # rism_description = ""
        rism_siglum = RismSiglum.objects.get(id=rism_id)
    except (KeyError, TypeError, ObjectDoesNotExist) as e:
        if type(e) == ObjectDoesNotExist:
            print(f"missing rism {rism_id} for source {source_id}")
            rism_siglum = RismSiglum.objects.create(id=rism_id)
        else:
            rism_siglum = None

    try:
        provenance_id = json_response["field_provenance_tax"]["und"][0]["tid"]
        # for some sources, the provenance_tax field has content but provenance field is empty
        # provenance_name = json_response["field_provenance"]["und"][0]["value"]
        provenance = Provenance.objects.get(id=provenance_id)
    except (KeyError, TypeError, ObjectDoesNotExist) as e:
        if type(e) == ObjectDoesNotExist:
            print(f"missing provenance {provenance_id} for source {source_id}")
            if json_response["field_provenance"]:
                provenance_name = json_response["field_provenance"]["und"][0]["value"]
            else:
                provenance_name = None
            provenance = Provenance.objects.create(
                id=provenance_id, name=provenance_name
            )
        else:
            provenance = None

    try:
        source_status_id = json_response["field_source_status_tax"]["und"][0]["tid"]

        # these codes and the actual source status string have been carefully matched
        # when logged-in at project manager level, old Cantus displays the source status
        # on the source-detail page
        if source_status_id == "4208":
            source_status = "Unpublished / Indexing process"
        elif source_status_id == "4209":
            source_status = "Editing process (not all the fields have been proofread)"
        elif source_status_id == "4210":
            source_status = "Unpublished / Proofread pending"
        elif source_status_id == "4211":
            # as of 2022-08-03, no source in this status
            source_status = "Unpublished / Proofreading process"
        elif source_status_id == "4212":
            source_status = "Published / Complete"
        elif source_status_id == "4213":
            source_status = "Unpublished / Editing process"
        elif source_status_id == "4217":
            source_status = "Published / Proofread pending"
        elif source_status_id == "4547":
            source_status = "Unpublished / No indexing activity"
        else:
            raise Exception(f"UNKNOWN SOURCE STATUS ID {source_status_id}")

    except (KeyError, TypeError):
        source_status_id = None
        source_status = None

    try:
        date = json_response["field_date"]["und"][0]["value"]
    except (KeyError, TypeError):
        date = None

    century = []
    if json_response["field_century"]:
        for und in json_response["field_century"]["und"]:
            century_id = und["tid"]
            century_name = get_century_name(century_id)
            try:
                century_item = Century.objects.get(id=century_id, name=century_name)
                century.append(century_item)
            except ObjectDoesNotExist:
                print(f"missing century {century_id} for source {source_id}")
                century_item = Century.objects.create(id=century_id, name=century_name)
                century.append(century_item)

    notation = []
    if json_response["field_notation"]:
        for und in json_response["field_notation"]["und"]:
            notation_id = und["tid"]
            try:
                notation_item = Notation.objects.get(id=notation_id)
                notation.append(notation_item)
            except ObjectDoesNotExist:
                notation_item = Notation.objects.create(id=notation_id)
                notation.append(notation_item)

    try:
        cursus_id = json_response["field_cursus"]["und"][0]["tid"]
        if cursus_id == "4218":
            cursus = "Monastic"
        elif cursus_id == "4219":
            cursus = "Secular"
        else:
            raise Exception(f"UNKNOWN CURSUS ID {cursus_id}")

    except (KeyError, TypeError):
        cursus = None

    try:
        segment_id = json_response["field_segment"]["und"][0]["tid"]  # 4063
        if segment_id == "4063":
            segment_name = "CANTUS Database"
        elif segment_id == "4064":
            segment_name = "Bower Sequence Database"
        else:
            print(f"Unknown segment {segment_id}")
        segment = Segment.objects.get(id=segment_id, name=segment_name)
    except (KeyError, TypeError, ObjectDoesNotExist) as e:
        if type(e) == ObjectDoesNotExist:
            print(f"missing segment {segment_id} for source {source_id}")
            segment = Segment.objects.create(id=segment_id, name=segment_name)
        else:
            segment = None

    try:
        summary = json_response["field_summary"]["und"][0]["value"]
    except (KeyError, TypeError):
        summary = None

    try:
        liturgical_occasions = json_response["field_liturgical_occasions"]["und"][0][
            "value"
        ]
    except (KeyError, TypeError):
        liturgical_occasions = None

    try:
        description = json_response["body"]["und"][0]["value"]
    except (KeyError, TypeError):
        description = None

    try:
        image_link = json_response["field_image_link"]["und"][0]["value"]
        validate = URLValidator()
        validate(image_link)
    except (KeyError, TypeError):
        image_link = None
    except ValidationError:
        image_link = None
        print(f"source {source_id} invalid image link")

    try:
        full_source_id = json_response["field_complete_fragment"]["und"][0]["target_id"]
        if full_source_id == "4242":
            full_source = True
        elif full_source_id == "4243":
            full_source = False
        else:
            print(f"Unknown full_source_id: {full_source_id}")
    except (KeyError, TypeError):
        full_source = True if segment_id == "4064" else None

    try:
        selected_bibliography = json_response["field_bibliography"]["und"][0]["value"]
    except (KeyError, TypeError):
        selected_bibliography = None

    try:
        indexing_notes = json_response["field_indexing_notes"]["und"][0]["value"]
    except (KeyError, TypeError):
        indexing_notes = None

    try:
        indexing_date = json_response["field_indexing_date"]["und"][0]["value"]
    except (KeyError, TypeError):
        indexing_date = None

    try:
        complete_inventory_id = json_response["field_complete_partial_inventory"][
            "und"
        ][0]["tid"]
        if complete_inventory_id == "4245":
            complete_inventory = True
        elif complete_inventory_id == "4246":
            complete_inventory = False
        else:
            print(f"Unknown complete_inventory_id: {complete_inventory_id}")
    except (KeyError, TypeError):
        complete_inventory = None

    try:
        fragmentarium_id = json_response["field_fragmentarium_id"]["und"][0]["value"]
    except (KeyError, TypeError):
        fragmentarium_id = None

    try:
        dact_id = json_response["field_dact_id"]["und"][0]["value"]
    except (KeyError, TypeError):
        dact_id = None

    # A field on old Cantus. It controls access to sources together with source_status_id
    # possible values: string "0" and "1"
    status_published = int(json_response["status"])

    # a source_status_id of None is considered published, because all sequence sources
    #  have a source_status of None, and they are all published
    if source_status_id in ["4212", "4217", "4547", None]:
        source_status_published = True
    elif source_status_id in ["4208", "4209", "4210", "4211", "4213"]:
        source_status_published = False
    else:
        raise Exception(f"UNKNOWN SOURCE STATUS ID {source_status_id}")

    # this is the only field that controls source access on new Cantus
    # True for published, False for unpublished
    published = status_published and source_status_published

    # current editors are User, the other "people" fields were originally Indexer,
    # but we harmonize them to User anyways
    current_editors = []
    try:
        current_editors_entries = json_response["field_editors"]["und"]
        for entry in current_editors_entries:
            user_id = entry["uid"]
            user = get_user_model().objects.get(id=user_id)
            current_editors.append(user)
    except (KeyError, TypeError):
        current_editors = []

    inventoried_by = get_indexers(json_response, "field_indexer")
    full_text_entered_by = get_indexers(json_response, "field_full_texts_entered_by")
    melodies_entered_by = get_indexers(json_response, "field_melody_indexer")
    proofreaders = get_indexers(json_response, "field_proofreader")
    other_editors = get_indexers(json_response, "field_editors_other")

    source_obj, created = Source.objects.update_or_create(
        id=source_id,
        defaults={
            "title": title,
            "created_by": author,
            "published": published,
            "siglum": siglum,
            "rism_siglum": rism_siglum,
            "provenance": provenance,
            # provenance_notes=provenance_notes, # this seems the same thing as the name of the provenance
            "source_status": source_status,
            "full_source": full_source,  # corresponding to "complete_fragment" in json-export
            "date": date,
            "cursus": cursus,
            "complete_inventory": complete_inventory,
            "fragmentarium_id": fragmentarium_id,
            "dact_id": dact_id,
            "segment": segment,
            "summary": summary,
            "liturgical_occasions": liturgical_occasions,
            "description": description,
            "selected_bibliography": selected_bibliography,
            "image_link": image_link,
            "indexing_notes": indexing_notes,
            "indexing_date": indexing_date,
            "json_info": json_response,
        },
    )
    if created:
        print(f"Created new source {source_id}")

    # set the many-to-many fields
    source_obj.century.set(century)
    source_obj.notation.set(notation)
    # these point to the Indexer model
    source_obj.inventoried_by.set(inventoried_by)
    source_obj.full_text_entered_by.set(full_text_entered_by)
    source_obj.melodies_entered_by.set(melodies_entered_by)
    source_obj.proofreaders.set(proofreaders)
    source_obj.other_editors.set(other_editors)
    # these point to the User model
    source_obj.current_editors.set(current_editors)

    return source_obj


def remove_extra_sources():
    waterloo_sources = get_source_list()
    our_sources = list(Source.objects.all().values_list("id", flat=True))
    our_sources = [str(id) for id in our_sources]
    waterloo_sources = set(waterloo_sources)
    print(len(our_sources))
    print(len(waterloo_sources))
    extra_sources = [id for id in our_sources if id not in waterloo_sources]
    if 1_000_000 in extra_sources:
        extra_sources.remove(1_000_000)
    for source in extra_sources:
        Source.objects.get(id=source).delete()
        print(f"Extra source removed: {source}")


def make_dummy_source() -> None:
    """
    creates a dummy source with an ID of 1_000_000. This ensures that all new sources
    created in NewCantus have IDs greater than 1_000_000. This, in turn, ensures that
    requests to /node/<id> URLS can be redirected to their proper chant/source/article
    detail page (all objects originally created in OldCantus have unique IDs, so there
    is no ambiguity as to which page a /node/ URL should lead.)
    """
    try:
        Source.objects.get(id=1_000_000)
        print(
            "Tried to create a dummy source with id=1000000. "
            "A source with id=1000000 already exists. "
            "Aborting attempt to create a new dummy source."
        )
        return
    except Source.DoesNotExist:
        pass

    cantus_segment = Segment.objects.get(id=4063)
    Source.objects.create(
        segment=cantus_segment,
        siglum="DUMMY",
        published=False,
        title="Unpublished Dummy Source",
        description=(
            "This unpublished dummy source exists in order that all newly created "
            "sources have IDs greater than 1,000,000 (which ensures that requests "
            "made to /node/<id> URLs can be redirected to their proper "
            "chant/source/article detail page). Once a source with an ID greater than "
            "1,000,000 has been created, this dummy source may be safely deleted."
        ),
    )
    dummy_source = Source.objects.filter(siglum="DUMMY")
    dummy_source.update(id=1_000_000)
    return dummy_source


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument(
            "id",
            type=str,
            help="update one source (<source_id>)) or update all sources ('all')",
        )
        parser.add_argument(
            "--remove_extra",
            action="store_true",
            help="add this flag to remove the sources in our database that are no longer present in waterloo database",
        )

    def handle(self, *args, **options):
        # before running this, run sync_indexers first
        id = options["id"]
        if id == "all":
            all_sources = get_source_list()
            for source_id in all_sources:
                print(source_id)
                source = get_new_source(source_id)
        else:
            new_source = get_new_source(id)
            print(new_source.title)

        if options["remove_extra"]:
            remove_extra_sources()
