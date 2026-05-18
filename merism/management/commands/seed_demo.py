"""``python manage.py seed_demo``

Populate the dev DB with a minimal demo dataset so the UI has something
to render on first boot. Idempotent.

Creates:
    - 1 Organization: "Merism Demo"
    - 1 Team:         "Research"
    - 1 OrganizationMembership linking the superuser as OWNER
    - 3 Study rows (one per status: draft / recruiting / closed)

The superuser is created by ``ensure_superuser`` first; this command
assumes it exists and links it. Run both:

    python manage.py ensure_superuser
    python manage.py seed_demo
"""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from merism.models import (
    Organization,
    OrganizationMembership,
    Study,
    Team,
)


class Command(BaseCommand):
    help = "Seed the dev DB with a demo org + team + 3 studies."

    def handle(self, *args: object, **options: object) -> None:
        User = get_user_model()

        admin = User.objects.filter(is_superuser=True).order_by("pk").first()
        if admin is None:
            raise CommandError(
                "No superuser found. Run `python manage.py ensure_superuser` first."
            )

        org, org_created = Organization.objects.get_or_create(
            slug="merism-demo",
            defaults={"name": "Merism Demo"},
        )
        if org_created:
            self.stdout.write(self.style.SUCCESS(f"Created Organization {org.name}"))

        membership, mem_created = OrganizationMembership.objects.get_or_create(
            organization=org,
            user=admin,
            defaults={"role": OrganizationMembership.Role.OWNER},
        )
        if mem_created:
            self.stdout.write(f"Linked {admin.email} as OWNER of {org.name}")

        team, team_created = Team.objects.get_or_create(
            organization=org,
            name="Research",
            defaults={"config": {}},
        )
        if team_created:
            self.stdout.write(self.style.SUCCESS(f"Created Team {team.name}"))

        study_fixtures = [
            {
                "name": "Power user churn — day 14 cohort",
                "research_goal": (
                    "Understand the usage patterns and psychological friction points "
                    "that drive advanced users to cancel in the second week."
                ),
                "status": Study.Status.DRAFT,
                "interview_mode": Study.InterviewMode.VOICE,
                "estimated_minutes": 30,
            },
            {
                "name": "Onboarding — first 5 minutes",
                "research_goal": (
                    "What do new users do in their first 5 minutes, and where do the "
                    "'aha' vs 'abandon' signals diverge?"
                ),
                "status": Study.Status.LIVE,
                "interview_mode": Study.InterviewMode.VOICE,
                "estimated_minutes": 20,
            },
            {
                "name": "Pricing page — interview framework pilot",
                "research_goal": (
                    "Did participants understand the pricing tiers, and which tier did "
                    "they identify with? Closed study — used as a calibration reference."
                ),
                "status": Study.Status.CLOSED,
                "interview_mode": Study.InterviewMode.TEXT,
                "estimated_minutes": 15,
            },
        ]

        for fixture in study_fixtures:
            study, created = Study.objects.get_or_create(
                team=team,
                name=fixture["name"],
                defaults={
                    "created_by": admin,
                    "research_goal": fixture["research_goal"],
                    "status": fixture["status"],
                    "interview_mode": fixture["interview_mode"],
                    "estimated_minutes": fixture["estimated_minutes"],
                },
            )
            if created:
                self.stdout.write(f"  Study: {study.name} ({fixture['status']})")

        total = Study.objects.filter(team=team).count()
        self.stdout.write(
            self.style.SUCCESS(
                f"Done. {org.name} / {team.name} has {total} studies total."
            )
        )
