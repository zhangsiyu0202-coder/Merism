"""``python manage.py ensure_superuser``

Idempotent — create the default dev superuser if it does not already exist.
Safe to run on every boot of ``bin/setup-dev.sh``.

Credentials:
    email:    admin@merism.test
    password: merism-dev

Override via env vars MERISM_SUPERUSER_EMAIL / MERISM_SUPERUSER_PASSWORD.
"""

from __future__ import annotations

import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Create the default dev superuser if it doesn't exist."

    def handle(self, *args: object, **options: object) -> None:
        User = get_user_model()
        email = os.environ.get("MERISM_SUPERUSER_EMAIL", "admin@merism.test")
        password = os.environ.get("MERISM_SUPERUSER_PASSWORD", "merism-dev")

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
        if created:
            user.set_password(password)
            user.save(update_fields=["password"])
            self.stdout.write(
                self.style.SUCCESS(f"Created superuser {email} (password: {password})")
            )
        else:
            # Ensure staff / superuser remain set if someone edited the row.
            changed = False
            if not user.is_staff:
                user.is_staff = True
                changed = True
            if not user.is_superuser:
                user.is_superuser = True
                changed = True
            if changed:
                user.save(update_fields=["is_staff", "is_superuser"])
            self.stdout.write(f"Superuser {email} already exists.")
