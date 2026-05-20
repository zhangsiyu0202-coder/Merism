"""Tests for Study primary link auto-creation + interview_number allocation.

Per 2026-05-20 simplification:
- Every Study auto-gets exactly one ``StudyLink(is_primary=True)``.
- ``UniqueConstraint`` guarantees at most one primary per study.
- ``InterviewSession.interview_number`` is allocated atomically per study.
"""

from __future__ import annotations

import pytest
from django.db import IntegrityError, transaction

from merism.models import (
    InterviewGuide,
    InterviewSession,
    Participation,
    Study,
    StudyLink,
    Team,
)


@pytest.mark.django_db
class TestStudyPrimaryLink:
    def _make_team(self) -> Team:
        from merism.models import Organization

        org = Organization.objects.create(name="Org-T", slug="org-t")
        return Team.objects.create(name="Team-T", organization=org)

    def test_study_creation_auto_creates_primary_link(self) -> None:
        team = self._make_team()
        study = Study.objects.create(
            team=team, name="Auto", research_goal="goal"
        )
        primary = study.primary_link
        assert primary is not None
        assert primary.is_primary is True
        assert primary.is_active is True
        assert primary.link_mode == StudyLink.LinkMode.NAMED
        assert primary.full_url.startswith("/i/") or primary.full_url.startswith("https://")

    def test_share_url_resolves_to_primary_link(self) -> None:
        team = self._make_team()
        study = Study.objects.create(
            team=team, name="Share", research_goal="g"
        )
        assert study.primary_link is not None
        assert study.primary_link.url_path == f"/i/{study.primary_link.slug}"

    def test_unique_constraint_one_primary_per_study(self) -> None:
        team = self._make_team()
        study = Study.objects.create(
            team=team, name="Unique", research_goal="g"
        )
        # Auto-create gave us one. Trying to insert a second primary
        # must fail at the DB level.
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                StudyLink.objects.create(
                    team=team, study=study, is_primary=True
                )

    def test_secondary_links_allowed_when_not_primary(self) -> None:
        """Multiple links per study still allowed (broadcast / invitation
        flows may create derived links). Only is_primary=True is unique.
        """
        team = self._make_team()
        study = Study.objects.create(
            team=team, name="Multi", research_goal="g"
        )
        # Auto primary already exists. Add a secondary.
        secondary = StudyLink.objects.create(
            team=team, study=study, is_primary=False
        )
        assert secondary.id != study.primary_link.id
        assert study.links.count() == 2
        # Primary still resolves cleanly.
        assert study.primary_link.is_primary is True

    def test_signal_idempotent_on_resave(self) -> None:
        team = self._make_team()
        study = Study.objects.create(
            team=team, name="Resave", research_goal="g"
        )
        first_primary_id = study.primary_link.id
        # Touching the study row should NOT create a second primary link.
        study.name = "Resave (renamed)"
        study.save(update_fields=["name", "updated_at"])
        assert study.primary_link.id == first_primary_id
        assert study.links.filter(is_primary=True).count() == 1


@pytest.mark.django_db
class TestInterviewNumber:
    def _make_team(self) -> Team:
        from merism.models import Organization

        org = Organization.objects.create(name="Org-N", slug="org-n")
        return Team.objects.create(name="Team-N", organization=org)

    def _make_session(
        self, *, study: Study, team: Team, guide: InterviewGuide
    ) -> InterviewSession:
        ptn = Participation.objects.create(team=team, study=study)
        # Mirror /start/ logic: allocate within atomic+select_for_update.
        from django.db import models

        with transaction.atomic():
            study_locked = Study.objects.select_for_update().get(id=study.id)
            next_n = (
                InterviewSession.objects.filter(study=study_locked)
                .aggregate(m=models.Max("interview_number"))
                .get("m")
                or 0
            ) + 1
            return InterviewSession.objects.create(
                team=team,
                study=study_locked,
                participation=ptn,
                guide=guide,
                interview_number=next_n,
            )

    def test_first_session_gets_number_1(self) -> None:
        team = self._make_team()
        study = Study.objects.create(team=team, research_goal="g")
        guide = InterviewGuide.objects.create(team=team, study=study, sections=[])
        session = self._make_session(study=study, team=team, guide=guide)
        assert session.interview_number == 1

    def test_subsequent_sessions_increment(self) -> None:
        team = self._make_team()
        study = Study.objects.create(team=team, research_goal="g")
        guide = InterviewGuide.objects.create(team=team, study=study, sections=[])
        s1 = self._make_session(study=study, team=team, guide=guide)
        s2 = self._make_session(study=study, team=team, guide=guide)
        s3 = self._make_session(study=study, team=team, guide=guide)
        assert [s1.interview_number, s2.interview_number, s3.interview_number] == [
            1,
            2,
            3,
        ]

    def test_numbers_isolated_per_study(self) -> None:
        team = self._make_team()
        study_a = Study.objects.create(team=team, research_goal="a")
        study_b = Study.objects.create(team=team, research_goal="b")
        guide_a = InterviewGuide.objects.create(team=team, study=study_a, sections=[])
        guide_b = InterviewGuide.objects.create(team=team, study=study_b, sections=[])
        a1 = self._make_session(study=study_a, team=team, guide=guide_a)
        b1 = self._make_session(study=study_b, team=team, guide=guide_b)
        a2 = self._make_session(study=study_a, team=team, guide=guide_a)
        # Each study counts from 1 independently.
        assert a1.interview_number == 1
        assert b1.interview_number == 1
        assert a2.interview_number == 2


@pytest.mark.django_db
class TestStudySerializer:
    def test_share_url_and_primary_link_in_response(self) -> None:
        from merism.api.serializers import StudySerializer
        from merism.models import Organization

        org = Organization.objects.create(name="Org-S", slug="org-s")
        team = Team.objects.create(name="Team-S", organization=org)
        study = Study.objects.create(team=team, research_goal="g", name="S")
        data = StudySerializer(study).data
        assert "share_url" in data
        assert data["share_url"] is not None
        assert data["share_url"].startswith("/i/") or data["share_url"].startswith(
            "https://"
        )
        assert data["primary_link"] is not None
        assert data["primary_link"]["is_active"] is True
        assert "slug" in data["primary_link"]
