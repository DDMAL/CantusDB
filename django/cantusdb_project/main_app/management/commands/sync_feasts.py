from django.core.management.base import BaseCommand
import requests
import lxml.html as lh
from main_app.models import Feast

FEAST_ID_FILE = "feast_list.txt"


def get_list_file(file_path):
    """for this one we need to scrape because it's more 'automated' than manual export
    """
    FEAST_LIST_PAGES = 8
    f = open(file_path, "w")
    url = "https://cantus.uwaterloo.ca/feasts"
    # add arguments for paginations
    for page in range(FEAST_LIST_PAGES):
        response = requests.get(url, params={"page": page})
        doc = lh.fromstring(response.content)
        hrefs = doc.xpath("//tr/td/strong/a/@href")
        ids = [href.split("/")[-1] for href in hrefs]
        for id in ids:
            f.write(id + "\n")
    f.close()


def get_feast_list(file_path):
    feast_list = []
    file = open(file_path, "r")
    for line in file:
        line = line.strip("\n")
        feast_list.append(line)
    file.close()
    return feast_list


def remove_extra_feasts():
    waterloo_feasts = get_feast_list(FEAST_ID_FILE)
    our_feasts = list(Feast.objects.all().values_list("id", flat=True))
    our_feasts = [str(id) for id in our_feasts]
    waterloo_feasts = set(waterloo_feasts)
    print(len(our_feasts))
    print(len(waterloo_feasts))
    extra_feasts = [id for id in our_feasts if id not in waterloo_feasts]
    for feast in extra_feasts:
        Feast.objects.get(id=feast).delete()
        print(f"Extra feast removed: {feast}")


def get_feast(feast_id):
    url = "https://cantus.uwaterloo.ca/feast/{}".format(feast_id)
    response = requests.get(url)
    doc = lh.fromstring(response.content)
    name = doc.xpath("//h1")[0].text_content()
    description = doc.xpath("//p")[0].text_content()

    feast_code = doc.xpath(
        '//div[@class="field field-name-field-feast-code field-type-text field-label-above"]/div[@class="field-items"]/div[@class="field-item even"]'
    )[0].text_content()
    if not feast_code.isdigit():
        feast_code = None

    try:
        day = doc.xpath(
            '//div[@class="field field-name-field-feastday field-type-number-integer field-label-above"]/div[@class="field-items"]/div[@class="field-item even"]'
        )[0].text_content()
        if not 1 <= int(day) <= 31:
            day = None
    except IndexError:
        day = None

    try:
        month = doc.xpath(
            '//div[@class="field field-name-field-feastmonth field-type-number-integer field-label-above"]/div[@class="field-items"]/div[@class="field-item even"]'
        )[0].text_content()
        if not 1 <= int(month) <= 12:
            month = None
    except IndexError:
        month = None

    try:
        notes = doc.xpath(
            '//div[@class="field field-name-field-feastnotes field-type-text field-label-above"]/div[@class="field-items"]/div[@class="field-item even"]'
        )[0].text_content()
    except IndexError:
        notes = None

    feast, created = Feast.objects.update_or_create(
        id=feast_id,
        defaults={
            "name": name,
            "description": description,
            "feast_code": feast_code,
            "notes": notes,
            "day": day,
            "month": month,
        },
    )
    if created:
        print(f"Created feast {feast_id}")


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument(
            "id",
            type=str,
            help="update one feast (<feast_id>)) or update all feasts ('all')",
        )
        parser.add_argument(
            "--remove_extra",
            action="store_true",
            help="add this flag to remove the feasts in our database that are no longer present in waterloo database",
        )

    def handle(self, *args, **options):
        id = options["id"]
        if id == "all":
            get_list_file(FEAST_ID_FILE)
            ids = get_feast_list(FEAST_ID_FILE)
            for id in ids:
                print(id)
                get_feast(id)
        else:
            get_feast(id)
        if options["remove_extra"]:
            remove_extra_feasts()
