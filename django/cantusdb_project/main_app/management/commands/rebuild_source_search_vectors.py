from django.core.management.base import BaseCommand

from main_app.source_search import rebuild_source_search_vectors


class Command(BaseCommand):
    help = "Rebuild PostgreSQL full-text search vectors for all sources."

    def handle(self, *args, **options):
        count = rebuild_source_search_vectors()
        self.stdout.write(self.style.SUCCESS(f"Rebuilt {count} source search vectors."))
