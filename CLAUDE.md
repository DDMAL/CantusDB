# Cantus Database

Django app for the Cantus Database — a digital catalogue of medieval Latin chant manuscripts. Built and maintained by DDMAL at McGill.

## Stack

Django + Postgres + Redis/Celery, managed with Poetry. `volpiano-display-utilities` is a custom DDMAL dependency installed from git, not PyPI. See `pyproject.toml` for versions.

## Local development

Docker Compose is the only supported local setup — bare `manage.py runserver` is not used. First-time setup (env file, compose file layout, Dev Containers option) is in the wiki.

```bash
docker compose up
```

## Tests

Tests run inside the dev `django` container. Make sure the dev stack is up (`docker compose up -d`), then:

```bash
docker compose exec -T django python manage.py test main_app.tests
```

Run a single module or class to keep the loop tight:

```bash
docker compose exec -T django python manage.py test main_app.tests.test_functions
```

Uses Django's built-in test runner, **not pytest**. Exec'ing into the existing dev container is faster than spinning up a clean-room run.

## Verifying changes

Beyond running tests:

- `docker compose exec -T django python manage.py check` — fast sanity check after settings, model, or URL changes.
- `docker compose exec -T django python manage.py makemigrations --dry-run` — confirms whether a migration is needed after model changes.
- UI/template changes can't be verified from the terminal — say so explicitly rather than claiming success.

## Lint, format, types

**No pre-commit hook is configured** — run `black`, `mypy`, `pylint`, and `djlint` yourself before pushing.

## Branches and PRs

Three long-lived branches: `production`, `staging`, and `develop`. PR against `develop`.

Branch names: `feat/<topic>` or `fix/<topic>`.

Commit messages: Conventional Commits (`feat:`, `fix:`, `refactor:`, `docs:`, `chore:`).

**Keep PRs small and focused.** Sprawling diffs are hard to review and slow the project down.

- One concern per PR. If you spot an unrelated bug, smell, or cleanup, surface it — don't bundle it in.
- Watch for scope creep. If you find yourself refactoring surrounding code, touching many files, or pulling in unplanned schema/migration work, pause and warn the user before continuing.
- New dependencies need explicit sign-off — don't add them silently.

## Architecture

- `users/` defines a custom `Group` and `GroupMembership` — **distinct from `django.contrib.auth.Group`, which is unregistered.** Don't confuse the two.
- `RevisionMiddleware` from `django-reversion` is active, so most model writes are tracked automatically.

## User permissions

Five access tiers, enforced via `main_app/permissions.py` (`CustomAccessMixin`, `get_sources_visible_to_user`):

- **Anonymous** — sees only `published=True` sources.
- **Logged-in user (no group)** — published sources plus any sources they're explicitly assigned to via `Source.current_editors`. Can edit those assigned sources.
- **`editor` group** — broad edit privileges across the site.
- **`global viewer` group** — can see *all* sources, published or not.
- **Superuser** — bypasses every permission check.

Group memberships have **expiration dates** (`GroupMembership.expiration`); `user_group_valid()` treats an expired membership as no membership.

Old groups `contributor` and `project manager` are deprecated. Only `editor` and `global viewer` are active. Some documentation refers to a "Debra" — this means superuser, after Debra Lacoste, the project manager. There is no `Debra` role in code.

## Migrations

- Migrations do **not** auto-run. Apply them manually: `docker compose exec -T django python manage.py migrate`.
- Data migrations using `RunPython` should define `reverse_code` where applicable.

## Project quirks

- **Single `published` field controls visibility.** OldCantus had separate `published` and `visible`; that was intentionally collapsed. Do not reintroduce a `visible` field. See *User permissions* for what `published` actually gates — it's not a simple "anonymous vs. logged-in" split.
- **CSV/JSON exports diverge from OldCantus.** Some endpoints (`/json-node`, `/json-activity`) behave differently or aren't implemented. Verify the OldCantus shape before claiming parity — README has the diff.

## More context

- Project wiki (API docs, history, local-dev setup): <https://github.com/DDMAL/CantusDB/wiki>
- Deployment / infrastructure (Ansible playbooks): <https://github.com/DDMAL/ansible.cantus-db>
- `README.md` covers the OldCantus → CantusDB transition and known test-data quirks.
