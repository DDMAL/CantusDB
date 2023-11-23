from main_app.models import Source, Chant
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from sys import stdout
from django.db.models.query import QuerySet
from typing import Optional

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


def reassign_sources() -> None:
    CHUNK_SIZE = 1_000
    sources: QuerySet[Source] = Source.objects.all()
    sources_count: int = sources.count()
    start_index: int = 0
    while start_index <= sources_count:
        stdout.write(f"processing chunk with {start_index=}\n")
        chunk: QuerySet[Source] = sources[start_index : start_index + CHUNK_SIZE]
        for source in chunk:
            old_creator: Optional[User] = source.created_by

            updated_id: Optional[int] = None
            try:
                updated_id: int = USER_ID_MAPPING[old_creator.id]
            except (
                KeyError,  # old_creator.id not in USER_ID_MAPPING
                AttributeError,  # old_creator is None
            ):
                pass

            if updated_id is None:
                # user ID doesn't need to be remapped
                continue

            updated_creator: Optional[User] = None
            try:
                updated_creator = User.objects.get(id=updated_id)
            except (
                User.DoesNotExist,
                AttributeError,
            ):
                pass

            source.created_by = updated_creator
            source.save()
        start_index += CHUNK_SIZE


def reassign_chants() -> None:
    CHUNK_SIZE = 1_000
    chants: QuerySet[Chant] = Chant.objects.all()
    chants_count: int = chants.count()
    start_index: int = 0
    while start_index <= chants_count:
        stdout.write(f"processing chunk with {start_index=}\n")
        chunk: QuerySet[Chant] = chants[start_index : start_index + CHUNK_SIZE]
        for chant in chunk:
            old_creator: Optional[User] = chant.created_by

            updated_id: Optional[int] = None
            try:
                updated_id: int = USER_ID_MAPPING[old_creator.id]
            except (
                KeyError,  # old_creator.id not in USER_ID_MAPPING
                AttributeError,  # old_creator is None
            ):
                pass

            if updated_id is None:
                # user ID doesn't need to be remapped
                continue

            updated_creator: Optional[User] = None
            try:
                updated_creator = User.objects.get(id=updated_id)
            except User.DoesNotExist:
                pass

            chant.created_by = updated_creator
            chant.save()
        start_index += CHUNK_SIZE


class Command(BaseCommand):
    def handle(self, *args, **kwargs) -> None:
        error_message = (
            "As of late November 2023, this command is not working. "
            "It has been temporarily disabled until the bugs have been worked out."
        )
        raise NotImplementedError(error_message)
        stdout.write("\n\n==== Reassigning Sources ====\n")
        reassign_sources()
        stdout.write("\n== All sources successfully remapped! ==\n")
        stdout.write("\n\n==== Reassigning Chants ====\n")
        reassign_chants()
        stdout.write("\n== All chants successfully remapped! ==\n")
