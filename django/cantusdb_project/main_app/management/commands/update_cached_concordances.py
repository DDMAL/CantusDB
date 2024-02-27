import ujson
import os
from sys import stdout
from datetime import datetime
from django.db.models.query import QuerySet
from django.core.management.base import BaseCommand
from main_app.models import Chant


# Usage: `python manage.py update_cached_concordances`
# or `python manage.py update_cached_concordances -d "/path/to/directory/in/which/to/save/concordances"`


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument(
            "-d",
            "--directory",
            help="Optional filepath specifying a directory to output concordances",
            type=str,
            # this default directory should match the value in docker-compose.yml,
            # at services:django:volumes:api_cache_volume
            default="/resources/api_cache",
        )

    def handle(self, *args, **kwargs) -> None:
        cache_dir: str = kwargs["directory"]
        filepath: str = f"{cache_dir}/concordances.json"
        start_time: str = datetime.now().isoformat()
        stdout.write(f"Running update_cached_concordances at {start_time}.\n")
        concordances: dict = get_concordances()
        write_time: str = datetime.now().isoformat()
        stdout.write(f"Attempting to make directory at {cache_dir} to hold cache: ")
        try:
            os.mkdir(cache_dir)
            stdout.write(f"successfully created directory at {cache_dir}.\n")
        except FileExistsError:
            stdout.write(f"directory at {cache_dir} already exists.\n")
        stdout.write(f"Writing concordances to {filepath} at {write_time}.\n")
        with open(filepath, "w") as json_file:
            ujson.dump(concordances, json_file)
        end_time = datetime.now().isoformat()
        stdout.write(
            f"Concordances successfully written to {filepath} at {end_time}.\n\n"
        )


def get_concordances() -> dict:
    """Fetch all published chants in the database, group them by Cantus ID, and return
    a dictionary containing information on each of these chants.

    Returns:
        dict: A dictionary where each key is a Cantus ID and each value is a list all
          published chants in the database with that Cantus ID.
    """

    stdout.write("Querying database for published chants\n")
    published_chants: QuerySet[Chant] = Chant.objects.filter(source__published=True)
    values: QuerySet[dict] = published_chants.select_related(
        "source",
        "feast",
        "genre",
        "office",
    ).values(
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

    concordances: list[dict] = [make_chant_dict(chant) for chant in values]
    return concordances


def make_chant_dict(chant: dict) -> dict:
    """Given a dictionary representing a chant from the database,
    return a chant with the keys specified at
    https://github.com/DDMAL/CantusDB/wiki/APIs#concordances

    Args:
        chant (dict): A dictionary representing a chant from the database,
            from a QuerySet.values() call, with several non-standardized
            keys from database traversals (e.g., `source__siglum`)

    Returns:
        dict: A dictionary representing a chant, with several values standardized
            (e.g., `siglum`) and several values calculated (e.g., `srclink`)
    """
    DOMAIN: str = "https://cantusdatabase.org"
    source_id: int = chant["source_id"]
    source_uri: str = f"{DOMAIN}/source/{source_id}/"
    chant_id: int = chant["id"]
    chant_uri: str = f"{DOMAIN}/chant/{chant_id}/"
    processed_chant: dict = {
        "siglum": chant["source__siglum"],
        "srclink": source_uri,
        "chantlink": chant_uri,
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

    return processed_chant
