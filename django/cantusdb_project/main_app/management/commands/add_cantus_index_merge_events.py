import requests
from typing import Optional
from datetime import datetime
from django.core.management.base import BaseCommand
from main_app.models import Chant
from cantusindex import get_merged_cantus_ids


class Command(BaseCommand):
    help = (
        "Fetch and apply merge events from the /json-merged-chants API on Cantus Index"
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "date",
            nargs="?",
            type=str,
            help="Filter merges by date in the format YYYY-MM-DD",
        )

    def handle(self, *args, **kwargs):
        date_filter: str = kwargs["date"]
        if date_filter:
            try:
                date_filter = datetime.strptime(date_filter, "%Y-%m-%d")
            except ValueError:
                self.stdout.write(
                    self.style.ERROR("Invalid date format. Please use YYYY-MM-DD.")
                )
                return

        # Fetch the merge events from the Cantus Index API
        merge_events: Optional[list] = get_merged_cantus_ids()

        if not merge_events:
            self.stdout.write(
                self.style.ERROR("Failed to fetch data from Cantus Index.")
            )
            return

        # Filter merge events by the provided date
        if date_filter:
            merge_events = self.filter_merge_events_by_date(merge_events, date_filter)

        # Apply the new merge events on Cantus DB
        for tx in merge_events:
            self.apply_transaction(tx)

    def filter_merge_events_by_date(self, merge_events: list, date_filter: str) -> list:

        filtered_merge_events = []
        for tx in merge_events:
            try:
                tx_date = datetime.strptime(tx["date"], "%Y-%m-%d")
                if tx_date > date_filter:
                    filtered_merge_events.append(tx)
            except ValueError:
                # Handle invalid date format (usually 0000-00-00)
                self.stdout.write(
                    self.style.WARNING(
                        f"Ignoring merge event with invalid date format: {tx['date']}"
                    )
                )

        return filtered_merge_events

    def apply_transaction(self, transaction: dict) -> None:
        old_cantus_id: str = transaction["old"]
        new_cantus_id: str = transaction["new"]

        if not old_cantus_id or not new_cantus_id:
            self.stdout.write(
                self.style.WARNING(
                    f"Skipping transaction with missing cantus_id. Old: {old_cantus_id}, New: {new_cantus_id}"
                )
            )
            return

        affected_chants = Chant.objects.filter(cantus_id=old_cantus_id)

        if affected_chants:
            try:
                affected_chants.update(cantus_id=new_cantus_id)
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Old Cantus ID: {old_cantus_id} -> New Cantus ID: {new_cantus_id}\n"
                    )
                )
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(
                        f"An error occurred while updating Chants with old cantus_id {old_cantus_id}: {e}"
                    )
                )
        else:
            self.stdout.write(
                self.style.WARNING(f"No Chants found with cantus_id: {old_cantus_id}")
            )
