#!/bin/bash

# Script backs up the Cantus Database in a compressed SQL file

mkdir -p /var/lib/postgresql/backups
pg_dump cantusdb -U cantusdb | gzip > /var/lib/postgresql/backups/$1