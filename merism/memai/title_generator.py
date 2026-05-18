"""LLM-powered title generation for conversations and studies."""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def generate_title(content: str, max_length: int = 30) -> str:
    """Generate a short Chinese title for the given content using LLM.

    Falls back to truncation if LLM is unavailable.
    """
    from merism.memai.llm import get_llm, default_model

    if not content.strip():
        return "新对话"

    try:
        client = get_llm()
        model = default_model()
        response = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": f"用中文为以下内容生成一个简短标题（不超过{max_length}个字，不要引号）。",
                },
                {"role": "user", "content": content[:500]},
            ],
            max_tokens=50,
            temperature=0.3,
        )
        title = (response.choices[0].message.content or "").strip().strip('"\'')
        return title[:max_length] if title else content[:max_length]
    except Exception as exc:
        logger.warning("title_generator.failed", extra={"error": str(exc)})
        return content[:max_length]
