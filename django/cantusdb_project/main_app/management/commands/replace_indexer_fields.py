from main_app.models import Source
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

# This command is intended as a temporary approach to 
# populate the user-related fields using the indexer-related fields. 
# The goal is to eventually remove the Indexer model and point all fields to User. 
# After running this command, the indexer-related fields can be removed from the Source model.
# The user-related fields can then be renamed as needed. 
# Run with `python manage.py replace_indexer_fields`.
class Command(BaseCommand):
    def handle(self, *args, **options):
        sources = Source.objects.all()
        for source in sources:
            print(source.id)

            inventoried_by = source.inventoried_by.all()
            for indexer in inventoried_by:
                user = get_user_model().objects.get(old_indexer_id=indexer.id)
                source.inventoried_by_u.add(user)

            full_text_entered_by = source.full_text_entered_by.all()
            for indexer in full_text_entered_by:
                user = get_user_model().objects.get(old_indexer_id=indexer.id)
                source.full_text_entered_by_u.add(user)

            melodies_entered_by = source.melodies_entered_by.all()
            for indexer in melodies_entered_by:
                user = get_user_model().objects.get(old_indexer_id=indexer.id)
                source.melodies_entered_by_u.add(user)

            proofreaders = source.proofreaders.all()
            for indexer in proofreaders:
                user = get_user_model().objects.get(old_indexer_id=indexer.id)
                source.proofreaders_u.add(user)

            other_editors = source.other_editors.all()
            for indexer in other_editors:
                user = get_user_model().objects.get(old_indexer_id=indexer.id)
                source.other_editors_u.add(user)
