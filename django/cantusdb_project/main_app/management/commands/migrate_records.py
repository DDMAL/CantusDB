from typing import Optional

import requests
from django.core.management import BaseCommand

from main_app.identifiers import ExternalIdentifiers
from main_app.models import Source, Institution, InstitutionIdentifier

private_collections = {
    "US-SLpc",
    "US-CinOHpc",
    "US-AshORpc",
    "US-CTpc",
    "IRL-Dpc",
    "US-NYpc",
    "GB-Oxpc",
    "US-Phpc",
    "D-ROTTpc",
    "D-Berpc",
    "US-Nevpc",
    "US-IssWApc",
    "US-RiCTpc",
    "US-RiCTpc,",
    "US-OakCApc",
    "US-CApc",
    "ZA-Newpc",
    "CDN-MtlQCpc",
    "CDN-MasQCpc",
    "CDN-HalNSpc",
    "CDN-WatONpc",
    "CDN-LonONpc",
    "CDN-VicBCpc",
    "US-BosMApc",
    "US-RiCTpc",
    "US-Unpc",
    "US-SalNHpc",
    "F-Villpc",
    "GB-Brpc",
    "CDN-NVanBCpc",
    "CDN-SYpc",
    "NL-EINpc",
    "BR-PApc",
}

siglum_to_country = {
    "A": "Austria",
    "AUS": "Australia",
    "B": "Belgium",
    "BR": "Brazil",
    "CDN": "Canada",
    "CH": "Switzerland",
    "CZ": "Czechia",
    "D": "Germany",
    "DK": "Denmark",
    "E": "Spain",
    "EC": "Ecuador",
    "F": "France",
    "FIN": "Finland",
    "GB": "United Kingdom",
    "GR": "Greece",
    "H": "Hungary",
    "HR": "Croatia",
    "I": "Italy",
    "IRL": "Ireland",
    "NL": "Netherlands",
    "NZ": "New Zealand",
    "P": "Portugal",
    "PL": "Poland",
    "RO": "Romania",
    "SI": "Slovenia",
    "SK": "Slovakia",
    "SA": "South Africa",
    "ZA": "South Africa",
    "S": "Sweden",
    "T": "Taiwan",
    "TR": "Turkey",
    "US": "United States",
    "V": "Vatican City",
    "XX": "Unknown",
}

prints = {
    "MA Impr. 1537",
    "N-N.miss.imp.1519",
    "D-A/imp:1498",
    "D-P/imp1511",
    "D-WÜ/imp1583",
}


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument("-e", "--empty", action="store_true")

    def handle(self, *args, **options):
        if options["empty"]:
            print(self.style.WARNING("Deleting records..."))
            Source.objects.all().update(holding_institution=None)
            Institution.objects.all().delete()
            InstitutionIdentifier.objects.all().delete()

        print_inst = Institution.objects.create(
            name="Print (Multiple Copies)", siglum="XX-NN", city=None
        )

        # Store a siglum: id
        created_institutions = {}
        # Track the sources with a bad siglum so that we don't try and look it up and fail.
        bad_siglum = set()

        for source in Source.objects.all().order_by("siglum"):
            print(self.style.SUCCESS(f"Processing {source.id}"))
            source_name = source.title
            source_siglum = source.siglum

            try:
                city, institution_name, shelfmark = source_name.split(",", 2)
            except ValueError:
                print(
                    self.style.WARNING(
                        f"{source.id:^11}| Could not extract institution name for {source_name}"
                    )
                )
                city = "[Unknown]"
                institution_name = source_name
                shelfmark = source_siglum

            try:
                siglum, _ = source_siglum.split(" ", 1)
            except ValueError:
                print(
                    self.style.WARNING(
                        f"{source.id:^11}| Could not extract siglum for {source_siglum}"
                    )
                )
                siglum = "XX-NN"
                bad_siglum.add(source.id)

            try:
                country = siglum_to_country[siglum.split("-")[0]]
            except KeyError:
                print(
                    self.style.WARNING(
                        f"{source.id:^11}| Could not extract country for {source_siglum}"
                    )
                )
                country = "[Unknown Country]"
                bad_siglum.add(source.id)

            if source_siglum in prints:
                print(
                    self.style.SUCCESS(
                        f"Adding {source_siglum} to the printed records institution"
                    )
                )
                institution = print_inst
            elif siglum in created_institutions:
                print(
                    self.style.SUCCESS(
                        f"Re-using the pre-created institution for {siglum}"
                    )
                )

                institution = created_institutions[siglum]

                # if the source we're publishing has a different institution name than the
                # one that already exists, save the source name as an alternate name.
                if institution_name and institution_name != institution.name:
                    existing_alt_names: list = institution.alternate_names.split("\n") if institution.alternate_names else []
                    existing_alt_names.append(institution_name.strip())
                    deduped_names = set(existing_alt_names)
                    institution.alternate_names = "\n".join(list(deduped_names))

                    institution.save()
            elif siglum not in created_institutions:
                print(self.style.SUCCESS(f"Creating institution record for {siglum}"))

                iobj = {
                    "city": city.strip() if city else None,
                    "country": country,
                    "name": institution_name.strip(),
                }

                if siglum in private_collections:
                    iobj["is_private_collector"] = True
                else:
                    iobj["siglum"] = siglum

                institution = Institution.objects.create(**iobj)

                rism_id = None
                if source.id not in bad_siglum and siglum not in private_collections:
                    rism_id = get_rism_id(siglum)
                elif siglum == "XX-NN":
                    rism_id = "institutions/51003803"

                if rism_id:
                    print(
                        self.style.SUCCESS(
                            f"Adding {rism_id} to the identifiers for {siglum}"
                        )
                    )

                    instid = InstitutionIdentifier.objects.create(
                        identifier=rism_id,
                        identifier_type=ExternalIdentifiers.RISM,
                        institution=institution,
                    )
                    instid.save()

                created_institutions[siglum] = institution

            else:
                print(
                    self.style.ERROR(
                        f"Could not determine the holding institution for {source}"
                    )
                )
                continue

            source.holding_institution = institution
            source.shelfmark = shelfmark.strip()
            source.save()


def get_rism_id(siglum) -> Optional[str]:
    req = requests.get(
        f"https://rism.online/sigla/{siglum}",
        allow_redirects=True,
        headers={"Accept": "application/ld+json"},
    )
    if req.status_code != 200:
        return None
    else:
        resp = req.json()
        inst_ident = resp.get("id", "")
        rism_id = "/".join(inst_ident.split("/")[-2:])
        return rism_id
