"""Tests for the cleaning stages — glossary ASR correction + normalization."""

from __future__ import annotations

import pytest
from asgiref.sync import async_to_sync

from merism.cleaning.stages.stage1_asr_correct import StageContext, correct_with_glossary
from merism.cleaning.stages.stage3_normalize import normalize_text


class TestStage3Normalize:
    def test_collapses_whitespace(self) -> None:
        turns = [{"role": "participant", "text": "hello    world  "}]
        result = async_to_sync(normalize_text)(turns, StageContext("t", "s", "sess"))
        assert result[0]["text"] == "hello world"

    def test_full_width_punctuation_converted(self) -> None:
        turns = [{"role": "participant", "text": "你好，世界！"}]
        result = async_to_sync(normalize_text)(turns, StageContext("t", "s", "sess"))
        # NFKC + our map turn ， into ,
        assert "," in result[0]["text"]
        assert "!" in result[0]["text"]

    def test_empty_text_passthrough(self) -> None:
        turns = [{"role": "participant", "text": ""}]
        result = async_to_sync(normalize_text)(turns, StageContext("t", "s", "sess"))
        assert result[0]["text"] == ""

    def test_preserves_newlines(self) -> None:
        turns = [{"role": "participant", "text": "line1\nline2"}]
        result = async_to_sync(normalize_text)(turns, StageContext("t", "s", "sess"))
        assert "line1" in result[0]["text"]
        assert "line2" in result[0]["text"]


class TestStage1Glossary:
    """Integration test — requires DB fixture."""

    @pytest.mark.django_db
    def test_no_glossary_passes_through(self) -> None:
        """When no glossary entries exist, turns are unchanged."""
        from merism.models import Organization, Team

        org = Organization.objects.create(name="Test", slug="test-gloss-1")
        team = Team.objects.create(name="T", organization=org)

        turns = [{"role": "participant", "text": "hello"}]
        result = async_to_sync(correct_with_glossary)(
            turns, StageContext(team.id, None, "sess"),
        )
        assert result[0]["text"] == "hello"

    @pytest.mark.django_db
    def test_variants_replaced_with_canonical(self) -> None:
        from merism.models import Glossary, Organization, Team

        org = Organization.objects.create(name="Test", slug="test-gloss-2")
        team = Team.objects.create(name="T", organization=org)

        Glossary.objects.create(
            team=team,
            study=None,
            canonical="Merism",
            variants=["米瑞姆", "merism platform", "MERIISM"],
            case_insensitive=True,
        )

        turns = [
            {"role": "participant", "text": "I love 米瑞姆 so much"},
            {"role": "participant", "text": "The meriism app works well"},
        ]
        result = async_to_sync(correct_with_glossary)(
            turns, StageContext(team.id, None, "sess"),
        )
        assert "Merism" in result[0]["text"]
        assert "米瑞姆" not in result[0]["text"]
