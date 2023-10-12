from main_app.models import Source, Chant
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

User = get_user_model()

# TODO:
#   - turn this into an actual command

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
    sources = Source.objects.all()
    sources_count = sources.count()
    start_index = 0
    num_sources_to_remap = 0
    while start_index <= sources_count:
        print(f"processing chunk with {start_index=}")
        chunk = sources[start_index : start_index + CHUNK_SIZE]
        for source in chunk:
            old_creator = source.created_by
            if old_creator and old_creator.id in USER_ID_MAPPING:
                updated_id = USER_ID_MAPPING[old_creator.id]
                updated_creator = User.objects.get(id=updated_id)
                num_sources_to_remap += 1
                source.created_by = updated_creator
                source.save()
        start_index += CHUNK_SIZE
    print(f"{num_sources_to_remap=}")


def reassign_chants() -> None:
    CHUNK_SIZE = 1_000
    chants = Chant.objects.all().order_by("?")
    chants_count = chants.count()
    start_index = 0
    num_chants_to_remap = 0
    while start_index <= chants_count:
        print(f"processing chunk with {start_index=}")
        chunk = chants[start_index : start_index + CHUNK_SIZE]
        for chant in chunk:
            old_creator = chant.created_by
            if old_creator.id in USER_ID_MAPPING:
                updated_id = USER_ID_MAPPING[old_creator.id]
                updated_creator = User.objects.get(id=updated_id)
                num_chants_to_remap += 1
                chant.created_by = updated_creator
                chant.save()
        start_index += CHUNK_SIZE
    print(f"{num_chants_to_remap=}")


class Command(BaseCommand):
    def handle(self, *args, **kwargs) -> None:
        print("", "==== Reassigning Sources ====")
        reassign_sources()
        print("", "==== Reassigning Chants ====")
        reassign_chants()
