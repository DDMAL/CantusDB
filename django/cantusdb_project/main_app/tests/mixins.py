"""
Assorted mixins for test cases.
"""

from typing import Optional
from django.http import HttpResponse
from bs4 import BeautifulSoup


class HTMLContentsTestMixin:
    """
    A mixin that provides a `assertParsedContains` method to check for
    HTML contents in the response content.

    This mixin uses the BeautifulSoup library to parse the response content
    which is especially useful for dealing with more complex HTML checks and
    for dealing with disparate whitespace in rendered HTML.
    """

    def assertParsedContains(
        self,
        response: HttpResponse,
        text: str,
        count: Optional[int] = None,
        status_code: int = 200,
        html: bool = True,
    ) -> None:
        """
        Asserts that the response content contains the given text.

        :param response: The response object to check.
        :param text: The text to check for in the response content.
        :param count: The number of times the text should appear in the
            response content.
        :param status_code: The expected status code of the response.
        :param html: If True, the text is treated as HTML and parsed with
            BeautifulSoup.
        """
        self.assertEqual(
            response.status_code,
            status_code,
            "Response status code was %d (expected %d)"
            % (response.status_code, status_code),
        )

        if html:
            soup = BeautifulSoup(response.content, "lxml")
            contents = str(soup)
        else:
            contents = response.content.decode("utf-8")

        if count is not None:
            self.assertEqual(
                contents.count(text),
                count,
                "The text '%s' appeared %d times in the response "
                "content (expected %d times)" % (text, contents.count(text), count),
            )
        else:
            self.assertIn(
                text,
                contents,
                "The text '%s' was not found in the response content" % text,
            )
