# PostgreSQL configuration

`client_connection_check_interval = '5s'` lets PostgreSQL check for closed client
connections while queries run, so it can stop abandoned work. Connected queries
can run longer than five seconds.

**Configuration changes need an image rebuild and container recreation.**
`postgresql.conf` is copied into the image at `/etc/postgresql/postgresql.conf`.
Restarting the existing container keeps the old file. Use the normal deployment
process and preserve the database volume.

**Emergency overrides survive deployment.** `ALTER SYSTEM SET` writes to
`postgresql.auto.conf` in the database volume. Its values override the repository
file even after rebuilding the image and recreating the container.

If an emergency override exists, record its value first. After deploying the new
image, verify that `/etc/postgresql/postgresql.conf` contains the intended `5s`
setting before removing that override:

```sql
ALTER SYSTEM RESET client_connection_check_interval;
SELECT pg_reload_conf();
```

Then verify the value and its source from a fresh database connection:

```sql
SELECT setting, unit, sourcefile
FROM pg_settings
WHERE name = 'client_connection_check_interval';
```

Expect `5000`, `ms`, and `/etc/postgresql/postgresql.conf`. Investigate a different
value or source before considering the configuration update complete.
