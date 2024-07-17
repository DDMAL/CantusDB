from collections import defaultdict

import requests
from django.core.exceptions import ValidationError
from django.core.management import BaseCommand

from main_app.identifiers import ExternalIdentifiers
from main_app.models import Source, Institution, InstitutionIdentifier

sigla_to_skip = {
    "N-N.miss.imp.1519",
    "McGill, Fragment 21",
    "D-WÜ/imp1583",
    "Unknown",
    "Test-Test IV",
    "Test-Test VI",
    "Test-test VII",
    "D-P/imp1511",
    "MA Impr. 1537",
    "GOTTSCHALK",
    "BEAUVAIS",
    "D-A/imp:1498",
}

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
    "BR-PApc"
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

prints = {
    "MA Impr. 1537",
    "N-N.miss.imp.1519",
    "D-A/imp:1498",
    "D-P/imp1511",
    "D-WÜ/imp1583"
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
            print(self.style.WARNING("Deleting records..."))
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
                source_shelfmarks[source.id] = shelfmark.strip()
            except ValueError:
                print(
                    self.style.WARNING(
                        f"{source.id:^11}| Could not extract institution name for {source_name}"
                    )
                )
                city = "[Unknown]"
                institution_name = source_name
                source_shelfmarks[source.id] = source_siglum.strip()
                shelfmark = source_siglum.strip()

            try:
                siglum, _ = source_siglum.split(" ", 1)
            except ValueError:
                print(
                    self.style.WARNING(
                        f"{source.id:^11}| Could not extract siglum for {source_siglum}"
                    )
                )
                bad_sigla.add(source_siglum)
                siglum = source_siglum

            insts_name[siglum].add(institution_name.strip())
            insts_city[siglum].add(city.strip())
            insts_ids[siglum].add(source.id)

            if options["lookup"] and (siglum not in bad_sigla or siglum not in private_collections or siglum not in insts_rism):
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
                else:
                    resp = req.json()
                    inst_ident = resp.get("id", "")
                    rism_id = "/".join(inst_ident.split("/")[-2:])
                    insts_rism[siglum] = rism_id

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

        print_inst = Institution.objects.create(
            name="Print (Multiple Copies)",
            siglum="XX-NN",
            city=None
        )

        for sig, names in insts_name.items():
            print("Sig: ", sig)
            inst_id = insts_ids[sig]

            if sig not in prints:
                if sig == "MA Impr. 1537":
                    print("WHAHAHAHATTT?T??T?TTT?T")

                inst_city = insts_city[sig]
                main_city = list(inst_city)[0] if len(inst_city) > 0 else ""
                main_name = list(names)[0] if len(names) > 0 else ""
                alt_names = "; ".join(list(names)[1:])
                alt_names_fmt = f'"{alt_names}"' if alt_names else ""

                try:
                    inst_country = siglum_to_country[sig.split("-")[0]]
                    inst_sig = sig
                except KeyError:
                    print(self.style.WARNING(f"Unknown country for siglum {sig}."))
                    inst_country = None
                    # Setting siglum to None will make it XX-NN
                    inst_sig = None

                print(f"{inst_sig},{main_city},{inst_country},{main_name},{alt_names_fmt}")

                if options["dry_run"]:
                    continue

                iobj = {
                    "city": main_city if main_city != "[Unknown]" else None,
                    "country": inst_country,
                    "name": main_name,
                    "alternate_names": "\n".join(list(names)[1:]),
                }

                if inst_sig in private_collections:
                    iobj["is_private_collector"] = True
                elif inst_sig is not None:
                    iobj["siglum"] = inst_sig
                else:
                    print(self.style.WARNING(f"Could not create {inst_id}. Setting siglum to XX-NN"))
                    iobj["siglum"] = "XX-NN"

                try:
                    holding_institution = Institution.objects.create(**iobj)
                except ValidationError:
                    print(
                        self.style.WARNING(f"Could not create {sig} {main_name}. Setting institution to None")
                    )
                    holding_institution = None

                if holding_institution:
                    print("Created", holding_institution)
            else:
                holding_institution = print_inst

            if rismid := insts_rism.get(sig):
                instid = InstitutionIdentifier.objects.create(
                    identifier=rismid,
                    identifier_type=ExternalIdentifiers.RISM,
                    institution=holding_institution,
                )
                instid.save()

            for source_id in list(inst_id):
                shelfmark = source_shelfmarks.get(source_id)

                s = Source.objects.get(id=source_id)
                if not shelfmark:
                    shelfmark = s.siglum

                print(s)
                s.holding_institution = holding_institution
                s.shelfmark = shelfmark.strip()
                s.save()
                print(self.style.SUCCESS(
                    f"Saved update to Source {s.id}"
                ))
