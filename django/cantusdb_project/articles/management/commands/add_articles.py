from django.core.management.base import BaseCommand
from xml.etree import ElementTree as ET
from articles.models import Article
from datetime import datetime


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument("xml_file", type=str)

    def handle(self, *args, **options):
        file_path = options["xml_file"]
        root = ET.parse(file_path).getroot()

        for article in root.findall("article"):
            title, article_body, author_id, image_link, date_created = (
                None,
                None,
                None,
                None,
                None,
            )

            for element in article:
                element_name = element.tag
                element_value = article.find(element.tag).text

                if element_name == "title":
                    title = element_value
                if element_name == "article_body":
                    body = element_value
                if element_name == "image_link":
                    image_link = element_value
                if element_name == "date":
                    date_created = datetime.strptime(
                        element_value, "%A, %B %d, %Y - %H:%M"
                    )
                if element_name == "author_id":
                    author_id = int(element_value)

            article = Article(
                title=title,
                date_created=date_created,
                body=body,
                author_id=author_id,
                image_link=image_link,
            )

            article.save()

            print(f"{article.slug} saved!")
