FROM postgres:14-alpine
COPY postgresql.conf /etc/postgresql/postgresql.conf
COPY postgres_backup.sh /usr/local/bin/postgres_backup.sh
RUN chmod +x /usr/local/bin/postgres_backup.sh
