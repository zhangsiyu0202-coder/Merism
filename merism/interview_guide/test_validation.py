from __future__ import annotations

import pytest
from rest_framework import serializers

from merism.interview_guide import validate_sections


class TestValidateSections:
    def test_preserves_builder_fields(self) -> None:
        sections = [
            {
                "id": "intro",
                "title": "Intro",
                "questions": [
                    {
                        "id": "q1",
                        "text": "Hello?",
                        "type": "conversational",
                        "probingAmount": "standard",
                        "probingInstructions": "Probe gently.",
                        "allowSkip": True,
                        "allowDynamicProbe": False,
                        "stimulusIds": ["stim-1"],
                    }
                ],
            }
        ]

        validated = validate_sections(sections)

        assert validated[0]["id"] == "intro"
        assert validated[0]["scope"] == "global"
        assert validated[0]["questions"][0]["type"] == "conversational"
        assert validated[0]["questions"][0]["probingAmount"] == "standard"
        assert validated[0]["questions"][0]["stimulusIds"] == ["stim-1"]
        assert validated[0]["questions"][0]["probe_policy"] == "light"
        assert validated[0]["questions"][0]["max_probes"] == 3

    def test_rejects_non_list_sections(self) -> None:
        with pytest.raises(serializers.ValidationError):
            validate_sections({})  # type: ignore[arg-type]
