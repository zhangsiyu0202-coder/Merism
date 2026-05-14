import uuid
from unittest.mock import MagicMock

import pytest

from merism.codebook.models import CodebookVersion, CodeChange, CodeMapping


@pytest.fixture
def study():
    s = MagicMock()
    s.id = uuid.uuid4()
    s.team = MagicMock()
    s.team.id = uuid.uuid4()
    s.codebook = [
        {"code_id": "pricing", "name": "Pricing", "description": "About pricing", "source": "seeded"},
        {"code_id": "ux_issue", "name": "UX Issue", "description": "Usability problems", "source": "seeded"},
        {"code_id": "feature_req", "name": "Feature Request", "description": "Wants new feature", "source": "seeded"},
    ]
    s.save = MagicMock()
    return s


class TestVersionManagerApply:
    @pytest.mark.django_db
    def test_apply_add_creates_new_version(self, study):
        from asgiref.sync import async_to_sync

        from merism.codebook.version_manager import apply_proposal

        # Create initial version
        v1 = CodebookVersion.objects.create(
            team_id=study.team.id, study_id=study.id, version=1,
            codes=study.codebook, source="seed",
        )
        change = CodeChange.objects.create(
            team_id=study.team.id, study_id=study.id, from_version=v1,
            change_type="add",
            payload={"code": {"code_id": "new_code", "name": "New Code", "description": "test"}},
            status="approved",
        )

        v2 = async_to_sync(apply_proposal)(study, change)

        assert v2.version == 2
        assert any(c["code_id"] == "new_code" for c in v2.codes)
        change.refresh_from_db()
        assert change.status == "applied"

    @pytest.mark.django_db
    def test_apply_merge_removes_sources_and_creates_mapping(self, study):
        from asgiref.sync import async_to_sync

        from merism.codebook.version_manager import apply_proposal

        v1 = CodebookVersion.objects.create(
            team_id=study.team.id, study_id=study.id, version=1,
            codes=study.codebook, source="seed",
        )
        change = CodeChange.objects.create(
            team_id=study.team.id, study_id=study.id, from_version=v1,
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

    @pytest.mark.django_db
    def test_apply_deprecate_marks_status(self, study):
        from asgiref.sync import async_to_sync

        from merism.codebook.version_manager import apply_proposal

        v1 = CodebookVersion.objects.create(
            team_id=study.team.id, study_id=study.id, version=1,
            codes=study.codebook, source="seed",
        )
        change = CodeChange.objects.create(
            team_id=study.team.id, study_id=study.id, from_version=v1,
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
