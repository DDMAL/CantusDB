"""Shared by 0048 and 0049. Convert the country field in saved institution revisions."""

import json


def convert_versions(apps, db, convert):
    versions = (
        apps.get_model("reversion", "Version")
        .objects.using(db)
        .filter(content_type__app_label="main_app", content_type__model="institution")
    )
    batch = []
    for version in versions.iterator():
        objects = json.loads(version.serialized_data)
        changed = False
        for obj in objects:
            fields = obj["fields"]
            if obj["model"] == "main_app.institution" and "country" in fields:
                old = fields["country"]
                new = convert(old)
                if old != new:
                    fields["country"] = new
                    changed = True
        if changed:
            version.serialized_data = json.dumps(objects)
            batch.append(version)
        if len(batch) == 500:
            versions.bulk_update(batch, ["serialized_data"])
            batch.clear()
    if batch:
        versions.bulk_update(batch, ["serialized_data"])
