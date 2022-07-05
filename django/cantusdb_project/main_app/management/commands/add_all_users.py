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
                city = row[6]
                country = row[7]
                username = row[8]
                email = row[9]

                user, created = User.objects.get_or_create(
                    username = username,
                    email = email,
                    id = uid,
                    first_name = name,
                    last_name = surname,
                    institution = institution,
                    city = city,
                    country = country
                )

                if created:
                    user.set_password("cantusdb")
                    user.save()

                if user.groups.first() is None:
                    old_role = "none"
                else:
                    old_role = user.groups.first().name

                roles_weights = {
                    "project manager": 3, 
                    "editor": 2, 
                    "contributor": 1,
                    "none": 0
                }
                
                if new_role != "none":
                    if roles_weights[new_role] > roles_weights[old_role]:
                        user.groups.clear()
                        group = Group.objects.get(name=new_role) 
                        group.user_set.add(user)
