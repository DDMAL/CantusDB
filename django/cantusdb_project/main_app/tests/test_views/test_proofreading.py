from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from main_app.tests.make_fakes import (
    make_fake_source,
    make_fake_chant,
    make_fake_segment,
)
from django.contrib.auth.models import Group


class ProofreadingOverviewViewTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        Group.objects.create(name="project manager")
        Group.objects.create(name="contributor")
        Group.objects.create(name="editor")
        cls.cantus_segment = make_fake_segment(id=4063)
        cls.other_segment = make_fake_segment(id=4064, name="Other Segment")

    def setUp(self):
        self.client = Client()
        self.user = get_user_model().objects.create_superuser(
            "test@example.com", "password"
        )
        self.client.login(username="test@example.com", password="password")
        self.url = reverse("proofread")
        project_manager = Group.objects.get(name="project manager")
        project_manager.user_set.add(self.user)

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
        editor_group.user_set.add(editor_user)

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
        sources_to_proofread = response.context["sources_to_proofread"]
        self.assertIn(source1, sources_to_proofread)
        self.assertIn(source2, sources_to_proofread)
        self.assertNotIn(source3, sources_to_proofread)

    def test_context_data(self):
        source1 = make_fake_source(title="Source 1", segment=[self.cantus_segment])
        make_fake_chant(source=source1)
        source2 = make_fake_source(title="Source 2", segment=[self.cantus_segment])
        chant1 = make_fake_chant(source=source1)
        response = self.client.get(self.url)
        sources_to_proofread = response.context["sources_to_proofread"]
        self.assertIn(source1, sources_to_proofread)
        self.assertNotIn(source2, sources_to_proofread)

    def test_search_functionality(self):
        source1 = make_fake_source(title="Test Source", segment=[self.cantus_segment])
        make_fake_chant(source=source1)
        response = self.client.get(self.url, {"q": "Test"})
        self.assertIn(source1, response.context["sources_to_proofread"])

        response = self.client.get(self.url, {"q": "NonExistent"})
        self.assertEqual(len(response.context["sources_to_proofread"]), 0)

    def test_sortable_headers(self):
        response = self.client.get(self.url, {"order": "country"})
        self.assertEqual(response.status_code, 200)

    def test_pagination(self):
        for i in range(60):
            source = make_fake_source(
                title=f"Source {i}", segment=[self.cantus_segment]
            )
            make_fake_chant(source=source)

        response = self.client.get(self.url, {"page": 1})
        self.assertEqual(response.status_code, 200)
        self.assertTrue("page_obj" in response.context)
        self.assertEqual(len(response.context["sources_to_proofread"]), 50)

        response2 = self.client.get(self.url, {"page": 2})
        self.assertEqual(response2.status_code, 200)
        self.assertTrue("page_obj" in response2.context)
        self.assertEqual(len(response2.context["sources_to_proofread"]), 10)

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
        sources_in_context = response.context["sources_to_proofread"]
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
        sources_to_proofread = response.context["sources_to_proofread"]
        self.assertIn(source_correct_segment, sources_to_proofread)
        self.assertNotIn(source_other_segment, sources_to_proofread)
