# PostgreSQL configuration

The PostgreSQL image copies `postgresql.conf` to
`/etc/postgresql/postgresql.conf`. Docker Compose starts PostgreSQL with that
configuration file. Changes to this repository file require rebuilding the
PostgreSQL image and recreating its container through the normal deployment;
restarting the existing container alone retains the old file. Preserve the
database volume.

## Queries whose clients disconnect

`client_connection_check_interval = '5s'` enables PostgreSQL's connection checks
while a query runs. If a Django worker exits and the operating system reports its
database connection closed, PostgreSQL can stop the abandoned query. The interval
is not a query deadline: a connected query can run longer than five seconds.
Detection concerns the database client, not whether a visitor closes their browser.
It does not guarantee cancellation within five seconds or prevent overload from
queries whose clients remain connected.

During the 12 October 2026 production incident, long-running chant searches
accumulated while PostgreSQL waited on temporary-file I/O. Cancelling 71 searches
cleared the observed backlog and reduced I/O wait from 86–94% to 0–1%. This setting
addresses queries that continue after their application connections close.

PostgreSQL 14 supports these checks on Linux, including the project's PostgreSQL
container. See the [PostgreSQL connection-check documentation](https://www.postgresql.org/docs/14/runtime-config-connection.html#GUC-CLIENT-CONNECTION-CHECK-INTERVAL).

## Deployment and emergency overrides

Follow the usual `develop` → staging testing → production release process. No
schema migration or data backfill is required. During an authorized deployment,
verify the following in PostgreSQL after deploying the rebuilt image:

```sql
SELECT sourcefile, sourceline, name, setting, applied, error
FROM pg_file_settings
WHERE name = 'client_connection_check_interval' OR error IS NOT NULL;
```

The `/etc/postgresql/postgresql.conf` entry must specify `5s`, and there must be
no configuration errors. If an emergency `ALTER SYSTEM SET` was used, an entry in
`postgresql.auto.conf` may override the repository file, even after a container
recreation. Record the existing value and source before changing it. Only after
verifying the repository file contains the intended value, remove that specific
emergency override if present:

```sql
ALTER SYSTEM RESET client_connection_check_interval;
SELECT pg_reload_conf();
```

From a fresh connection, verify the effective setting:

```sql
SELECT name, setting, unit, source, sourcefile, pending_restart
FROM pg_settings
WHERE name = 'client_connection_check_interval';
```

Expect `setting = 5000`, `unit = ms`, `sourcefile =
/etc/postgresql/postgresql.conf`, and `pending_restart = false`. Database, role,
or session overrides can take precedence; investigate a different value or source
before considering the rollout complete. Observe active-query ages and disk I/O
after rollout; verifying the setting alone does not establish sustained recovery.

This parameter supports a configuration reload without a database restart when
the file is already present in the running container. The image rebuild and
container recreation above are needed to deliver the repository file.

If rollback is necessary, restore the previous configuration and any recorded
override deliberately. The previous default was `0`, which disables these checks.
Reverting the image alone does not undo settings in `postgresql.auto.conf`.
See [ALTER SYSTEM](https://www.postgresql.org/docs/14/sql-altersystem.html) for
override persistence and reset behaviour.
