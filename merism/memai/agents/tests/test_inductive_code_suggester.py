import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestInductiveCodeSuggester:
    @pytest.mark.asyncio
    async def test_returns_empty_for_few_quotes(self):
        from merism.memai.agents.inductive_code_suggester import suggest_codes

        study = MagicMock()
        study.codebook = [{"code_id": "x", "name": "X", "description": "x"}]
        quotes = [MagicMock(text="short")]

        result = await suggest_codes(quotes, study)
        assert result == []

    @pytest.mark.asyncio
    async def test_parses_llm_response(self):
        from merism.memai.agents.inductive_code_suggester import suggest_codes

        study = MagicMock()
        study.id = "test-study"
        study.team = MagicMock()
        study.codebook = [{"code_id": "existing", "name": "Existing", "description": "exists"}]

        quotes = [MagicMock(text=f"quote text {i}") for i in range(5)]

        llm_response = json.dumps({
            "suggestions": [{
                "code_id": "new_pattern",
                "name": "New Pattern",
                "description": "A newly discovered pattern",
                "evidence_quotes": ["quote text 1", "quote text 3"],
                "rationale": "Not covered by existing codes",
            }]
        })

        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(
            return_value=MagicMock(choices=[MagicMock(message=MagicMock(content=llm_response))])
        )

        with (
            patch("merism.memai.agents.inductive_code_suggester.get_llm", return_value=mock_client),
            patch("merism.llm_gateway.client.get_client", side_effect=Exception("no gateway")),
        ):
            result = await suggest_codes(quotes, study)

        assert len(result) == 1
        assert result[0]["code_id"] == "new_pattern"
