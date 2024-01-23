import json
import os
from sys import stdout
from datetime import datetime
from django.db.models.query import QuerySet
from django.core.management.base import BaseCommand
from main_app.models import Chant


class Command(BaseCommand):
    def handle(self, *args, **kwargs) -> None:
        CACHE_DIR: str = "api_cache"
        FILEPATH: str = "api_cache/all_concordances.json"
        start_time: str = datetime.now().isoformat()
        stdout.write("Running save_concordances_to_file " f"at {start_time}.\n")
        concordance_info: dict = get_concordance_info_for_all_cantus_ids()
        write_time: str = datetime.now().isoformat()
        metadata: dict = {
            "last_updated": write_time,
        }
        data_and_metadata: dict = {
            "data": concordance_info,
            "metadata": metadata,
        }
        stdout.write(
            "  save_concordances_to_file: attempting to make directory "
            f"at {CACHE_DIR} to hold cache: "
        )
        try:
            os.mkdir(CACHE_DIR)
            stdout.write(f"successfully created directory at {CACHE_DIR}.\n")
        except FileExistsError:
            stdout.write(f"directory at {CACHE_DIR} already exists.\n")
        stdout.write(
            "  save_concordances_to_file: Writing concordances "
            f"information to {FILEPATH} "
            f"at {write_time}.\n"
        )
        with open(FILEPATH, "w") as json_file:
            json.dump(data_and_metadata, json_file)
        stdout.write(
            "save_concordances_to_file: Concordances successfully written to "
            f"{FILEPATH}.\n\n"
        )


def get_concordance_info_for_all_cantus_ids() -> dict:
    """
    Create a dictionary with information on all published chants
    in the database, grouped by Cantus ID

    Returns:
        dict: a dictionary, with each key being one Cantus ID, and each
        value being a list of chants in the database matching that ID
    """
    cantus_ids = list(get_set_of_cantus_ids())
    cantus_id_count = len(cantus_ids)
    stdout.write(
        f"  save_concordances_to_file: Computing concordances "
        f"information for {cantus_id_count} Cantus IDs.\n"
    )
    dictionary: dict = {
        cantus_id: get_concordance_info_for_cantus_id(cantus_id)
        for cantus_id in cantus_ids
    }

    return dictionary


def get_set_of_cantus_ids() -> set[str]:
    """
    Create a set of all Cantus IDs in the database.

    Returns only those Cantus IDs associated with published chants,
    and ignoring those from the Bower Database.

    Returns [set[str]]: a set of strings, each string being
        a single Cantus ID
    """
    published_chants: QuerySet[Chant] = Chant.objects.filter(source__published=True)
    published_cantus_ids: QuerySet[dict] = published_chants.values("cantus_id")
    unique_cantus_ids: set[str] = set(c["cantus_id"] for c in published_cantus_ids)

    return unique_cantus_ids


def get_concordance_info_for_cantus_id(cantus_id: str) -> list[dict]:
    """
    Given a Cantus ID, return a list of dictionareis containing
    information on all published chants in the database with that Cantus ID

    Args:
    - cantus_id [str]: the Cantus ID

    Returns [list[dict]]: a list of dictionaries, with each dictionary representing
    one chant
    """
    published_chants: QuerySet[Chant] = Chant.objects.filter(source__published=True)
    chants_matching_cantus_id: QuerySet[Chant] = published_chants.filter(
        cantus_id=cantus_id
    ).prefetch_related(
        # .prefetch_related() is necessary in order to be able to follow
        # source__siglum, feast__name, etc. when using .values(), below
        "source",
        "feast",
        "genre",
        "office",
    )
    chants_values: QuerySet[dict] = chants_matching_cantus_id.values(
        "id",
        "source_id",
        "source__siglum",
        "folio",
        "c_sequence",
        "incipit",
        "feast__name",
        "genre__name",
        "office__name",
        "position",
        "cantus_id",
        "image_link",
        "mode",
        "manuscript_full_text_std_spelling",
        "volpiano",
    )
    return [build_chant_dictionary(chant) for chant in chants_values]


def build_chant_dictionary(chant: dict) -> dict:
    DOMAIN: str = "https://cantusdatabase.org"
    source_id: str = chant["source_id"]
    chant_id: str = chant["id"]
    source_absolute_uri: str = f"{DOMAIN}/source/{source_id}/"
    chant_absolute_uri: str = f"{DOMAIN}/chant/{chant_id}/"
    dictionary = {
        "siglum": chant["source__siglum"],
        "srclink": source_absolute_uri,
        "chantlink": chant_absolute_uri,
        "folio": chant["folio"],
        "sequence": chant["c_sequence"],
        "incipit": chant["incipit"],
        "feast": chant["feast__name"],
        "genre": chant["genre__name"],
        "office": chant["office__name"],
        "position": chant["position"],
        "cantus_id": chant["cantus_id"],
        "image": chant["image_link"],
        "mode": chant["mode"],
        "full_text": chant["manuscript_full_text_std_spelling"],
        "melody": chant["volpiano"],
        "db": "CD",
    }
    return dictionary
