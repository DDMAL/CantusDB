import json
import os
from sys import stdout
from datetime import datetime
from collections import defaultdict
from django.db.models.query import QuerySet
from django.core.management.base import BaseCommand
from main_app.models import Chant


class Command(BaseCommand):
    def handle(self, *args, **kwargs) -> None:
        CACHE_DIR: str = "api_cache"
        FILEPATH: str = "api_cache/concordances.json"
        start_time: str = datetime.now().isoformat()
        stdout.write("Running update_cached_concordances " f"at {start_time}.\n")
        concordances: dict = get_concordances()
        write_time: str = datetime.now().isoformat()
        metadata: dict = {
            "last_updated": write_time,
        }
        data_and_metadata: dict = {
            "data": concordances,
            "metadata": metadata,
        }
        stdout.write("Attempting to make directory " f"at {CACHE_DIR} to hold cache: ")
        try:
            os.mkdir(CACHE_DIR)
            stdout.write(f"successfully created directory at {CACHE_DIR}.\n")
        except FileExistsError:
            stdout.write(f"directory at {CACHE_DIR} already exists.\n")
        stdout.write(f"Writing concordances to {FILEPATH} " f"at {write_time}.\n")
        with open(FILEPATH, "w") as json_file:
            json.dump(data_and_metadata, json_file)
        end_time = datetime.now().isoformat()
        stdout.write(
            f"Concordances successfully written to {FILEPATH} at {end_time}.\n\n"
        )


def get_concordances() -> dict:
    DOMAIN: str = "https://cantusdatabase.org"

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

    stdout.write("Processing chants\n")
    concordances: defaultdict = defaultdict(list)
    for chant in values:
        source_id: int = chant["source_id"]
        source_absolute_url: str = f"{DOMAIN}/source/{source_id}/"
        chant_id: int = chant["id"]
        chant_absolute_url: str = f"{DOMAIN}/chant/{chant_id}/"

        concordances[chant["cantus_id"]].append(
            {
                "siglum": chant["source__siglum"],
                "srclink": source_absolute_url,
                "chantlink": chant_absolute_url,
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
        )

    stdout.write(f"All chants processed - found {len(concordances)} Cantus IDs\n")

    return dict(concordances)
