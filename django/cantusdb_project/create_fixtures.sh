#!/bin/bash

# This script runs the commands necessary to export fixtures from a working version
# of CantusDB, putting them all in a single folder, fixtures/ .
# They can then be unpacked in a fresh clone of CantusDB by running break_json.py
# followed by load_fixtures.sh .
# This file should be in the same directory as manage.py .
# Run this file inside the django container with `bash create_fixtures.sh`.

mkdir fixtures

echo "creating group_fixture.json"
python manage.py dumpdata auth.Group -o fixtures/group_fixture.json --indent 4

echo "creating user_fixture.json"
python manage.py dumpdata users.User -o fixtures/user_fixture.json --indent 4

echo "creating flatpage_fixture.json"
python manage.py dumpdata flatpages -o fixtures/flatpage_fixture.json --indent 4

echo "creating article_fixture.json"
python manage.py dumpdata articles.Article -o fixtures/article_fixture.json --indent 4

echo "creating office_fixture.json"
python manage.py dumpdata main_app.Office -o fixtures/office_fixture.json --indent 4

echo "creating genre_fixture.json"
python manage.py dumpdata main_app.Genre -o fixtures/genre_fixture.json --indent 4

echo "creating feast_fixture.json"
python manage.py dumpdata main_app.Feast -o fixtures/feast_fixture.json --indent 4

echo "creating notation_fixture.json"
python manage.py dumpdata main_app.Notation -o fixtures/notation_fixture.json --indent 4

echo "creating century_fixture.json"
python manage.py dumpdata main_app.Century -o fixtures/century_fixture.json --indent 4

echo "creating provenance_fixture.json"
python manage.py dumpdata main_app.Provenance -o fixtures/provenance_fixture.json --indent 4

echo "creating rism_siglum_fixture.json"
python manage.py dumpdata main_app.RismSiglum -o fixtures/rism_siglum_fixture.json --indent 4

echo "creating segment_fixture.json"
python manage.py dumpdata main_app.Segment -o fixtures/segment_fixture.json --indent 4

echo "creating source_fixture.json"
python manage.py dumpdata main_app.Source -o fixtures/source_fixture.json --indent 4

echo "creating sequence_fixture.json"
python manage.py dumpdata main_app.Sequence -o fixtures/sequence_fixture.json --indent 4


echo "creating chant_fixture.json"
python manage.py dumpdata main_app.Chant -o fixtures/chant_fixture.json --indent 4
