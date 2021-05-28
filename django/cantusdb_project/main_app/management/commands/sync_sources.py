from main_app.models import (
    Source,
    Century,
    Indexer,
    Notation,
    Provenance,
    RismSiglum,
    Segment,
)
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
    # this will not get all sources, the json export is not complete
    # published_sources = []
    # url = "https://cantus.uwaterloo.ca/json-sources"
    # response = requests.get(url)
    # json_response = json.loads(response.content)
    # for key in json_response:
    #     published_sources.append(key)
    # return published_sources


def get_century_name(century_id):
    assert len(century_id) == 4
    url = "https://cantus.uwaterloo.ca/century/{}".format(century_id)
    response = requests.get(url)
    doc = lh.fromstring(response.content)
    century_name = doc.xpath("//h1")[0].text_content()
    return century_name


def get_indexers(json_response, field_name):
    indexers = []
    if json_response[field_name]:
        for und in json_response[field_name]["und"]:
            indexer_id = und["nid"]
            indexer = Indexer.objects.get(id=indexer_id)
            indexers.append(indexer)
    return indexers


def get_new_source(source_id):
    url = f"http://cantus.uwaterloo.ca/json-node/{source_id}"
    response = requests.get(url)
    json_response = json.loads(response.content)
    title = json_response["title"]
    # mysterious field, status 0 for unpublished source (visible in db, denied entry on web), status 1 for published
    status = json_response["status"]
    if status != "1":
        print(f"STATUS {status} at source {source_id}")

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
        source_status_id = json_response["field_source_status_tax"]["und"][0][
            "tid"
        ]  # 4212

        # these mappings are estimated by observing individual sources in the database
        # not necessarily accurate, but it gives the same results between the old and new cantus
        # published / unpublished
        if source_status_id == "4208":  # 234 / 19
            source_status = "Published / Proofread pending"
        elif source_status_id == "4209":  # 0 / 1
            source_status = "Unpublished / Editing process"
        elif source_status_id == "4210":  # 0 / 3
            source_status = "Unpublished / Indexing process"
        elif source_status_id == "4211":  # 1 / 0
            source_status = "Editing process (not all the fields have been proofread)"
        elif source_status_id == "4212":  # 162 / 0
            source_status = "Published / Complete"
        elif source_status_id == "4213":  # 1 / 1
            source_status = "Unpublished / Proofread pending"
        elif source_status_id == "4217":  # 3 / 5
            source_status = "Unpublished / Proofreading process"
            # source_status_id == None # 326 / 9
        else:
            print(f"Unknown source status: {source_status_id}")
            return
    except (KeyError, TypeError):
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
            # notation_name = get_notation_name(century_id)
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
            print(f"Unknown cursus {cursus_id}")
    except (KeyError, TypeError):
        cursus = None

    try:
        segment_id = json_response["field_segment"]["und"][0]["tid"]  # 4063
        if segment_id == "4063":
            segment_name = "CANTUS Database"
        elif segment_id == "4064":
            segment_name = "Bower Sequence Database"
        else:
            print(f"Unknown segment: {segment_id}")
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
        full_source = None

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

    # try:
    #     # current editors are User, the other fields are Indexer
    #     current_editors_id = json_response["field_editors"]["und"][0]["uid"]  # 613
    # except (KeyError, TypeError):
    #     current_editors = None

    inventoried_by = get_indexers(json_response, "field_indexer")
    full_text_entered_by = get_indexers(json_response, "field_full_texts_entered_by")
    melodies_entered_by = get_indexers(json_response, "field_melody_indexer")
    proofreaders = get_indexers(json_response, "field_proofreader")
    other_editors = get_indexers(json_response, "field_editors_other")

    source_obj, created = Source.objects.update_or_create(
        id=source_id,
        defaults={
            "title": title,
            "visible_status": status,
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

    source_obj.century.set(century)
    source_obj.notation.set(notation)
    # source_obj.current_editors.set(current_editors) # user, not indexer
    source_obj.inventoried_by.set(inventoried_by)
    source_obj.full_text_entered_by.set(full_text_entered_by)
    source_obj.melodies_entered_by.set(melodies_entered_by)
    source_obj.proofreaders.set(proofreaders)
    source_obj.other_editors.set(other_editors)

    return source_obj


def remove_extra_sources():
    waterloo_sources = get_source_list()
    our_sources = list(Source.objects.all().values_list("id", flat=True))
    our_sources = [str(id) for id in our_sources]
    waterloo_sources = set(waterloo_sources)
    print(len(our_sources))
    print(len(waterloo_sources))
    extra_sources = [id for id in our_sources if id not in waterloo_sources]
    for source in extra_sources:
        Source.objects.get(id=source).delete()
        print(f"Extra source removed: {source}")


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
                # print(source.title)
        else:
            new_source = get_new_source(id)
            print(new_source.title)

        if options["remove_extra"]:
            remove_extra_sources()

