import io

from django.conf import settings
from django.core.management import call_command
from django.test import TestCase

from main_app.tests.make_fakes import make_fake_segment, make_fake_source


class TestMoveCantoralesContributors(TestCase):
    def setUp(self):
        self.segment = make_fake_segment(
            name="Cantorales in the Americas and Beyond",
            id=settings.CANTORALES_SEGMENT_ID,
        )

    def _make_cantorales_source(self, **kwargs):
        source = make_fake_source(**kwargs)
        source.segment_m2m.set([self.segment])
        return source

    def test_moves_inventoried_users_to_contributors(self):
        source = self._make_cantorales_source(shelfmark="Cant 1")
        # make_fake_source seeds one user in each editor M2M.
        inventoried_ids = set(source.inventoried_by.values_list("id", flat=True))
        self.assertTrue(inventoried_ids)
        original_contributor_ids = set(
            source.source_data_contributed_by.values_list("id", flat=True)
        )

        call_command("move_cantorales_contributors", stdout=io.StringIO())

        source.refresh_from_db()
        # inventoried_by is emptied; its users are now data contributors.
        self.assertEqual(set(source.inventoried_by.values_list("id", flat=True)), set())
        self.assertEqual(
            set(source.source_data_contributed_by.values_list("id", flat=True)),
            original_contributor_ids | inventoried_ids,
        )

    def test_idempotent(self):
        source = self._make_cantorales_source(shelfmark="Cant 1")

        call_command("move_cantorales_contributors", stdout=io.StringIO())
        contributor_ids = set(
            source.source_data_contributed_by.values_list("id", flat=True)
        )
        call_command("move_cantorales_contributors", stdout=io.StringIO())

        source.refresh_from_db()
        self.assertEqual(set(source.inventoried_by.values_list("id", flat=True)), set())
        self.assertEqual(
            set(source.source_data_contributed_by.values_list("id", flat=True)),
            contributor_ids,
        )

    def test_leaves_non_cantorales_sources_untouched(self):
        """Sources outside the Cantorales segment keep their inventoried_by."""
        other = make_fake_source(shelfmark="Other 1")
        original_inventoried_ids = set(
            other.inventoried_by.values_list("id", flat=True)
        )
        self.assertTrue(original_inventoried_ids)

        call_command("move_cantorales_contributors", stdout=io.StringIO())

        other.refresh_from_db()
        self.assertEqual(
            set(other.inventoried_by.values_list("id", flat=True)),
            original_inventoried_ids,
        )
