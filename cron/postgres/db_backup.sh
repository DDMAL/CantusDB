#!/bin/bash

# This script creates a compressed SQL dump of the database. It is intended to be
# run daily. The script also manages the retention of these backups in the 
# /home/ubuntu/backups/postgres directory according to the following schedule: 
#  - a new backup is added daily to the ./daily subdirectory, and the 7 most
#       recent are retained
#  - a new backup is added every Monday to the ./weekly subdirectory, and the 8
#       most recent are retained
#  - a new backup is added on the first day of every month to the ./monthly
#       subdirectory, and the 12 most recent are retained
#  - a new backup is added on the first day of every year to the ./yearly
#       subdirectory

# Note: This script is set up to run on the production server. If you want to run it on your local machine, you will need to change the paths.

BACKUP_DIR=$1                                                       # This is the directory where the backups will be stored.
BACKUP_FILENAME=$(date "+%Y-%m-%dT%H:%M:%S").sql.gz                 # This is the name of the backup file.


# Create the backup and copy it to the daily backup directory
mkdir -p $BACKUP_DIR/daily $BACKUP_DIR/weekly $BACKUP_DIR/monthly $BACKUP_DIR/yearly
/usr/bin/docker exec cantusdb-postgres-1 /usr/local/bin/postgres_backup.sh $BACKUP_FILENAME
/usr/bin/docker cp cantusdb-postgres-1:/var/lib/postgresql/backups/$BACKUP_FILENAME $BACKUP_DIR/daily
/usr/bin/docker exec cantusdb-postgres-1 rm /var/lib/postgresql/backups/$BACKUP_FILENAME

# Manage retention of daily backups
FILES_TO_REMOVE=$(ls -td $BACKUP_DIR/daily/* | tail -n +8)
[[ ! -z "$FILES_TO_REMOVE" ]] && rm $FILES_TO_REMOVE

DAY_OF_MONTH=$(date "+%d")
DAY_OF_WEEK=$(date "+%u")
MONTH_OF_YEAR=$(date "+%m")

# Retain weekly backups on Mondays
# Manage retention of weekly backups
if [ $DAY_OF_WEEK -eq 1 ]; then
    cp $BACKUP_DIR/daily/$BACKUP_FILENAME $BACKUP_DIR/weekly
    FILES_TO_REMOVE=$(ls -td $BACKUP_DIR/weekly/* | tail -n +9)
    [[ ! -z "$FILES_TO_REMOVE" ]] && rm $FILES_TO_REMOVE
fi

# Retain a monthly backup on the first day of the month
# Manage retention of monthly backups
if [ $DAY_OF_MONTH -eq 1 ]; then
    cp $BACKUP_DIR/daily/$BACKUP_FILENAME $BACKUP_DIR/monthly
    FILES_TO_REMOVE=$(ls -td $BACKUP_DIR/monthly/* | tail -n +13)
    [[ ! -z "$FILES_TO_REMOVE" ]] && rm $FILES_TO_REMOVE
fi

# Retain an annual backup on the first day of the year
if [ $DAY_OF_MONTH -eq 1 ] && [ $MONTH_OF_YEAR -eq 1 ]; then
    cp $BACKUP_DIR/daily/$BACKUP_FILENAME $BACKUP_DIR/yearly
fi
