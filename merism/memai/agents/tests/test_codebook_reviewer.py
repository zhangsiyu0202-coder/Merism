import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestCodebookReviewer:
    @pytest.mark.asyncio
    async def test_returns_empty_for_empty_codebook(self):
        from merism.memai.agents.codebook_reviewer import review_codebook

        study = MagicMock()
        study.codebook = []

        result = await review_codebook(study, [])
        assert result == []

    @pytest.mark.asyncio
    async def test_filters_low_confidence_proposals(self):
        from merism.memai.agents.codebook_reviewer import review_codebook

        study = MagicMock()
        study.id = "test-study"
        study.team = MagicMock()
        study.codebook = [{"code_id": "a", "name": "A", "description": "a"}]

        llm_response = json.dumps({
            "proposals": [
                {"change_type": "add", "payload": {"code": {"code_id": "b", "name": "B", "description": "b", "source": "inductive"}}, "rationale": "valid", "confidence": 0.8},
                {"change_type": "deprecate", "payload": {"code_id": "x", "replaced_by": None}, "rationale": "low conf", "confidence": 0.3},
            ]
        })

        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(
            return_value=MagicMock(choices=[MagicMock(message=MagicMock(content=llm_response))])
        )

        with (
            patch("merism.memai.agents.codebook_reviewer.get_llm", return_value=mock_client),
            patch("merism.llm_gateway.client.get_client", side_effect=Exception("no gateway")),
        ):
            result = await review_codebook(study, [{"code_id": "b", "name": "B"}])

        assert len(result) == 1
        assert result[0]["change_type"] == "add"
