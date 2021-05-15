#!/bin/bash

# generate tables in the database
python manage.py makemigrations
python manage.py migrate

# load initial data to populate the database
# these fixtures need to be loaded in a certain order due to foreign key dependance
# before running this, make sure you put the 'fixtures' folder under 'main_app'
FIXTURES_LIST=(
   flatpages_fixtures.json
   indexer_fixtures.json
   office_fixtures.json
   genre_fixtures.json
   feast_fixturesjson
   notation_fixtures.json
   century_fixtures.json
   provenance_fixtures.json
   rism_siglum_fixtures.json
   segment_fixtures.json
   source_fixtures.json
   # sequences.json is not here yet, but will be added in the future
   sequences_fixtures.json
)

for fixture in ${FIXTURES_LIST[*]}
do
   echo $fixture
   python manage.py loaddata $fixture
done

# load all the chants, this takes a few hours as we have half a million chants
FILES=./main_app/fixtures/chants_fixed/*
for f in $FILES
do
   python manage.py loaddata $f -v 2
done

# now you can runserver and expect things to work properly