from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
import csv
from django.contrib.auth.models import Group
from main_app.models import Source, Chant
import string
import secrets

ALPHABET: str = string.ascii_letters + string.digits


class Command(BaseCommand):
    def handle(self, *args, **kwargs):
        with open("oldcantususer_uid_role_detailed.csv", "r") as csvinput:
            reader = csv.reader(csvinput)
            next(reader, None)

            User = get_user_model()

            for row in reader:
                uid = row[0]
                new_role = row[2]
                name = row[3]
                surname = row[4]
                institution = row[5]
                city = row[6]
                country = row[7]
                email = row[9]

                user, created = User.objects.get_or_create(id=uid, email=email)

                if created:
                    user.first_name = name
                    user.last_name = surname

                    user.institution = institution
                    user.city = city
                    user.country = country

                    password: str = "".join(secrets.choice(ALPHABET) for _ in range(32))
                    user.set_password(password)

                    user.save()

                if user.groups.first() is None:
                    old_role = "none"
                else:
                    old_role = user.groups.first().name

                roles_weights = {
                    "project manager": 3,
                    "editor": 2,
                    "contributor": 1,
                    "none": 0,
                }

                if new_role != "none":
                    if roles_weights[new_role] > roles_weights[old_role]:
                        user.groups.clear()
                        group = Group.objects.get(name=new_role)
                        group.user_set.add(user)

        with open("editors_source.csv", "r") as csvinput:
            reader = csv.reader(csvinput)

            User = get_user_model()

            for row in reader:
                source_id = row[3]
                user_id = row[7]

                try:
                    user = User.objects.get(id=user_id)
                except User.DoesNotExist:
                    user = None
                try:
                    source = Source.objects.get(id=source_id)
                except Source.DoesNotExist:
                    source = None

                if user is not None and source is not None:
                    user.sources_user_can_edit.add(source)

        with open("editors_chant.csv", "r") as csvinput:
            reader = csv.reader(csvinput)

            User = get_user_model()

            for row in reader:
                chant_id = row[3]
                user_id = row[7]

                try:
                    user = User.objects.get(id=user_id)
                except User.DoesNotExist:
                    user = None
                try:
                    chant = Chant.objects.get(id=chant_id)
                    source = chant.source
                except Chant.DoesNotExist:
                    source = None

                if user is not None and source is not None:
                    user.sources_user_can_edit.add(source)
