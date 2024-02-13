from main_app.models import Chant, Genre, Source
from typing import Optional
import csv


def write_csv_to_file(chants) -> None:
    with open("cantus_dump.csv", "w", newline="") as file:
        writer = csv.writer(file)
        header = [
            "chant_id",
            "incipit",
            "genre",
            "mode",
            "finalis",
            "absolute_url",
            "src_link",
            "cantus_id",
            "indexing_notes",
            "source_description",
        ]

        writer.writerow(header)
        for chant in chants:
            genre: Optional[Genre] = chant.genre
            genre_description: str
            try:
                genre_description = genre.description
            except AttributeError:  # genre is None
                genre_description = ""

            source: Source = chant.source
            source_description: Optional[str] = source.description

            writer.writerow(
                [
                    chant.id,
                    chant.incipit,
                    genre_description,
                    chant.mode,
                    chant.finalis,
                    f"https://cantusdatabase.org/chant/{chant.id}",
                    f"https://cantusdatabase.org/source/{chant.source.id}",
                    chant.cantus_id,
                    chant.indexing_notes,
                    source_description,
                ]
            )


def create_csv():
    thousand_chants = (
        Chant.objects.all()
        .filter(source__published=True)
        .filter(finalis__isnull=False)
        .order_by("?")[:1_000]
    )
    write_csv_to_file(thousand_chants)
