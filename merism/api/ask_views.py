"""Ask Merism endpoints — with tool calling + RAG transcript search.

/api/ask/stream/ → POST {question, history?} → SSE stream
/api/ask/title/ → POST {content} → JSON {title}
/api/knowledge/search/ → POST {query} → JSON results
"""

from __future__ import annotations

import json
import logging
from typing import Any, Iterator

from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, JsonResponse, StreamingHttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.db.models import Q as models_Q
from django.views.decorators.http import require_http_methods

logger = logging.getLogger(__name__)

# ── Tool definitions ────────────────────────────────────────

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "create_study",
            "description": "创建一个新的定性研究项目。当用户表达想要创建研究、访谈、调研的意图时调用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "研究项目名称"},
                    "research_goal": {"type": "string", "description": "研究目标"},
                    "interview_mode": {"type": "string", "enum": ["voice", "text"], "description": "访谈模式"},
                },
                "required": ["name", "research_goal"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_transcripts",
            "description": "搜索访谈转写稿内容。当用户询问已有访谈内容、参与者反馈、某个主题的讨论时调用。使用语义+关键词混合检索。",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "搜索关键词或语义查询"},
                    "study_id": {"type": "string", "description": "限定在某个研究内搜索（可选）"},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_studies",
            "description": "列出用户的所有研究项目。当用户问'我有哪些研究'、'最近的项目'、需要了解研究概况时调用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "status": {"type": "string", "enum": ["draft", "live", "closed", "all"], "description": "按状态筛选"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_study",
            "description": "读取某个研究的详细信息（目标、状态、访谈数、洞察摘要等）。当用户问某个具体研究的情况时调用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "study_id": {"type": "string", "description": "研究 ID"},
                },
                "required": ["study_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "generate_report_section",
            "description": "基于访谈数据生成一段研究报告内容（如发现总结、建议、主题分析）。当用户要求生成报告、总结发现、写分析时调用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "study_id": {"type": "string", "description": "研究 ID"},
                    "section_type": {"type": "string", "enum": ["summary", "findings", "recommendations", "themes"], "description": "报告段落类型"},
                    "focus": {"type": "string", "description": "聚焦的具体方面（可选）"},
                },
                "required": ["study_id", "section_type"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "analyze_sessions",
            "description": "分析某个研究的访谈数据统计（完成数、平均时长、状态分布等）。当用户问数据概况、进度时调用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "study_id": {"type": "string", "description": "研究 ID"},
                },
                "required": ["study_id"],
            },
        },
    },
]

SYSTEM_PROMPT = """你是 Merism，一个 AI 定性研究助手。

你的能力：
- 回答关于定性研究方法、访谈技巧、数据分析的问题
- 帮助用户创建新的研究项目（使用 create_study 工具）
- 搜索已有的访谈转写稿内容（使用 search_transcripts 工具）
- 提供研究设计建议

当用户想创建研究时，使用 create_study。
当用户询问已有访谈内容时，使用 search_transcripts 搜索后引用结果回答。
回答使用中文，保持简洁专业。引用转写稿时标注来源。"""


def _sse(event: str, data: dict[str, Any]) -> bytes:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n".encode("utf-8")


def _execute_tool(tool_name: str, args: dict[str, Any], user) -> dict[str, Any]:
    if tool_name == "create_study":
        return _execute_create_study(args, user)
    elif tool_name == "search_transcripts":
        return _execute_search_transcripts(args, user)
    elif tool_name == "list_studies":
        return _execute_list_studies(args, user)
    elif tool_name == "read_study":
        return _execute_read_study(args, user)
    elif tool_name == "generate_report_section":
        return _execute_generate_report_section(args, user)
    elif tool_name == "analyze_sessions":
        return _execute_analyze_sessions(args, user)
    return {"error": f"Unknown tool: {tool_name}"}


def _execute_create_study(args: dict[str, Any], user) -> dict[str, Any]:
    from merism.models import OrganizationMembership, Study, Team

    membership = OrganizationMembership.objects.filter(user=user).select_related("organization").first()
    if not membership:
        return {"error": "用户没有关联的工作空间"}
    team = Team.objects.filter(organization=membership.organization).first()
    if not team:
        return {"error": "找不到团队"}

    study = Study.objects.create(
        name=args.get("name", "未命名研究"),
        research_goal=args.get("research_goal", ""),
        interview_mode=args.get("interview_mode", "voice"),
        team=team,
        created_by=user,
    )
    return {
        "success": True,
        "study_id": str(study.id),
        "name": study.name,
        "research_goal": study.research_goal,
        "url": f"/studies/{study.id}/settings",
        "artifact": {
            "type": "study_card",
            "id": str(study.id),
            "data": {"name": study.name, "goal": study.research_goal, "mode": study.interview_mode, "status": study.status},
        },
    }


def _execute_search_transcripts(args: dict[str, Any], user) -> dict[str, Any]:
    """Hybrid search (BM25 + vector + RRF) over transcript chunks + findings."""
    from merism.knowledge.search import chunk_search_team
    from merism.models import OrganizationMembership, Team

    query = args.get("query", "")
    if not query:
        return {"results": [], "findings": []}

    membership = OrganizationMembership.objects.filter(user=user).select_related("organization").first()
    if not membership:
        return {"results": [], "findings": [], "message": "无权限"}
    team = Team.objects.filter(organization=membership.organization).first()
    if not team:
        return {"results": [], "findings": [], "message": "无团队"}

    # Hybrid retrieval (BM25 + cosine + RRF fusion)
    chunks = chunk_search_team(team_id=team.id, query=query, limit=5)

    results = []
    for chunk in chunks:
        results.append({
            "content": chunk.content[:400],
            "session_id": chunk.metadata.get("session_id", ""),
            "study_id": chunk.metadata.get("study_id", ""),
            "score": round(1 - getattr(chunk, "distance", 0.5), 3),
        })

    # Also search findings for richer context
    findings = _search_findings(team, query)

    return {"results": results, "findings": findings, "count": len(results)}


def _search_findings(team, query: str) -> list[dict[str, Any]]:
    """Search InsightFinding by title/summary text match."""
    from merism.models import InsightFinding

    try:
        matches = InsightFinding.objects.filter(
            team=team,
        ).filter(
            models_Q(title__icontains=query[:30]) | models_Q(summary__icontains=query[:30])
        )[:3]
        return [
            {
                "id": str(f.id),
                "title": f.title,
                "summary": f.summary[:200],
                "themes": f.themes if isinstance(f.themes, list) else [],
            }
            for f in matches
        ]
    except Exception:
        return []


def _get_team_for_user(user):
    from merism.models import OrganizationMembership, Team
    membership = OrganizationMembership.objects.filter(user=user).select_related("organization").first()
    if not membership:
        return None
    return Team.objects.filter(organization=membership.organization).first()


def _execute_list_studies(args: dict[str, Any], user) -> dict[str, Any]:
    from merism.models import Study
    team = _get_team_for_user(user)
    if not team:
        return {"error": "无团队"}
    qs = Study.objects.filter(team=team).order_by("-created_at")
    status = args.get("status", "all")
    if status and status != "all":
        qs = qs.filter(status=status)
    studies = qs[:20]
    return {
        "studies": [
            {"id": str(s.id), "name": s.name, "status": s.status, "research_goal": s.research_goal[:100], "interview_mode": s.interview_mode}
            for s in studies
        ],
        "total": qs.count(),
    }


def _execute_read_study(args: dict[str, Any], user) -> dict[str, Any]:
    from merism.models import InterviewSession, Study
    team = _get_team_for_user(user)
    if not team:
        return {"error": "无团队"}
    try:
        study = Study.objects.get(id=args["study_id"], team=team)
    except Study.DoesNotExist:
        return {"error": "研究不存在"}
    sessions = InterviewSession.objects.filter(study=study)
    return {
        "id": str(study.id),
        "name": study.name,
        "status": study.status,
        "research_goal": study.research_goal,
        "interview_mode": study.interview_mode,
        "target_completed_count": study.target_completed_count,
        "sessions_completed": sessions.filter(status="completed").count(),
        "sessions_total": sessions.count(),
        "created_at": study.created_at.isoformat() if study.created_at else None,
    }


def _execute_generate_report_section(args: dict[str, Any], user) -> dict[str, Any]:
    """Generate a report section using LLM based on study data."""
    from merism.memai.llm import get_llm, default_model
    from merism.models import InterviewSession, Study
    team = _get_team_for_user(user)
    if not team:
        return {"error": "无团队"}
    try:
        study = Study.objects.get(id=args["study_id"], team=team)
    except Study.DoesNotExist:
        return {"error": "研究不存在"}

    sessions = InterviewSession.objects.filter(study=study, status="completed")
    transcripts = []
    for s in sessions[:10]:
        if s.transcript:
            text = "\n".join(f"{t.get('role')}: {t.get('text','')}" for t in s.transcript[:8])
            transcripts.append(text)

    section_type = args.get("section_type", "summary")
    focus = args.get("focus", "")

    prompt = f"""基于以下访谈数据，生成一段{section_type}类型的研究报告内容。
研究目标：{study.research_goal}
聚焦方面：{focus or '整体'}
访谈数据（{len(transcripts)}场）：
{chr(10).join(transcripts[:5])}

请用中文生成专业的研究报告段落（200-400字）。"""

    try:
        client = get_llm()
        response = client.chat.completions.create(
            model=default_model(), messages=[{"role": "user", "content": prompt}], max_tokens=600, temperature=0.3,
        )
        report_content = response.choices[0].message.content
        artifact_id = f"report-{study.id}-{section_type}"
        return {
            "section_type": section_type,
            "content": report_content,
            "study_name": study.name,
            "artifact": {
                "type": "report_section",
                "id": artifact_id,
                "data": {"study_id": str(study.id), "study_name": study.name, "section_type": section_type, "content": report_content},
            },
        }
    except Exception as exc:
        return {"error": f"生成失败: {exc}"}


def _execute_analyze_sessions(args: dict[str, Any], user) -> dict[str, Any]:
    from django.db.models import Avg, Count, DurationField, ExpressionWrapper, F
    from merism.models import InterviewSession, Study
    team = _get_team_for_user(user)
    if not team:
        return {"error": "无团队"}
    try:
        study = Study.objects.get(id=args["study_id"], team=team)
    except Study.DoesNotExist:
        return {"error": "研究不存在"}

    sessions = InterviewSession.objects.filter(study=study)
    stats = sessions.aggregate(
        total=Count("id"),
        completed=Count("id", filter=models_Q(status="completed")),
        in_progress=Count("id", filter=models_Q(status="in_progress")),
        abandoned=Count("id", filter=models_Q(status="abandoned")),
    )
    avg_dur = sessions.filter(started_at__isnull=False, ended_at__isnull=False).annotate(
        dur=ExpressionWrapper(F("ended_at") - F("started_at"), output_field=DurationField())
    ).aggregate(avg=Avg("dur"))["avg"]

    result = {
        "study_name": study.name,
        "total_sessions": stats["total"],
        "completed": stats["completed"],
        "in_progress": stats["in_progress"],
        "abandoned": stats["abandoned"],
        "avg_duration_minutes": round(avg_dur.total_seconds() / 60, 1) if avg_dur else None,
        "completion_rate": round(stats["completed"] / stats["total"] * 100, 1) if stats["total"] > 0 else 0,
    }
    result["artifact"] = {
        "type": "chart",
        "id": f"chart-sessions-{study.id}",
        "data": {
            "chart_type": "bar",
            "title": f"{study.name} · 访谈进度",
            "categories": ["已完成", "进行中", "已放弃"],
            "values": [stats["completed"], stats["in_progress"], stats["abandoned"]],
        },
    }
    return result


def _stream_answer(question: str, history: list[dict], user) -> Iterator[bytes]:
    """Stream answer with multi-turn tool calling + thinking states."""
    from merism.memai.llm import get_llm, default_model

    try:
        client = get_llm()
        model = default_model()
    except Exception as exc:
        logger.warning("ask.client_init_failed", extra={"err": str(exc)})
        yield _sse("delta", {"partial": "(LLM 未配置)"})
        yield _sse("done", {"answer_markdown": "(LLM 未配置)", "tool_calls": []})
        return

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages.extend(history[-10:])
    messages.append({"role": "user", "content": question})

    all_tool_results: list[dict[str, Any]] = []
    max_rounds = 3  # prevent infinite tool loops

    for round_num in range(max_rounds):
        try:
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                tools=TOOLS,
                stream=True,
                max_tokens=1500,
                temperature=0.3,
            )
        except Exception as exc:
            logger.exception("ask.request_failed")
            yield _sse("error", {"message": f"LLM 请求失败: {exc}"})
            return

        text_accum: list[str] = []
        tool_calls_accum: dict[int, dict] = {}

        try:
            for chunk in response:
                choice = chunk.choices[0] if chunk.choices else None
                if not choice:
                    continue
                delta = choice.delta
                if delta.content:
                    text_accum.append(delta.content)
                    yield _sse("delta", {"partial": "".join(text_accum)})
                if delta.tool_calls:
                    for tc in delta.tool_calls:
                        idx = tc.index
                        if idx not in tool_calls_accum:
                            tool_calls_accum[idx] = {"id": tc.id or "", "name": "", "arguments": ""}
                        if tc.id:
                            tool_calls_accum[idx]["id"] = tc.id
                        if tc.function:
                            if tc.function.name:
                                tool_calls_accum[idx]["name"] = tc.function.name
                            if tc.function.arguments:
                                tool_calls_accum[idx]["arguments"] += tc.function.arguments
        except Exception as exc:
            logger.exception("ask.stream_failed")
            yield _sse("error", {"message": str(exc)})
            return

        # No tool calls — we're done
        if not tool_calls_accum:
            break

        # Execute tool calls and feed results back to LLM
        assistant_content = "".join(text_accum)
        tool_call_messages = []
        for idx in sorted(tool_calls_accum.keys()):
            tc = tool_calls_accum[idx]
            try:
                args = json.loads(tc["arguments"]) if tc["arguments"] else {}
            except json.JSONDecodeError:
                args = {}

            yield _sse("thinking", {"status": f"正在执行: {tc['name']}..."})
            yield _sse("tool_call", {"name": tc["name"], "arguments": args})

            result = _execute_tool(tc["name"], args, user)
            all_tool_results.append({"name": tc["name"], "result": result})
            yield _sse("tool_result", {"name": tc["name"], "result": result})

            tool_call_messages.append({
                "role": "assistant",
                "content": assistant_content or None,
                "tool_calls": [{"id": tc["id"], "type": "function", "function": {"name": tc["name"], "arguments": tc["arguments"]}}],
            })
            tool_call_messages.append({
                "role": "tool",
                "tool_call_id": tc["id"],
                "content": json.dumps(result, ensure_ascii=False),
            })

        # Add tool interaction to messages for next round
        messages.extend(tool_call_messages)
        yield _sse("thinking", {"status": "正在整理回答..."})
        text_accum = []  # reset for next round

    # Generate title for first message
    title = None
    if not history:
        from merism.memai.title_generator import generate_title
        try:
            title = generate_title(question)
        except Exception:
            pass

    answer = "".join(text_accum) or ""
    yield _sse("done", {
        "answer_markdown": answer,
        "tool_calls": all_tool_results,
        "title": title,
    })



@csrf_exempt
@login_required
@require_http_methods(["POST"])
def ask_stream(request: HttpRequest) -> StreamingHttpResponse:
    try:
        body = json.loads(request.body or b"{}")
    except Exception:
        body = {}
    question = (body.get("question") or "").strip()
    if not question:
        return JsonResponse({"error": "question required"}, status=400)
    history = body.get("history", [])

    response = StreamingHttpResponse(
        _stream_answer(question, history, request.user),
        content_type="text/event-stream",
    )
    response["Cache-Control"] = "no-cache"
    response["X-Accel-Buffering"] = "no"
    return response


@csrf_exempt
@login_required
@require_http_methods(["POST"])
def ask_title(request: HttpRequest) -> JsonResponse:
    """Generate a title for content using LLM."""
    from merism.memai.title_generator import generate_title

    try:
        body = json.loads(request.body or b"{}")
    except Exception:
        body = {}
    content = (body.get("content") or "").strip()
    if not content:
        return JsonResponse({"title": "新对话"})
    title = generate_title(content)
    return JsonResponse({"title": title})


@csrf_exempt
@login_required
@require_http_methods(["POST"])
def knowledge_search(request: HttpRequest) -> JsonResponse:
    """Semantic search over knowledge chunks."""
    try:
        body = json.loads(request.body or b"{}")
    except Exception:
        body = {}
    query = (body.get("query") or "").strip()
    if not query:
        return JsonResponse({"results": []})

    result = _execute_search_transcripts({"query": query}, request.user)
    return JsonResponse(result)
