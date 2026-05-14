from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestRetagging:
    @pytest.mark.asyncio
    async def test_retag_skips_when_no_mappings(self):
        from merism.codebook.retagging import retag_affected_quotes

        study = MagicMock()
        change = MagicMock()

        with patch("merism.codebook.retagging._get_mappings", new_callable=AsyncMock, return_value=[]):
            result = await retag_affected_quotes(study, change)

        assert result == 0

    @pytest.mark.asyncio
    async def test_retag_clears_and_retags_affected(self):
        from merism.codebook.retagging import retag_affected_quotes

        study = MagicMock()
        change = MagicMock()

        mapping = MagicMock()
        mapping.old_code_id = "old_code"

        quote = MagicMock()
        quote.tags = {"deductive": [{"code_id": "old_code", "confidence": 0.9}]}
        quote.save = MagicMock()

        with (
            patch("merism.codebook.retagging._get_mappings", new_callable=AsyncMock, return_value=[mapping]),
            patch("merism.codebook.retagging._find_affected_quotes", new_callable=AsyncMock, return_value=[quote]),
            patch("merism.codebook.retagging._clear_deductive_tags", new_callable=AsyncMock),
            patch("merism.memai.agents.quote_tagger.tag_quotes_for_session", new_callable=AsyncMock),
        ):
            result = await retag_affected_quotes(study, change)

        assert result == 1
