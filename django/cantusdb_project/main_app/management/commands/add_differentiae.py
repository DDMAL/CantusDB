from main_app.models import Chant, Differentia
from django.core.management.base import BaseCommand


# Python script to sync the differentia database with CantusDB. Previously, we had a CharField that represented
# the differentia ID. Now, we change this field to a ForeignKey that points to the new Differentia model that contains
# the ID, melodic transcription, and mode.


DIFFERENTIA_DATA = "differentia_data.txt"


class Command(BaseCommand):
    def handle(self, *args, **options):
        differentia_database = get_differentia_data(DIFFERENTIA_DATA)
        total = len(differentia_database)
        count = 0
        for item in differentia_database:
            differentia_id, melodic_transcription, mode, _ = item
            differentia = Differentia.objects.filter(
                differentia_id=differentia_id
            ).first()

            if differentia:
                differentia.melodic_transcription = melodic_transcription
                differentia.mode = mode
                differentia.save()
            else:
                differentia = Differentia(
                    differentia_id=differentia_id,
                    melodic_transcription=melodic_transcription,
                    mode=mode,
                )
                differentia.save()
            if count % 100 == 0:
                print(
                    f"------------------- {count} of {total} differentia created -------------------"
                )
            count += 1

        CHUNK_SIZE = 1_000
        chants = Chant.objects.all()
        chants_count = chants.count()
        start_index = 0
        count = 0
        while start_index <= chants_count:
            print("processing chunk with start_index of", start_index)
            chunk = chants[start_index : start_index + CHUNK_SIZE]

            # Update Chant model to use foreign key
            for chant in chunk:
                try:
                    differentia_id = chant.differentiae_database
                    # Check if differentiae_database is null
                    if differentia_id:
                        differentia = Differentia.objects.filter(
                            differentia_id=differentia_id
                        ).first()

                        if differentia:
                            chant.differentiae_database_new = differentia
                        else:
                            # If the Differentia doesn't exist, create a new one
                            differentia = Differentia(
                                differentia_id=differentia_id,
                            )
                            differentia.save()
                            chant.differentiae_database_new = differentia

                        chant.save()
                    if count % 100 == 0:
                        print(
                            f"------------------- {count} of {chants_count} chants updated -------------------"
                        )
                except Differentia.DoesNotExist:
                    print(f"Differentia not found for chant: {chant}")
                count += 1
            del chunk  # make sure we don't use too much RAM
            start_index += CHUNK_SIZE


def get_differentia_data(filename):
    differentia_list = []
    with open(filename, "r") as file:
        for line in file:
            line = line.strip()
            values = tuple(line.split(","))
            differentia_list.append(values)
    return differentia_list
