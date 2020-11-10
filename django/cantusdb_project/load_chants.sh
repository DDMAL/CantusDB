#!/bin/bash
FILES=./main_app/fixtures/chants/*
for f in $FILES
do
  echo "Processing $f file..."
  python manage.py loaddata $f
done