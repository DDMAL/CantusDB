from collections import defaultdict
from typing import Optional

import requests
from django.core.management import BaseCommand

from main_app.identifiers import ExternalIdentifiers
from main_app.models import Source, Institution, InstitutionIdentifier

sigla_to_skip = {
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
    "N-N.miss.imp.1519",
    "BR-PApc D-0egev (fragment)",
    "McGill, Fragment 21",
    "D-WÜ/imp1583",
    "Unknown",
    "P-Pm 1151",
    "E-Zahp 'Book 1'",
    "NL-UStPFragm01",
    "NL-EINpc",
    "Test-Test IV",
    "Test-Test VI",
    "Test-test VII",
    "D-P/imp1511",
    "P-Cug",
    "P-La",
    "SK-BRm EC Lad. 4, ba",
    "MS 0285 - 5",
    "MA Impr. 1537",
    "GOTTSCHALK",
    "BEAUVAIS",
    "D-Mü Clm 19162",
    "D-A/imp:1498",
    "US-Phpc",
    "D-ROTTpc",
    "D-Berpc",
    "US-Nevpc",
    "US-IssWApc",
    "US-RiCTpc",
    "US-RiCTpc,",
    "US-OakCApc",
    "US-CTpc",
    "IRL-Dpc",
    "US-NYpc",
    "GB-Oxpc",
    "US-AshORpc",
    "US-CinOHpc",
    "I-Pc B16*",
    "I-Vlevi CF D 21",
    "CZ-Bu R 387",
    "US-SLpc"
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
    "T": "Taiwan",
    "TR": "Turkey",
    "US": "United States",
    "V": "Vatican City",
    "XX": "Unknown",
}


class Command(BaseCommand):
    help = "Creates institution records based on the entries in the Sources model"

    def add_arguments(self, parser):
        parser.add_argument("-e", "--errors", action="store_true")
        parser.add_argument("-l", "--lookup", action="store_true")
        parser.add_argument("-d", "--dry-run", action="store_true")
        parser.add_argument("-m", "--empty", action="store_true")

    def handle(self, *args, **options):
        if options["empty"]:
            Source.objects.all().update(holding_institution=None)
            Institution.objects.all().delete()
            InstitutionIdentifier.objects.all().delete()

        insts_name = defaultdict(set)
        insts_ids = defaultdict(set)
        insts_city = defaultdict(set)
        insts_rism = {}
        bad_sigla = set()
        source_shelfmarks = {}

        for source in Source.objects.all().order_by("siglum"):
            source_name = source.title
            source_siglum = source.siglum

            try:
                city, institution_name, shelfmark = source_name.split(",", 2)
                source_shelfmarks[source.id] = shelfmark
            except ValueError:
                print(
                    self.style.WARNING(
                        f"{source.id:^11}| Could not extract institution name for {source_name}"
                    )
                )
                bad_sigla.add(source_siglum)
                source_shelfmarks[source.id] = source_name
                continue

            try:
                siglum, _ = source_siglum.split(" ", 1)
            except ValueError:
                print(
                    self.style.WARNING(
                        f"{source.id:^11}| Could not extract siglum for {source_siglum}"
                    )
                )
                bad_sigla.add(source_siglum)
                continue

            insts_name[siglum].add(institution_name.strip())
            insts_city[siglum].add(city.strip())
            insts_ids[siglum].add(source.id)

            if options["lookup"]:
                if siglum in bad_sigla:
                    # if we already know it's bad, no need to look it up again.
                    continue
                if siglum in insts_rism:
                    # If we've already looked it up...
                    continue

                req = requests.get(
                    f"https://rism.online/sigla/{siglum}",
                    allow_redirects=True,
                    headers={"Accept": "application/ld+json"},
                )
                if req.status_code != 200:
                    print(
                        self.style.WARNING(
                            f"{source.id:^11}| Could not fetch siglum {siglum}"
                        )
                    )
                    bad_sigla.add(siglum)
                    continue

                resp = req.json()
                inst_ident = resp.get("id", "")
                rism_id = "/".join(inst_ident.split("/")[-2:])
                insts_rism[siglum] = rism_id

            if options["errors"]:
                continue

            print(
                self.style.SUCCESS(
                    f"{source.id:^11}|{city:^31}|{institution_name:^101}|{siglum:^11}|{shelfmark}"
                )
            )

        if options["lookup"]:
            print("Bad Sigla: ")
            for sig in bad_sigla:
                names = list(insts_name[sig])
                print(sig, ",", names if len(names) > 0 else "No name")

        print("Here are the institutions that I will create:")
        print("siglum,city,country,name,alt_names")
        for sig, names in insts_name.items():
            if sig in sigla_to_skip:
                continue

            inst_id = insts_ids[sig]
            inst_city = insts_city[sig]
            main_city = list(inst_city)[0] if len(inst_city) > 0 else ""
            main_name = list(names)[0] if len(names) > 0 else ""
            alt_names = "; ".join(list(names)[1:])
            alt_names_fmt = f'"{alt_names}"' if alt_names else ""
            inst_country = siglum_to_country[sig.split("-")[0]]

            print(f"{sig},{main_city},{inst_country},{main_name},{alt_names_fmt}")
            if not main_name:
                breakpoint()

            if options["dry_run"]:
                continue

            inst = Institution.objects.create(
                siglum=sig,
                city=main_city,
                country=inst_country,
                name=main_name,
                alternate_names="\n".join(list(names)[1:]),
            )
            inst.save()
            print("Created", inst)

            if rismid := insts_rism.get(sig):
                instid = InstitutionIdentifier.objects.create(
                    identifier=rismid,
                    identifier_type=ExternalIdentifiers.RISM,
                    institution=inst,
                )
                instid.save()

            for source_id in list(inst_id):
                shelfmark = source_shelfmarks[source_id]
                s = Source.objects.get(id=source_id)
                print(s)
                s.holding_institution = inst
                s.shelfmark = shelfmark
                s.save()
