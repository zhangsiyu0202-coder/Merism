"""Ask Merism endpoints.

Minimal working implementation of ``/api/ask/stream/`` + ``/api/knowledge/search/``
so the frontend AskPage is no longer a broken fetch. The endpoints are
intentionally scoped small:

- **/api/ask/stream/** → POST ``{question}`` → SSE stream of ``delta``
  events with a final ``done`` event carrying ``{answer_markdown,
  chart?, citations?}``. Under the hood we call our existing DeepSeek
  client with a conservative prompt that tells the model to answer
  briefly and cite nothing (we have no cross-study retrieval wired yet,
  so citing would be dishonest).

- **/api/knowledge/search/** → POST ``{query}`` → JSON list of matching
  ``KnowledgeChunk`` rows. Stub returns []; the real hybrid-search
  backend lands when the Repository tab goes live.

Both endpoints deliberately do the simplest useful thing. Swapping in
a retrieval-augmented implementation later changes the body of these
views without changing the URL contract.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Iterator

from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, JsonResponse, StreamingHttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

logger = logging.getLogger(__name__)


def _sse(event: str, data: dict[str, Any]) -> bytes:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n".encode(
        "utf-8"
    )


def _stream_answer(question: str) -> Iterator[bytes]:
    """Stream a DeepSeek answer as SSE ``delta`` events.

    Falls back to a stub echo if the LLM client isn't configured — keeps
    the frontend usable in dev without requiring a DEEPSEEK_API_KEY.
    """
    from merism.memai.llm import get_llm, default_model

    try:
        client = get_llm()
        model = default_model()
    except Exception as exc:
        logger.warning("ask.client_init_failed", extra={"err": str(exc)})
        yield _sse("delta", {"partial": "(LLM client not configured in this env.)"})
        yield _sse(
            "done",
            {
                "answer_markdown": "(LLM client not configured in this env.)",
                "chart": None,
                "citations": [],
            },
        )
        return

    try:
        stream = client.chat.completions.create(
            model=model,
            stream=True,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are Merism, a qualitative-research assistant. "
                        "Answer the user's question clearly in markdown. "
                        "Keep answers grounded; if you don't know, say so."
                    ),
                },
                {"role": "user", "content": question},
            ],
            max_tokens=800,
            temperature=0.3,
        )
    except Exception as exc:
        logger.exception("ask.request_failed")
        yield _sse("delta", {"partial": f"Error reaching LLM: {exc}"})
        yield _sse(
            "done",
            {
                "answer_markdown": f"Error reaching LLM: {exc}",
                "chart": None,
                "citations": [],
            },
        )
        return

    accum = []
    try:
        for chunk in stream:
            delta = chunk.choices[0].delta.content if chunk.choices else None
            if delta:
                accum.append(delta)
                yield _sse("delta", {"partial": "".join(accum)})
    except Exception as exc:
        logger.exception("ask.stream_failed")

    answer = "".join(accum) or "(empty response)"
    yield _sse("done", {"answer_markdown": answer, "chart": None, "citations": []})


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

    response = StreamingHttpResponse(
        _stream_answer(question),
        content_type="text/event-stream",
    )
    response["Cache-Control"] = "no-cache"
    response["X-Accel-Buffering"] = "no"
    return response


@csrf_exempt
@login_required
@require_http_methods(["POST"])
def knowledge_search(request: HttpRequest) -> JsonResponse:
    """Stub — hybrid search lands with the Repository tab build-out."""
    try:
        body = json.loads(request.body or b"{}")
    except Exception:
        body = {}
    query = (body.get("query") or "").strip()
    return JsonResponse(
        {
            "query": query,
            "results": [],
            "status": "not_implemented",
            "note": "Hybrid (BM25 + dense + reranker) search lands with Repository tab.",
        }
    )
