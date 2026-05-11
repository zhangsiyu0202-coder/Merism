# Contributing to Merism

This repository is proprietary and closed-source. This document applies to
**internal contributors only** — employees, contractors, and authorized
licensees. External pull requests will not be reviewed or merged.

For the why/what/how of the product, read [`docs/PRODUCT.md`](docs/PRODUCT.md)
first, then [`AGENTS.md`](AGENTS.md) for the non-negotiable engineering
rules, then [`docs/ROADMAP.md`](docs/ROADMAP.md) to see what's open.

## Getting started

```bash
# One-command bootstrap: docker up + uv sync + migrate + seed + smoke.
bin/setup-dev.sh
```

Verify the environment:

```bash
make test-backend
make test-frontend
make lint
```

If `make test-backend` does not report `210+ passed`, stop and fix the
environment before writing new code.

## Branching & commit style

### Branch names

- `feat/<scope>-<short-description>` — new feature
- `fix/<scope>-<short-description>` — bug fix
- `chore/<scope>-<short-description>` — docs, CI, refactor without
  behavior change
- `hotfix/<scope>-<short-description>` — P0/P1 production fix

`<scope>` matches the Merism domain: `study`, `interview`, `knowledge`,
`recruit`, `report`, `memai`, `design-system`, `realtime`, `voice`,
`conductor`, `infra`, `ci`.

### Commits

[Conventional commits](https://www.conventionalcommits.org/en/v1.0.0/) are
required. The commit type prefix is enforced by CI:

```
<type>(<scope>): <description>
```

Examples:

- `feat(study): add outline review agent function call schema`
- `fix(recruit): handle feishu token refresh race condition`
- `chore(ci): wire pyright into the workflow`

The description must be lowercase, under 72 characters, and must not end
with a period.

## Pull request checklist

Every PR must:

1. **Pass CI.** `pytest merism/ -q` + `pnpm typecheck && pnpm test && pnpm
   lint && pnpm build` all green locally before push. Use
   `make test && make lint && make typecheck` to run the full set.
2. **Include tests.** New code paths need corresponding tests under
   `merism/**/tests/` or a colocated `test_<module>.py`. Bug fixes include
   a regression test that fails on the old code.
3. **Respect the rules in `AGENTS.md`.** In particular:
   - No `from posthog.*` imports (boundary test enforces this).
   - Every model sets `db_table = "merism_<noun>"`.
   - Every tenant-data model carries `team_id`.
   - Interview moderator stays single-LLM-call.
   - `Study.research_goal` remains the single North Star field.
4. **Be scoped.** One logical change per PR. If you touch >10 files, split
   unless the change is a coordinated refactor.
5. **Update documentation** when behavior changes: `docs/PRODUCT.md`,
   `docs/ROADMAP.md`, `docs/RUNTIME.md`, or the relevant ADR.
6. **Ship a migration for any model change** — `python manage.py
   makemigrations` and commit the generated file in the same PR.

### PR description template

The repository's pull request template (see `.github/pull_request_template.md`)
enforces the following sections. Fill them all in — the reviewer will ask
for them otherwise.

- **What**: one-line change summary.
- **Why**: which requirement / ticket / ADR this satisfies.
- **Tested**: paste the key test output (`pytest -q` summary line).
- **Breaking**: any schema or API-surface change (include migration file
  path and migration strategy).
- **Rollback**: one line on how to revert if this turns out badly.

## Code review

- At least **one approval from a CODEOWNER** is required before merging.
- Reviewers have **2 business days** to respond. If blocked, nudge in
  the team channel — do not sit on a PR silently.
- The author merges after approval, not the reviewer.
- Merge strategy: **squash merge** by default. Keep the squashed commit
  title in conventional-commit form.

## Testing conventions

- Prefer `pytest` fixtures in `merism/testing/` over hand-rolled `MagicMock`.
- Use `parameterized.parameterized.expand` over 5 near-identical tests.
- Do not add doc comments to test functions.
- One top-level `class Test...` per logical unit under test.
- Mark slow or network-dependent tests with
  `@pytest.mark.slow` / `@pytest.mark.live` so CI can skip them by default.
- Never commit snapshot or recording fixtures larger than ~1 MB without
  approval — they bloat the repo.

## Dependencies

- Python deps go in `pyproject.toml` under the right table (`dependencies`
  vs `[project.optional-dependencies].dev`).
- Pin new deps to the exact version the first time you add them. Renovate
  will propose the upgrade strategy going forward.
- Frontend deps go in `frontend/package.json`. Match the same pinning
  discipline.
- Do not add a new LLM provider, data store, or queue system without an
  ADR under `docs/adr/`.

## Security

See [`SECURITY.md`](SECURITY.md) for vulnerability reporting, severity
scale, and incident response. In short: never commit real secrets, never
log raw PII, and email `security@merism.ai` if you find a vulnerability.

## Design-system compliance

All new frontend code imports primitives / patterns / tokens from
`~/lib/merism`. Do not introduce LemonUI components or arbitrary Tailwind
utilities outside the `merism-*` namespace. See
`docs/specs/merism-design-system/` for the full catalog.

## AI-assisted code

- Agent-generated code is treated identically to human-authored code — it
  must pass CI and reviewer expectations.
- Do not paste proprietary internals into third-party chat assistants
  that are not approved by the Company. Approved assistants are listed
  in the internal tooling registry.
- When an AI agent makes non-trivial architectural decisions, capture
  the reasoning in a commit-message footer or a new ADR.

## Questions

- Product / scope questions → `docs/PRODUCT.md` or the Product owner.
- Architecture / design questions → `docs/adr/` or the tech lead.
- Environment / local setup issues → `docs/MIGRATION.md` or
  `docs/RUNTIME.md`.

When in doubt, ask in the internal engineering channel before writing
code that might not land.
