# Cantus Database

Django app for the Cantus Database — a digital catalogue of medieval Latin chant manuscripts. Built and maintained by DDMAL at McGill.

## Development workflow

`volpiano-display-utilities` is a custom DDMAL dependency installed from git, not PyPI.

Docker Compose is the only supported local setup — bare `manage.py runserver` is not used. With the dev stack up (`docker compose up -d`), run from the host. Prefer `exec` into the running container over `run`:

```bash
# Tests (Django's built-in runner, not pytest)
docker compose exec -T django python manage.py test main_app.tests

# Single module/class to keep the loop tight
docker compose exec -T django python manage.py test main_app.tests.test_functions

# Fast sanity check after settings, model, or URL changes
docker compose exec -T django python manage.py check

# Confirm a migration is needed after model changes
docker compose exec -T django python manage.py makemigrations --dry-run
```

**Migrations do not auto-run.** Apply them manually: `docker compose exec -T django python manage.py migrate`. Data migrations using `RunPython` should define `reverse_code` where applicable.

UI/template changes can't be verified from the terminal — say so explicitly rather than claiming success.

**No pre-commit hook is configured** — run `black`, `mypy`, `pylint`, and `djlint` yourself before pushing.

## Branches and PRs

Three long-lived branches: `production`, `staging`, and `develop`. PR against `develop`.

Branch names: `feat/<topic>` or `fix/<topic>`.

Commit messages: Conventional Commits (`feat:`, `fix:`, `refactor:`, `docs:`, `chore:`).

**Keep PRs small and focused.** Sprawling diffs are hard to review and slow the project down.

- Watch for scope creep. If you find yourself refactoring surrounding code, touching many files, or pulling in unplanned schema/migration work, pause and warn the user before continuing.
- New dependencies need explicit sign-off — don't add them silently.

## Architecture and permissions

**Models, migrations, and `main_app/permissions.py` are the highest-risk areas.** Use plan mode and confirm the approach before editing.

- `users/` defines a custom `Group` and `GroupMembership` — **distinct from `django.contrib.auth.Group`, which is unregistered.** Don't confuse the two.
- `RevisionMiddleware` from `django-reversion` is active, so most model writes are tracked automatically.

Five access tiers, enforced via `main_app/permissions.py` (`CustomAccessMixin`, `get_sources_visible_to_user`):

- **Anonymous** — sees only `published=True` sources.
- **Logged-in user (no group)** — published sources plus any sources they're explicitly assigned to via `Source.current_editors`. Can edit those assigned sources.
- **`editor` group** — broad edit privileges across the site.
- **`global viewer` group** — can see *all* sources, published or not.
- **Superuser** — bypasses every permission check.

Group memberships have **expiration dates** (`GroupMembership.expiration`); `user_group_valid()` treats an expired membership as no membership.

Old groups `contributor` and `project manager` are deprecated. Only `editor` and `global viewer` are active.

## Gotchas

- **Single `published` field controls visibility.** OldCantus had separate `published` and `visible`; that was intentionally collapsed. Do not reintroduce a `visible` field. See *Architecture and permissions* for what `published` actually gates — it's not a simple "anonymous vs. logged-in" split.
- **CSV/JSON exports diverge from OldCantus.** Some endpoints (`/json-node`, `/json-activity`) behave differently or aren't implemented. Verify the OldCantus shape before claiming parity — README has the diff.

## References

The wiki is often the fastest source for API shape, OldCantus → CantusDB diffs, and historical decisions — check it before assuming code is the only source of truth. It can lag behind the codebase, so verify against current code before acting on anything load-bearing.

- Wiki: <https://github.com/DDMAL/CantusDB/wiki>
- Deployment / infrastructure (Ansible playbooks): <https://github.com/DDMAL/ansible.cantus-db>
- `README.md` covers the OldCantus → CantusDB transition and known test-data quirks.
