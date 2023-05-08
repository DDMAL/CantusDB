from django.core.management.base import BaseCommand
from main_app.models import Indexer
from users.models import User
from faker import Faker


class Command(BaseCommand):
    def add_arguments(self, parser):
        pass

    def handle(self, *args, **options):
        faker = Faker()
        users = User.objects.all()
        indexers = Indexer.objects.all()

        for user in users:
            # set all users to be non-indexer first
            # those listed as indexers on old Cantus will have this adjusted to True
            user.is_indexer = False
            if user.first_name or user.last_name:
                user.full_name = f"{user.first_name.strip()} {user.last_name.strip()}"
            else:
                user.full_name = "Anonymous User"
            user.save()

        for indexer in indexers:
            indexer_full_name = f"{indexer.given_name} {indexer.family_name}"
            print(indexer_full_name)
            homonymous_users = User.objects.filter(full_name__iexact=indexer_full_name)
            # if the indexer also exists as a user
            if homonymous_users:
                assert homonymous_users.count() == 1
                homonymous_user = homonymous_users.get()
                print(f"homonymous: {homonymous_user.full_name}")
                # keep the user as it is (merge the indexer into existing user)
                # and store the ID of its indexer object
                homonymous_user.old_indexer_id = indexer.id
                homonymous_user.is_indexer = True
                homonymous_user.save()
            # if the indexer doesn't exist as a user
            else:
                # create a new user with the indexer information
                User.objects.create(
                    institution=indexer.institution,
                    city=indexer.city,
                    country=indexer.country,
                    full_name=indexer_full_name,
                    # assign random email to dummy users
                    email=f"{faker.lexify('????????')}@fakeemail.com",
                    # leave the password empty for dummy users
                    # the password can't be empty in login form, so they can't log in
                    password="",
                    old_indexer_id=indexer.id,
                    is_indexer=True,
                )
