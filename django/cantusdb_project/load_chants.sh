#!/bin/bash
FILES=./main_app/fixtures/chants_fixed/*
for f in $FILES
do
   python manage.py loaddata $f -v 2
done