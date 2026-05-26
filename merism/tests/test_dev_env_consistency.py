"""Guard test: docker-compose.yml backend services must share env consistently.

The pre-2026-05-24 docker-compose.yml had a silent drift: ``celery-worker``
defined ``CELERY_RESULT_BACKEND`` but ``celery-beat`` didn't, so beat
inherited Django settings' default of ``redis://localhost:6379/2`` —
which inside a container resolves to nothing reachable. Beat got stuck
in a "Retry limit exceeded" loop for days before anyone noticed.

The fix was to extract a shared ``x-merism-backend-env`` YAML anchor
and have every backend service alias it. This test enforces that
contract: any service running our Django/Celery code must end up with
the same set of env-var keys, so dropping a variable from one service
necessarily drops it from all (or fails the test).

Why this lives in the test suite (not pre-commit / docs):
    - CI runs the suite on every PR; doc rules are advisory.
    - Catches the drift on the same machine where everything else is
      validated, with the same cache invariants.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
COMPOSE_FILE = REPO_ROOT / "docker-compose.yml"

# Backend services run Django/Celery code and must share the same env
# block (broker, postgres host, settings module, LLM credentials, ...).
# Postgres / redis / minio are infrastructure and have their own env.
BACKEND_SERVICES: tuple[str, ...] = ("celery-worker", "celery-beat")


def _load_compose() -> dict:
    # PyYAML doesn't preserve YAML anchors as a separate object; the
    # parsed result already has the alias merged into each service's
    # environment dict. That's exactly what we want — we test the
    # **post-merge** view, which is what Docker actually sees.
    with COMPOSE_FILE.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


class TestDockerComposeBackendEnvConsistency:
    def test_compose_file_exists(self) -> None:
        assert COMPOSE_FILE.exists(), f"missing {COMPOSE_FILE}"

    def test_each_backend_service_has_environment(self) -> None:
        compose = _load_compose()
        services = compose.get("services", {})
        for name in BACKEND_SERVICES:
            assert name in services, f"service {name!r} missing from compose"
            env = services[name].get("environment")
            assert env, f"service {name!r} has no environment block"

    def test_backend_services_share_identical_env_keys(self) -> None:
        """All backend services must define the **same set** of env keys.

        Values may differ (worker vs beat may legitimately want
        different concurrency, etc.) but the key set must match — if
        you add ``MERISM_LLM_API_KEY`` to worker, beat must get it too,
        otherwise async tasks vs scheduled tasks behave differently.
        """
        compose = _load_compose()
        services = compose["services"]

        env_keys_per_service: dict[str, frozenset[str]] = {}
        for name in BACKEND_SERVICES:
            env = services[name]["environment"]
            # docker-compose accepts environment as either a dict
            # (KEY: VALUE) or a list of "KEY=VALUE" / "KEY" strings.
            if isinstance(env, dict):
                keys = frozenset(env.keys())
            elif isinstance(env, list):
                keys = frozenset(item.split("=", 1)[0] for item in env)
            else:
                pytest.fail(f"service {name!r} environment has unexpected type {type(env)}")
            env_keys_per_service[name] = keys

        # Compare every pair against the first service.
        reference_name = BACKEND_SERVICES[0]
        reference_keys = env_keys_per_service[reference_name]
        for name in BACKEND_SERVICES[1:]:
            this_keys = env_keys_per_service[name]
            missing_in_this = reference_keys - this_keys
            extra_in_this = this_keys - reference_keys
            assert not missing_in_this and not extra_in_this, (
                f"docker-compose.yml drift between {reference_name!r} and {name!r}:\n"
                f"  keys in {reference_name} but not in {name}: {sorted(missing_in_this) or 'none'}\n"
                f"  keys in {name} but not in {reference_name}: {sorted(extra_in_this) or 'none'}\n"
                f"\nFix: alias the shared env anchor (x-merism-backend-env) on "
                f"every backend service instead of inlining."
            )

    def test_required_celery_env_keys_present(self) -> None:
        """The bug we hit: beat was missing CELERY_RESULT_BACKEND.

        These three keys are mandatory for any Celery service. Loose
        check (string membership) so renames are caught.
        """
        required = {
            "DJANGO_SETTINGS_MODULE",
            "CELERY_BROKER_URL",
            "CELERY_RESULT_BACKEND",
            "REDIS_URL",
            "POSTGRES_HOST",
        }
        compose = _load_compose()
        services = compose["services"]
        for name in BACKEND_SERVICES:
            env = services[name]["environment"]
            keys = set(env.keys()) if isinstance(env, dict) else {item.split("=", 1)[0] for item in env}
            missing = required - keys
            assert not missing, f"service {name!r} is missing required env keys: {sorted(missing)}"

    def test_pointing_at_docker_internal_hostnames(self) -> None:
        """Backend services run inside the docker network — they must
        address postgres/redis by service name, not localhost."""
        compose = _load_compose()
        services = compose["services"]
        for name in BACKEND_SERVICES:
            env = services[name]["environment"]
            if not isinstance(env, dict):
                continue  # list form harder to inspect; skip
            host = env.get("POSTGRES_HOST", "")
            broker = env.get("CELERY_BROKER_URL", "")
            assert host == "postgres", f"{name!r} POSTGRES_HOST should be 'postgres' (docker DNS), got {host!r}"
            assert "redis://redis:" in broker, (
                f"{name!r} CELERY_BROKER_URL should target the 'redis' service "
                f"hostname, got {broker!r} — using localhost will fail inside the container"
            )
