from main_app.models import Chant, Differentia
from django.core.management.base import BaseCommand
from django.db.models import Q
from typing import Optional


class Command(BaseCommand):
    def handle(self, *args, **kwargs):
        CHUNK_SIZE = 500
        chants = Chant.objects.filter(
            Q(differentiae_database__isnull=False) & Q(diff_db__isnull=True)
        )
        chants_count = chants.count()
        start_index = 0
        count = 0
        while start_index <= chants_count:
            self.stdout.write(f"processing chunk with {start_index=}")
            chunk = chants[start_index : start_index + CHUNK_SIZE]

            for chant in chunk:
                try:
                    differentia_id: Optional[str] = chant.differentiae_database
                    if not differentia_id is None:

                        differentia = Differentia.objects.get(
                            differentia_id=differentia_id
                        )
                        if differentia:
                            chant.diff_db = differentia
                        else:
                            # If the Differentia doesn't exist, create a new one
                            differentia = Differentia(
                                differentia_id=differentia_id,
                            )
                            differentia.save()
                            chant.diff_db = differentia
                    chant.save()
                except Differentia.DoesNotExist:
                    print(f"Differentia not found for chant: {chant}")
                count += 1
                if count % 100 == 0:
                    print(
                        f"------------------ {count} of {chants_count} chants updated ------------------"
                    )
            del chunk  # make sure we don't use too much RAM
            start_index += CHUNK_SIZE

        self.stdout.write(
            self.style.SUCCESS("Success! Command has run to completion.\n")
        )
