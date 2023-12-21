#!/bin.bash

# This script creates a compressed SQL dump of the database in the /home/ubuntu/backups/postgres/weekly directory.
# It then deletes any weekly backups so that only 8 weekly backups are retained.

# Note: This script is set up to run on the production server. If you want to run it on your local machine, you will need to change the paths.

DOCKER_COMPOSE_FILE=/home/ubuntu/code/CantusDB/docker-compose.yml   # This is the path to the docker-compose file.
BACKUP_DIR=/home/ubuntu/backups/postgres/weekly                     # This is the directory where the weekly backups will be stored.
RETENTION_COUNT=8                                                   # This is the number of weekly backups to keep.

mkdir -p $BACKUP_DIR
FILENAME=$(date "+%Y-%m-%dT%H:%M:%S").sql.gz
/usr/local/bin/docker exec cantusdb_postgres_1 /usr/local/bin/postgres_backup.sh $FILENAME
/usr/local/bin/docker copy cantusdb_postgres_1:/var/lib/postgresql/backups/$FILENAME $BACKUP_DIR
/usr/local/bin/docker exec cantusdb_postgres_1 rm /var/lib/postgresql/backups/$FILENAME
FILES_TO_REMOVE=$(ls -td $BACKUP_DIR/* | tail -n +$(($RETENTION_COUNT + 1)))
[[ ! -z "$FILES_TO_REMOVE" ]] && rm $FILES_TO_REMOVE