from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
import csv
from django.contrib.auth.models import Group

class Command(BaseCommand):

    def handle(self, *args, **kwargs):
        with open('oldcantususer_uid_role_detailed.csv','r') as csvinput:
            reader = csv.reader(csvinput)
            next(reader, None)

            User = get_user_model()

            for row in reader:
                uid = row[0]
                new_role = row[2]
                name = row[3]
                surname = row[4]
                institution = row[5]
                country = row[7]

                user, created = User.objects.get_or_create(
                    username = f"{name}_{uid}",
                    id = uid,
                    first_name = name,
                    last_name = surname,
                    institution = institution,
                    country = country
                )

                if created:
                    user.set_password("cantusdb")
                    user.save()

                if new_role != "none":
                    group = Group.objects.get(name=new_role) 
                    group.user_set.add(user)
