from django.test import TestCase
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from main_app.forms import SourceURLForm, get_source_url_formset
from main_app.models import SourceURL

User = get_user_model()


class SourceURLFormPermissionsTest(TestCase):
    def setUp(self):
        # Create user groups
        self.project_manager_group = Group.objects.create(name="project manager")
        self.editor_group = Group.objects.create(name="editor")

        # Create users
        self.project_manager = User.objects.create_user(
            email="pm@test.com", password="testpass123"
        )
        self.project_manager.groups.add(self.project_manager_group)

        self.regular_user = User.objects.create_user(
            email="user@test.com", password="testpass123"
        )
        self.regular_user.groups.add(self.editor_group)

    def test_project_manager_sees_all_url_types(self):
        """Project managers should see all URL type options including IIIF Manifest"""
        form = SourceURLForm(user=self.project_manager)
        url_type_choices = form.fields["url_type"].choices

        # Should include all choices from SourceURL.URLTypes plus empty choice
        expected_choices = [("", "---------")] + list(SourceURL.URLTypes.choices)
        self.assertEqual(list(url_type_choices), expected_choices)

        # Specifically check that IIIF Manifest is included
        iiif_choice = (SourceURL.URLTypes.IIIF_MANIFEST, "IIIF Manifest")
        self.assertIn(iiif_choice, url_type_choices)

    def test_regular_user_does_not_see_iiif_manifest(self):
        """Regular users should not see the IIIF Manifest option"""
        form = SourceURLForm(user=self.regular_user)
        url_type_choices = form.fields["url_type"].choices

        # Should not include IIIF Manifest
        iiif_choice = (SourceURL.URLTypes.IIIF_MANIFEST, "IIIF Manifest")
        self.assertNotIn(iiif_choice, url_type_choices)

        # Should include other choices plus empty choice
        host_choice = (
            SourceURL.URLTypes.HOST_INSTITUTION_RECORD,
            "Host Institution Record",
        )
        external_choice = (SourceURL.URLTypes.EXTERNAL_IMAGES, "External Images")
        empty_choice = ("", "---------")
        self.assertIn(host_choice, url_type_choices)
        self.assertIn(external_choice, url_type_choices)
        self.assertIn(empty_choice, url_type_choices)

        # Should have 3 choices total: empty + 2 non-IIIF choices
        self.assertEqual(len(url_type_choices), 3)

    def test_anonymous_user_does_not_see_iiif_manifest(self):
        """Anonymous users should not see the IIIF Manifest option"""
        form = SourceURLForm(user=None)
        url_type_choices = form.fields["url_type"].choices

        # Should not include IIIF Manifest
        iiif_choice = (SourceURL.URLTypes.IIIF_MANIFEST, "IIIF Manifest")
        self.assertNotIn(iiif_choice, url_type_choices)

        # Should have 3 choices total: empty + 2 non-IIIF choices
        self.assertEqual(len(url_type_choices), 3)

    def test_project_manager_can_submit_iiif_manifest(self):
        """Project managers should be able to submit IIIF Manifest URL type"""
        form_data = {
            "url": "https://example.com/iiif/manifest",
            "url_type": SourceURL.URLTypes.IIIF_MANIFEST,
            "url_description": "Test IIIF manifest",
        }
        form = SourceURLForm(data=form_data, user=self.project_manager)
        self.assertTrue(form.is_valid())

    def test_regular_user_cannot_submit_iiif_manifest(self):
        """Regular users should not be able to submit IIIF Manifest URL type"""
        form_data = {
            "url": "https://example.com/iiif/manifest",
            "url_type": SourceURL.URLTypes.IIIF_MANIFEST,
            "url_description": "Test IIIF manifest",
        }
        form = SourceURLForm(data=form_data, user=self.regular_user)
        self.assertFalse(form.is_valid())
        self.assertIn("url_type", form.errors)

    def test_formset_factory_passes_user_correctly(self):
        """Test that the formset factory correctly passes user to individual forms"""
        FormSet = get_source_url_formset(user=self.project_manager)
        formset = FormSet()

        # Check that each form in the formset has the correct user
        for form in formset.forms:
            self.assertEqual(form.user, self.project_manager)
            # Project manager should see IIIF option
            iiif_choice = (SourceURL.URLTypes.IIIF_MANIFEST, "IIIF Manifest")
            self.assertIn(iiif_choice, form.fields["url_type"].choices)

        # Test with regular user
        FormSet = get_source_url_formset(user=self.regular_user)
        formset = FormSet()

        for form in formset.forms:
            self.assertEqual(form.user, self.regular_user)
            # Regular user should not see IIIF option
            iiif_choice = (SourceURL.URLTypes.IIIF_MANIFEST, "IIIF Manifest")
            self.assertNotIn(iiif_choice, form.fields["url_type"].choices)
