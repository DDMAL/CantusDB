"""
Test helper functions in permissions.py
"""

from datetime import date, timedelta

from django.test import SimpleTestCase

from main_app.permissions import (
    user_can_view_record_creator,
    KAIATONSERA_SOURCE_IDS,
    KAIATONSERA_VIEWER_GROUP,
)


class UserCanViewRecordCreatorTest(SimpleTestCase):
    """
    Tests for the user_can_view_record_creator helper, which gates the
    "Chant record created by" field. See issue #2077.
    """

    def setUp(self) -> None:
        self.kaiatonsera_source_id = sorted(KAIATONSERA_SOURCE_IDS)[0]
        self.other_source_id = 999999
        self.assertNotIn(self.other_source_id, KAIATONSERA_SOURCE_IDS)

    def test_editor_sees_field(self) -> None:
        self.assertTrue(
            user_can_view_record_creator(self.kaiatonsera_source_id, True, {})
        )

    def test_class_member_sees_field(self) -> None:
        groups = {KAIATONSERA_VIEWER_GROUP: None}
        self.assertTrue(
            user_can_view_record_creator(self.kaiatonsera_source_id, False, groups)
        )

    def test_class_member_with_unexpired_membership_sees_field(self) -> None:
        groups = {KAIATONSERA_VIEWER_GROUP: date.today() + timedelta(days=1)}
        self.assertTrue(
            user_can_view_record_creator(self.kaiatonsera_source_id, False, groups)
        )

    def test_class_member_with_expired_membership_denied(self) -> None:
        groups = {KAIATONSERA_VIEWER_GROUP: date.today() - timedelta(days=1)}
        self.assertFalse(
            user_can_view_record_creator(self.kaiatonsera_source_id, False, groups)
        )

    def test_unrelated_user_denied(self) -> None:
        self.assertFalse(
            user_can_view_record_creator(self.kaiatonsera_source_id, False, {})
        )

    def test_field_hidden_outside_kaiatonsera_sources(self) -> None:
        groups = {KAIATONSERA_VIEWER_GROUP: None}
        # Neither an editor nor a class member sees the field for other sources.
        self.assertFalse(user_can_view_record_creator(self.other_source_id, True, {}))
        self.assertFalse(
            user_can_view_record_creator(self.other_source_id, False, groups)
        )

    def test_missing_source_id_denied(self) -> None:
        self.assertFalse(user_can_view_record_creator(None, True, {}))
