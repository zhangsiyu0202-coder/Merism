<!--
Keep the title under 72 chars, in conventional-commit form:
  feat(<scope>): add thing
  fix(<scope>): handle edge case
  chore(<scope>): refactor X
-->

## What

<!-- One line summary of the change. -->

## Why

<!--
Reference the requirement / ticket / ADR this satisfies.
Examples:
  - Req 14.7 of docs/specs/merism-platform/requirements.md
  - Closes #123
  - Follows ADR 0006 (runtime harness)
-->

## How

<!--
A short technical description. What files moved, what new abstractions
were introduced, what tradeoffs were made. Skip if the diff speaks for
itself.
-->

## Tested

<!--
Paste the relevant test output. Required for every PR that ships code
(docs-only PRs can say "N/A").

  $ pytest merism/ -q
  210 passed, 1 skipped in 15.4s

  $ cd frontend && pnpm typecheck && pnpm test && pnpm build
  ✓ 0 errors · 39 passed · built in 3.5s
-->

## Breaking

<!--
Required for any schema / migration / API-surface change. Include:
  - The migration file path: merism/migrations/00XX_*.py
  - Whether the migration is backwards-compatible (can be deployed before
    the code change ships).
  - The rollout plan (feature flag / staged rollout / none).

Say "None" if nothing breaks.
-->

## Rollback

<!--
One line on how to undo this change if it turns out badly:

  - Revert this commit and redeploy.
  - Set MERISM_FOO_ENABLED=0 and restart the worker.
  - Run: python manage.py migrate merism 00XX_previous.

Say "Revert + redeploy" for the common case.
-->

## Checklist

- [ ] Tests cover the new behavior (or reproduce the bug they fix).
- [ ] No `from posthog.*` imports introduced.
- [ ] Every new model has `db_table = "merism_<noun>"` and `team_id`.
- [ ] No secrets, PII, or recipient identifiers in logs.
- [ ] Relevant docs updated (`docs/PRODUCT.md` / `docs/ROADMAP.md` /
      `docs/RUNTIME.md` / ADR).
- [ ] Commit title follows conventional-commit form.
