"""Tests for codebook version_manager.apply_proposal.

Real DB rows (Organization → Team → Study) are required because
``apply_proposal`` runs ORM queries against ``CodebookVersion.objects``
and creates ``CodeMapping`` rows that have FK constraints back to Study.
A previous MagicMock-based fixture compiled but failed at runtime when
Django tried to coerce the Mock into a UUID.
"""

from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model

from merism.codebook.models import CodebookVersion, CodeChange, CodeMapping
from merism.models import Organization, Study, Team


@pytest.fixture
def study(db) -> Study:
    """Real Study row with a seeded 3-code codebook."""
    User = get_user_model()
    user = User.objects.create_superuser(
        username="vm-test@m.test", email="vm-test@m.test", password="x"
    )
    org = Organization.objects.create(name="VM Org", slug="vm-test")
    team = Team.objects.create(name="VM Team", organization=org)
    s = Study.objects.create(
        team=team,
        created_by=user,
        research_goal="version manager test",
        codebook=[
            {"code_id": "pricing", "name": "Pricing", "description": "About pricing", "source": "seeded"},
            {"code_id": "ux_issue", "name": "UX Issue", "description": "Usability problems", "source": "seeded"},
            {"code_id": "feature_req", "name": "Feature Request", "description": "Wants new feature", "source": "seeded"},
        ],
    )
    return s


class TestVersionManagerApply:
    def test_apply_add_creates_new_version(self, study: Study) -> None:
        from asgiref.sync import async_to_sync

        from merism.codebook.version_manager import apply_proposal

        v1 = CodebookVersion.objects.create(
            team_id=study.team_id, study_id=study.id, version=1,
            codes=study.codebook, source="seed",
        )
        change = CodeChange.objects.create(
            team_id=study.team_id, study_id=study.id, from_version=v1,
            change_type="add",
            payload={"code": {"code_id": "new_code", "name": "New Code", "description": "test"}},
            status="approved",
        )

        v2 = async_to_sync(apply_proposal)(study, change)

        assert v2.version == 2
        assert any(c["code_id"] == "new_code" for c in v2.codes)
        change.refresh_from_db()
        assert change.status == "applied"

    def test_apply_merge_removes_sources_and_creates_mapping(self, study: Study) -> None:
        from asgiref.sync import async_to_sync

        from merism.codebook.version_manager import apply_proposal

        v1 = CodebookVersion.objects.create(
            team_id=study.team_id, study_id=study.id, version=1,
            codes=study.codebook, source="seed",
        )
        change = CodeChange.objects.create(
            team_id=study.team_id, study_id=study.id, from_version=v1,
            change_type="merge",
            payload={"source_ids": ["ux_issue", "feature_req"], "target_id": "pricing"},
            status="approved",
        )

        v2 = async_to_sync(apply_proposal)(study, change)

        code_ids = [c["code_id"] for c in v2.codes]
        assert "ux_issue" not in code_ids
        assert "feature_req" not in code_ids
        assert "pricing" in code_ids
        assert CodeMapping.objects.filter(change=change).count() == 2

    def test_apply_deprecate_marks_status(self, study: Study) -> None:
        from asgiref.sync import async_to_sync

        from merism.codebook.version_manager import apply_proposal

        v1 = CodebookVersion.objects.create(
            team_id=study.team_id, study_id=study.id, version=1,
            codes=study.codebook, source="seed",
        )
        change = CodeChange.objects.create(
            team_id=study.team_id, study_id=study.id, from_version=v1,
            change_type="deprecate",
            payload={"code_id": "ux_issue", "replaced_by": "pricing"},
            status="approved",
        )

        v2 = async_to_sync(apply_proposal)(study, change)

        deprecated = next(c for c in v2.codes if c["code_id"] == "ux_issue")
        assert deprecated["status"] == "deprecated"
        mapping = CodeMapping.objects.get(change=change)
        assert mapping.old_code_id == "ux_issue"
        assert mapping.new_code_id == "pricing"
