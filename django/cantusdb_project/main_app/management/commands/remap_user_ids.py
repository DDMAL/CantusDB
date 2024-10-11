from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db.models.query import QuerySet
import reversion  # type: ignore[import-untyped]

from main_app.models import Source, Chant

User = get_user_model()

USER_ID_MAPPING = {
    # Fake user accounts with sequential numbering were created on NewCantus
    # for OldCantus Indexers. In the time since user accounts were
    # programmatically synced, new user accounts were created on OldCantus,
    # which duplicated these IDs. Then, we manually created new user accounts
    # on NewCantus for these newer users, with new IDs that don't match those
    # in OldCantus.
    #
    # In this dictionary:
    # - Keys represent the IDs of users recently created on OldCantus, which collide
    #   with those of NewCantus Indexers
    # - Values represent the IDs of manually-created users in NewCantus.
    251610: 251660,
    251611: 251661,
    251612: 251662,
    251613: 251663,
    251614: 251664,
    251616: 251665,
    251617: 251666,
    251618: 251667,
    251619: 251668,
    251620: 251669,
    251621: 251670,
    251622: 251671,
    251623: 251672,
    251624: 251673,
    251625: 251674,
    251626: 251657,
    251627: 251675,
    251630: 251676,
    251632: 251678,
    251633: 251679,
    251638: 251656,
    251639: 251680,
    251640: 251681,
    251641: 251682,
    251642: 251683,
    251643: 251684,
    251645: 251685,
}


class Command(BaseCommand):
    def reassign_sources(self) -> None:
        sources: QuerySet[Source] = Source.objects.filter(
            created_by__in=USER_ID_MAPPING.keys()
        )
        num_sources = sources.count()
        self.stdout.write(
            self.style.NOTICE(f"Reassigning {num_sources} sources to new users.")
        )
        source_counter = 0
        for source in sources.iterator(chunk_size=1_000):
            old_creator = source.created_by

            # We know the old_creator is in USER_ID_MAPPING.keys() because of the filter
            # on the queryset.
            updated_id = USER_ID_MAPPING[old_creator.id]  # type: ignore[union-attr]

            updated_creator = User.objects.get(id=updated_id)

            source.created_by = updated_creator
            source.save()
            source_counter += 1
            if source_counter % 100 == 0:
                self.stdout.write(
                    self.style.NOTICE(f"Reassigned {source_counter} sources.")
                )

    def reassign_chants(self) -> None:
        chants: QuerySet[Chant] = Chant.objects.filter(
            created_by__in=USER_ID_MAPPING.keys()
        )
        num_chants = chants.count()
        self.stdout.write(
            self.style.NOTICE(f"Reassigning {num_chants} sources to new users.")
        )
        chant_counter = 0
        for chant in chants.iterator(chunk_size=1_000):
            old_creator = chant.created_by
            # We know the old_creator is in USER_ID_MAPPING.keys() because of the filter
            # on the queryset.
            updated_id: int = USER_ID_MAPPING[old_creator.id]  # type: ignore[union-attr]
            updated_creator = User.objects.get(id=updated_id)
            chant.created_by = updated_creator
            chant.save()
            chant_counter += 1
            if chant_counter % 100 == 0:
                self.stdout.write(
                    self.style.NOTICE(f"Reassigned {chant_counter} chants.")
                )

    def handle(self, *args, **kwargs) -> None:
        with reversion.create_revision():
            self.stdout.write(self.style.NOTICE("==== Reassigning Sources ===="))
            self.reassign_sources()
            self.stdout.write(
                self.style.SUCCESS("== All sources successfully remapped! ==")
            )
            self.stdout.write(self.style.NOTICE("==== Reassigning Chants ===="))
            self.reassign_chants()
            self.stdout.write(
                self.style.SUCCESS("== All chants successfully remapped! ==")
            )
            reversion.set_comment("Command: remap user IDs")
