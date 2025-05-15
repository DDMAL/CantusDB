from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from main_app.models import Source, Chant, ProofreadingStats, Segment
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
        source = make_fake_source(segment=[self.cantus_segment])
        chant1 = make_fake_chant(source=source)
        chant2 = make_fake_chant(source=source)
        chant3 = make_fake_chant(source=source, volpiano_proofread=False)
        chant4 = make_fake_chant(source=source, manuscript_full_text_proofread=False)

        # Calculate proofreading stats for the source
        stats, _ = ProofreadingStats.objects.calculate_and_update_for_source(source)

        response = self.client.get(self.url)

        # Check if the number of unproofread items is displayed correctly
        self.assertContains(response, str(stats.num_ms_full_text_std_to_proofread))
        self.assertContains(response, str(stats.num_ms_full_text_to_proofread))
        self.assertContains(response, str(stats.num_volpiano_to_proofread))
        self.assertContains(response, str(stats.num_other_fields_to_proofread))

        # Check if the progress bar percentage is displayed correctly
        self.assertContains(response, str(stats.percent_complete))

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
