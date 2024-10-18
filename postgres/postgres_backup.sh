#!/bin/bash

# Script backs up the Cantus Database in a compressed SQL file

mkdir -p /var/lib/postgresql/backups
# Create a full DB backup for recovery purposes
pg_dump cantusdb -U cantusdb | gzip > /var/lib/postgresql/backups/$1


# Create a partial DB backup for RISM purposes on Mondays
DAY_OF_WEEK=$(date "+%u")
if [ $DAY_OF_WEEK -eq 1 ]; then
    pg_dump -U cantusdb -d cantusdb -T 'auth*' -T 'users*' -T 'reversion*' | gzip > /var/lib/postgresql/backups/cantusdb_rism_export.sql.gz
fi