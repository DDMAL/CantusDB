"""
Tests for the robots.txt view
"""

from django.test import TestCase


class RobotsTxtTest(TestCase):
    def test_robots_txt_returns_200(self):
        response = self.client.get("/robots.txt")
        self.assertEqual(response.status_code, 200)

    def test_robots_txt_content_type(self):
        response = self.client.get("/robots.txt")
        self.assertEqual(response["Content-Type"], "text/plain; charset=utf-8")

    def test_robots_txt_blocks_search_endpoints(self):
        response = self.client.get("/robots.txt")
        content = response.content.decode()
        self.assertIn("User-agent: *", content)
        # These are the expensive endpoints that caused the OOM crashes
        self.assertIn("Disallow: /chant-search/", content)
        self.assertIn("Disallow: /searchms/", content)
        self.assertIn("Disallow: /ci-search/", content)
        self.assertIn("Disallow: /melody/", content)

    def test_robots_txt_blocks_api_and_admin_endpoints(self):
        response = self.client.get("/robots.txt")
        content = response.content.decode()
        self.assertIn("Disallow: /ajax/", content)
        self.assertIn("Disallow: /admin/", content)
        self.assertIn("Disallow: /json-sources/", content)

    def test_robots_txt_does_not_block_everything(self):
        response = self.client.get("/robots.txt")
        content = response.content.decode()
        # Should not block all crawling — public pages like /sources/,
        # /chant/<id>, etc. should remain indexable
        self.assertNotIn("Disallow: /\n", content)
