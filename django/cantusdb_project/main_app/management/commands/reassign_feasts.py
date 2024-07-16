from django.core.management.base import BaseCommand
from main_app.models import Feast, Chant


class Command(BaseCommand):
    help = "Reassign feasts and update chants accordingly"

    def handle(self, *args, **options):
        feast_mapping = {
            2456: 4474,
            2094: 4475,
        }

        for old_feast_id, new_feast_id in feast_mapping.items():
            try:
                old_feast = Feast.objects.get(id=old_feast_id)
                new_feast = Feast.objects.get(id=new_feast_id)
            except Feast.DoesNotExist as e:
                self.stderr.write(self.style.ERROR(f"Feast not found: {e}"))
                continue

            # Transfer data (if necessary)
            new_feast.name = new_feast.name or old_feast.name
            new_feast.description = new_feast.description or old_feast.description
            new_feast.feast_code = new_feast.feast_code or old_feast.feast_code
            new_feast.notes = new_feast.notes or old_feast.notes
            new_feast.month = new_feast.month or old_feast.month
            new_feast.day = new_feast.day or old_feast.day
            new_feast.save()

            # Reassign chants and sequences
            chants_updated = Chant.objects.filter(feast=old_feast).update(
                feast=new_feast
            )
            self.stdout.write(
                self.style.SUCCESS(
                    f"Reassigned {chants_updated} chants from feast {old_feast_id} to {new_feast_id}"
                )
            )

            old_feast.delete()
            self.stdout.write(self.style.SUCCESS(f"Deleted old feast {old_feast_id}"))

        self.stdout.write(self.style.SUCCESS("Feast reassignment complete."))
