import random

from django.conf import settings
from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model
from main_app.tests.make_fakes import (
    make_fake_source,
    make_fake_chant,
    make_fake_segment,
    make_fake_institution,
)
from main_app.views.proofreading import ProofreadView
from users.models import Group


class ProofreadingOverviewViewTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        Group.objects.create(name="editor")
        cls.cantus_segment = make_fake_segment(id=settings.CANTUS_SEGMENT_ID)
        cls.other_segment = make_fake_segment(
            id=settings.BOWER_SEGMENT_ID, name="Other Segment"
        )
        cls.project_manager_user = get_user_model().objects.create_superuser(
            "pm@example.com", "password"
        )
        cls.url = reverse("proofread-overview")

    def setUp(self):
        self.client.login(username="pm@example.com", password="password")

    def test_url_exists_at_correct_location(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)

    def test_template_used(self):
        response = self.client.get(self.url)
        self.assertTemplateUsed(response, "proofreading_overview.html")

    def test_access_permissions(self):
        # Unauthenticated user
        self.client.logout()
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)

        # User with no groups
        no_group_user = get_user_model().objects.create_user(
            "nogroup@example.com", "password"
        )
        self.client.login(username="nogroup@example.com", password="password")
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 403)

        # Contributor user (not in project manager or editor group)
        contributor_user = get_user_model().objects.create_user(
            "contributor@example.com", "password"
        )
        self.client.login(username="contributor@example.com", password="password")
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 403)

    def test_editor_sees_only_assigned_sources(self):
        # Create an editor user
        editor_group = Group.objects.get(name="editor")
        editor_user = get_user_model().objects.create_user(
            "editor@example.com", "password"
        )
        editor_user.groups_new.add(editor_group)

        source1 = make_fake_source(title="Source 1", segment=[self.cantus_segment])
        make_fake_chant(source=source1)
        source2 = make_fake_source(title="Source 2", segment=[self.cantus_segment])
        make_fake_chant(source=source2)
        source3 = make_fake_source(title="Source 3", segment=[self.cantus_segment])
        make_fake_chant(source=source3)

        # Assign source1 and source2 to the editor
        editor_user.sources_user_can_edit.add(source1, source2)

        # Log in as the editor
        self.client.login(username="editor@example.com", password="password")

        response = self.client.get(self.url)

        # Check that the editor only sees source1 and source2
        sources = response.context["sources"]
        self.assertIn(source1, sources)
        self.assertIn(source2, sources)
        self.assertNotIn(source3, sources)

    def test_context_data(self):
        source1 = make_fake_source(title="Source 1", segment=[self.cantus_segment])
        make_fake_chant(source=source1)
        source2 = make_fake_source(title="Source 2", segment=[self.cantus_segment])
        chant1 = make_fake_chant(source=source1)
        response = self.client.get(self.url)
        sources = response.context["sources"]
        self.assertIn(source1, sources)
        self.assertNotIn(source2, sources)

    def test_search_functionality(self):
        source1 = make_fake_source(title="Test Source", segment=[self.cantus_segment])
        make_fake_chant(source=source1)
        response = self.client.get(self.url, {"q": "Test"})
        self.assertIn(source1, response.context["sources"])

        response = self.client.get(self.url, {"q": "NonExistent"})
        self.assertEqual(len(response.context["sources"]), 0)

    def test_proofread_unpublished_filter(self):
        fully_proofread_kwargs = dict(
            volpiano_proofread=True,
            manuscript_full_text_proofread=True,
            manuscript_full_text_std_proofread=True,
            other_fields_proofread=True,
        )

        proofread_unpublished_source = make_fake_source(
            published=False, segment=[self.cantus_segment]
        )
        make_fake_chant(source=proofread_unpublished_source, **fully_proofread_kwargs)

        needs_proofread_unpublished_source = make_fake_source(
            published=False, segment=[self.cantus_segment]
        )
        make_fake_chant(source=needs_proofread_unpublished_source)

        proofread_published_source = make_fake_source(
            published=True, segment=[self.cantus_segment]
        )
        make_fake_chant(source=proofread_published_source, **fully_proofread_kwargs)

        response = self.client.get(self.url, {"inactive": "proofread_unpublished"})
        sources = list(response.context["sources"])
        self.assertIn(proofread_unpublished_source, sources)
        self.assertNotIn(needs_proofread_unpublished_source, sources)
        self.assertNotIn(proofread_published_source, sources)

    def test_sortable_headers(self):
        response = self.client.get(self.url, {"order": "country"})
        self.assertEqual(response.status_code, 200)

    def test_ordering(self):
        """
        Order on the Proofreading Overview should mirror Browse Sources for the
        shared sort modes: by country (with NULL sigla coalesced to "") and by
        institution siglum + shelfmark.
        """
        sources = []
        # A source from a private collector (NULL siglum).
        private_collector = make_fake_institution(is_private_collector=True)
        sources.append(
            make_fake_source(
                holding_institution=private_collector, segment=[self.cantus_segment]
            )
        )
        # A handful of other sources with distinct institutions.
        inst = None
        for _ in range(10):
            inst = make_fake_institution()
            sources.append(
                make_fake_source(
                    holding_institution=inst, segment=[self.cantus_segment]
                )
            )
        # Another institution sharing the last one's country, to exercise
        # within-country ordering by siglum.
        sources.append(
            make_fake_source(
                holding_institution=make_fake_institution(country=inst.country),
                segment=[self.cantus_segment],
            )
        )
        # A second source under an existing institution, to exercise shelfmark
        # as a tiebreaker.
        sources.append(
            make_fake_source(holding_institution=inst, segment=[self.cantus_segment])
        )
        for s in sources:
            make_fake_chant(source=s)

        with self.subTest("Order by country"):
            response = self.client.get(self.url, {"order": "country"})
            expected = sorted(
                sources,
                key=lambda s: (
                    s.holding_institution.country,
                    s.holding_institution.siglum or "",
                    s.shelfmark,
                ),
            )
            self.assertEqual(expected, list(response.context["sources"]))

            response_desc = self.client.get(
                self.url, {"order": "country", "sort": "desc"}
            )
            self.assertEqual(
                list(reversed(expected)), list(response_desc.context["sources"])
            )

        with self.subTest("Order by source_siglum"):
            # source_siglum sorts by institution siglum then shelfmark, without
            # COALESCE — so NULL sigla (private collectors) land last in asc.
            response = self.client.get(self.url, {"order": "source_siglum"})
            expected = sorted(
                sources,
                key=lambda s: (
                    s.holding_institution.siglum is None,
                    s.holding_institution.siglum or "",
                    s.shelfmark,
                ),
            )
            self.assertEqual(expected, list(response.context["sources"]))

    def test_pagination(self):
        paginate_by = ProofreadView.paginate_by
        full_pages = 2
        for _ in range(paginate_by * full_pages):
            make_fake_chant(source=make_fake_source(segment=[self.cantus_segment]))

        for page_num in range(1, full_pages + 1):
            response = self.client.get(self.url, {"page": page_num})
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.context["is_paginated"])
            self.assertEqual(len(response.context["sources"]), paginate_by)

        random.seed(0)
        overflow = random.randint(1, paginate_by - 1)
        for _ in range(overflow):
            make_fake_chant(source=make_fake_source(segment=[self.cantus_segment]))

        response = self.client.get(self.url, {"page": full_pages + 1})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["sources"]), overflow)

        response = self.client.get(self.url, {"page": "last"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["sources"]), overflow)

        for invalid_page in [-1, 0, "lst", full_pages + 2]:
            response = self.client.get(self.url, {"page": invalid_page})
            self.assertEqual(response.status_code, 404)

    def test_proofreading_stats_display(self):
        source = make_fake_source(segment=[self.cantus_segment], title="Stats Source")
        # Ensure the source has a non-zero number_of_chants if your view relies on it for percent_complete
        # or if the make_fake_chant doesn't update it automatically.
        # For this test, we'll create 5 chants.
        source.number_of_chants = 5
        source.save()

        # Chant 1: All relevant fields populated and proofread
        make_fake_chant(
            source=source,
            volpiano="a-b-c",
            volpiano_proofread=True,
            manuscript_full_text="chant text one",
            manuscript_full_text_proofread=True,
            manuscript_full_text_std_spelling="chant text one std",
            manuscript_full_text_std_proofread=True,
            other_fields_proofread=True,
        )
        # Chant 2: Volpiano needs proofreading
        make_fake_chant(
            source=source,
            volpiano="d-e-f",  # Populated
            volpiano_proofread=False,  # Needs proofreading
            manuscript_full_text="chant text two",
            manuscript_full_text_proofread=True,
            manuscript_full_text_std_spelling="chant text two std",
            manuscript_full_text_std_proofread=True,
            other_fields_proofread=True,
        )
        # Chant 3: Manuscript Full Text needs proofreading
        make_fake_chant(
            source=source,
            volpiano="g-h-i",
            volpiano_proofread=True,
            manuscript_full_text="chant text three",  # Populated
            manuscript_full_text_proofread=False,  # Needs proofreading
            manuscript_full_text_std_spelling="chant text three std",
            manuscript_full_text_std_proofread=True,
            other_fields_proofread=True,
        )
        # Chant 4: Manuscript Full Text Std Spelling needs proofreading
        make_fake_chant(
            source=source,
            volpiano="j-k-l",
            volpiano_proofread=True,
            manuscript_full_text="chant text four",
            manuscript_full_text_proofread=True,
            manuscript_full_text_std_spelling="chant text four std",  # Populated
            manuscript_full_text_std_proofread=False,  # Needs proofreading
            other_fields_proofread=True,
        )
        # Chant 5: Other fields need proofreading
        make_fake_chant(
            source=source,
            volpiano="m-n-o",
            volpiano_proofread=True,
            manuscript_full_text="chant text five",
            manuscript_full_text_proofread=True,
            manuscript_full_text_std_spelling="chant text five std",
            manuscript_full_text_std_proofread=True,
            other_fields_proofread=False,  # Needs proofreading
        )

        # Expected counts
        expected_volpiano_to_proofread = 1
        expected_ms_full_text_to_proofread = 1
        expected_ms_full_text_std_to_proofread = 1
        expected_other_fields_to_proofread = 1
        # Chants 2, 3, 4, 5 each have at least one field needing proofreading
        expected_total_chants_needing_proofread = 4

        # Expected percent_complete calculation
        # Volpiano: 4 proofread / 5 opportunities
        # MS Full Text: 4 proofread / 5 opportunities
        # MS Full Text Std: 4 proofread / 5 opportunities
        # Other Fields: 4 proofread / 5 opportunities (total chants)
        # Total proofread fields = 4 + 4 + 4 + 4 = 16
        # Total opportunities = 5 + 5 + 5 + 5 = 20
        expected_percent_complete = (16 / 20) * 100  # 80.0

        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)

        # Retrieve the source from the context
        # The queryset is paginated, so we get the first item if it exists
        sources_in_context = response.context["sources"]
        self.assertTrue(len(sources_in_context) > 0, "Source not found in context")

        source_from_context = None
        for s_in_ctx in sources_in_context:
            if s_in_ctx.id == source.id:
                source_from_context = s_in_ctx
                break

        self.assertIsNotNone(
            source_from_context, "Target source not found in paginated list"
        )

        # Check annotated values on the source object from context
        self.assertEqual(
            source_from_context.num_volpiano_to_proofread,
            expected_volpiano_to_proofread,
        )
        self.assertEqual(
            source_from_context.num_ms_full_text_to_proofread,
            expected_ms_full_text_to_proofread,
        )
        self.assertEqual(
            source_from_context.num_ms_full_text_std_to_proofread,
            expected_ms_full_text_std_to_proofread,
        )
        self.assertEqual(
            source_from_context.num_other_fields_to_proofread,
            expected_other_fields_to_proofread,
        )
        self.assertEqual(
            source_from_context.total_chants_needing_proofread,
            expected_total_chants_needing_proofread,
        )
        self.assertAlmostEqual(
            source_from_context.percent_complete, expected_percent_complete, places=1
        )

        # If you are using source.number_of_chants directly from the model for "Total Chants" column
        self.assertEqual(source_from_context.number_of_chants, 5)
        # If you are annotating total_chants_in_source, use that:
        # self.assertEqual(source_from_context.total_chants_in_source, 5)

        # Check if the progress bar percentage is displayed correctly (formatted to 1 decimal place in template)
        # Example: <span ...>80.0%</span>
        formatted_percentage = f"{expected_percent_complete:.1f}%"
        self.assertContains(response, formatted_percentage)

    def test_no_sources_message(self):
        response = self.client.get(self.url)
        self.assertContains(
            response, "No sources currently require proofreading attention"
        )

    def test_clear_search(self):
        response = self.client.get(self.url, {"q": "Test"})
        self.assertEqual(response.status_code, 200)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)

    def test_sources_in_other_segments_do_not_show(self):
        source_correct_segment = make_fake_source(
            title="Correct Segment Source", segment=[self.cantus_segment]
        )
        make_fake_chant(source=source_correct_segment)

        source_other_segment = make_fake_source(
            title="Other Segment Source", segment=[self.other_segment]
        )
        make_fake_chant(source=source_other_segment)

        response = self.client.get(self.url)

        # Check that only the source in the correct segment is displayed
        sources = response.context["sources"]
        self.assertIn(source_correct_segment, sources)
        self.assertNotIn(source_other_segment, sources)
