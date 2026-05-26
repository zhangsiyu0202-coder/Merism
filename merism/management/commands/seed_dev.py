"""``python manage.py seed_dev``

One-shot idempotent dev environment seed. Combines and supersedes the
chain that ``bin/setup-dev.sh`` used to run separately:

  - ``ensure_superuser`` — create the dev admin
  - ``seed_demo``        — create demo org / team / studies
  - manual: add admin to every existing org

Differences vs the old chain:

  - **Always resets the admin password** to the configured value (the
    old ``ensure_superuser`` only set it on first creation, so a stale
    DB row would silently mismatch the documented credentials).
  - **Adds the admin to every existing organization** so they can see
    studies created by other seed commands or fixtures (the old chain
    only joined them to ``Merism Demo``).
  - Calls ``seed_demo`` if its sentinel rows are missing.

Safe to re-run on every boot of ``bin/dev.sh`` or ``bin/reset.sh``.

Credentials:
    email:    admin@merism.test
    password: merism-dev

Override via env vars MERISM_SUPERUSER_EMAIL / MERISM_SUPERUSER_PASSWORD.
"""

from __future__ import annotations

import os

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import BaseCommand

from merism.models import Organization, OrganizationMembership


class Command(BaseCommand):
    help = "Idempotent dev seed: admin + org membership + demo data."

    def handle(self, *args: object, **options: object) -> None:
        User = get_user_model()
        email = os.environ.get("MERISM_SUPERUSER_EMAIL", "admin@merism.test")
        password = os.environ.get("MERISM_SUPERUSER_PASSWORD", "merism-dev")

        # ── 1. Admin user (always reset password) ─────────────
        user, created = User.objects.get_or_create(
            username=email,
            defaults={
                "email": email,
                "first_name": "Merism",
                "last_name": "Admin",
                "is_staff": True,
                "is_superuser": True,
            },
        )
        # Re-affirm staff/superuser flags in case they were edited away.
        flags_changed = False
        if not user.is_staff:
            user.is_staff = True
            flags_changed = True
        if not user.is_superuser:
            user.is_superuser = True
            flags_changed = True
        if flags_changed:
            user.save(update_fields=["is_staff", "is_superuser"])

        # **Always** reset the password — the whole point of seed_dev is
        # that the documented credentials always work.
        user.set_password(password)
        user.save(update_fields=["password"])

        verb = "created" if created else "updated"
        self.stdout.write(self.style.SUCCESS(f"  admin {verb}: {email} / {password} (is_superuser=True)"))

        # ── 2. Demo data (call seed_demo only if missing) ──────
        if not Organization.objects.filter(slug="merism-demo").exists():
            self.stdout.write("  running seed_demo (Merism Demo missing)...")
            call_command("seed_demo")

        # ── 3. Add admin to every existing org ─────────────────
        # Dev convenience: a researcher logged in as admin should be
        # able to see all data, regardless of which org seeded the
        # study. This is dev-only behavior — prod uses real RBAC.
        joined = 0
        for org in Organization.objects.all():
            _, created = OrganizationMembership.objects.get_or_create(
                user=user,
                organization=org,
                defaults={"role": "owner"},
            )
            if created:
                joined += 1

        if joined > 0:
            self.stdout.write(self.style.SUCCESS(f"  joined admin to {joined} new org(s) as owner"))
        else:
            existing = OrganizationMembership.objects.filter(user=user).count()
            self.stdout.write(f"  admin already in {existing} org(s)")

        self.stdout.write(self.style.SUCCESS("seed_dev complete."))
