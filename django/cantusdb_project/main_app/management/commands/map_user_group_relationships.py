"""
A command meant to be run in a single use to transfer use of the
default django.contrib.auth Group model to the custom Group model
defined in the users app.

The command adds all "editor" users to the new "editor" group. The
old "contributor" and "project manager" groups are deprecated.
"""

from typing import Any

from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group as OldGroup
from users.models import Group


class Command(BaseCommand):

    def handle(self, *args: Any, **options: Any) -> None:
        # Get all users in the old "editor" group.
        editor_group = OldGroup.objects.get(name="editor")
        editor_users = editor_group.user_set.all()
        editor_group_new = Group.objects.get(name="editor")
        for user in editor_users:
            # Add each user to the new "editor" group.
            user.groups_new.add(editor_group_new)
            user.save()
