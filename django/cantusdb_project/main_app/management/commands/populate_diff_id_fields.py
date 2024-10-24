from main_app.models import Chant, Differentia
from django.core.management.base import BaseCommand
from django.db.models import Q
from typing import Optional
from django.db import transaction


class Command(BaseCommand):
    @transaction.atomic
    def handle(self, *args, **kwargs):
        chants = Chant.objects.filter(
            Q(differentiae_database__isnull=False) & Q(diff_db__isnull=True)
        ).iterator(chunk_size=500)
        chants_total = Chant.objects.filter(
            Q(differentiae_database__isnull=False) & Q(diff_db__isnull=True)
        ).count()
        count = 0

        for chant in chants:
            try:
                differentia_id: Optional[str] = chant.differentiae_database
                differentia = Differentia.objects.get(differentia_id=differentia_id)
            except Differentia.DoesNotExist:
                # If the Differentia doesn't exist, create a new one
                differentia = Differentia(differentia_id=differentia_id)
                differentia.save()
                self.stdout.write(
                    self.style.WARNING(f"Differentia created for chant: {chant}")
                )

            chant.diff_db = differentia
            chant.save()

            count += 1
            if count % 100 == 0:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"------------------ {count} of {chants_total} chants updated ------------------"
                    )
                )

        self.stdout.write(
            self.style.SUCCESS("Success! Command has run to completion.\n")
        )
