"""Recruitment message generator for one-click study outreach.

This is an internal agent step, not a researcher-facing chat surface. It
turns study context into a group-ready invite message for one outbound
channel at a time.
"""

from __future__ import annotations

import json
import logging
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from merism.memai.llm import default_model, get_llm
from merism.models import Study

logger = logging.getLogger(__name__)


class RecruitmentMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(..., min_length=1, max_length=80)
    body_markdown: str = Field(..., min_length=1)
    body_text: str = Field(..., min_length=1)


SYSTEM_PROMPT = """\
You write outbound recruitment invites for qualitative research studies.

Audience:
- Potential participants reading a group chat message.
- The researcher wants a message they can send immediately with no editing.

Rules:
- Be concise, concrete, and easy to skim.
- State who the study is for, what the participant will do, and how to join.
- Include the exact study link once near the end.
- Avoid hype, jargon, and fake urgency.
- Do not invent incentives, deadlines, or eligibility constraints that are
  not present in the provided context.
- `body_markdown` should be channel-ready Markdown for a group message.
- `body_text` should be the plain-text equivalent of the same message.
"""


SUBMIT_TOOL = {
    "type": "function",
    "function": {
        "name": "submit_recruitment_message",
        "description": "Return the final invite message for this channel.",
        "parameters": RecruitmentMessage.model_json_schema(),
    },
}


def generate_recruitment_message(
    *,
    study: Study,
    study_link: str,
    channel_type: str,
) -> RecruitmentMessage:
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "system",
            "content": _context_prompt(study=study, study_link=study_link, channel_type=channel_type),
        },
        {"role": "user", "content": "Write the recruitment invite now."},
    ]

    gw_client = None
    try:
        from merism.llm_gateway.client import sync_get_client

        gw_client = sync_get_client("chat", team=study.team, trace_id=uuid4())
    except Exception:
        pass

    if gw_client:
        completion = gw_client.sync_complete(
            messages=messages,
            tools=[SUBMIT_TOOL],
            tool_choice={"type": "function", "function": {"name": "submit_recruitment_message"}},
        )
    else:
        client = get_llm()
        completion = client.chat.completions.create(
            model=default_model(),
            messages=messages,
            tools=[SUBMIT_TOOL],
            tool_choice={"type": "function", "function": {"name": "submit_recruitment_message"}},
        )

    choice = completion.choices[0]
    tool_calls = getattr(choice.message, "tool_calls", None) or []
    if not tool_calls:
        logger.warning("memai.recruitment_message.no_tool_call")
        raise RuntimeError("Recruitment message generation returned no tool call")

    try:
        payload = json.loads(tool_calls[0].function.arguments)
        return RecruitmentMessage.model_validate(payload)
    except (json.JSONDecodeError, ValueError) as exc:
        logger.warning("memai.recruitment_message.parse_failed", extra={"error": str(exc)})
        raise RuntimeError("Recruitment message generation produced invalid JSON") from exc


def _context_prompt(*, study: Study, study_link: str, channel_type: str) -> str:
    quotas = json.dumps(study.recruitment_quotas or [], ensure_ascii=False)
    return (
        "<study>\n"
        f"name={study.name or '(untitled study)'}\n"
        f"research_goal={study.research_goal.strip()}\n"
        f"research_background={study.research_background.strip() or '(none)'}\n"
        f"target_audience={study.target_audience.strip() or '(none)'}\n"
        f"target_completed_count={study.target_completed_count}\n"
        f"estimated_minutes={study.estimated_minutes}\n"
        f"channel_type={channel_type}\n"
        f"study_link={study_link}\n"
        "</study>\n\n"
        "<quotas>\n"
        f"{quotas}\n"
        "</quotas>\n"
    )
