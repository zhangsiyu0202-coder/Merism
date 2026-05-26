"""验证 post_session 清洗管线吃 v3 transcript 形状不炸.

走通: v3 graph 跑完 → finalize_to_session 写 transcript →
process_session_transcripts 清洗 → SessionInsight 生成.
"""

from __future__ import annotations

import asyncio
import os
import sys
import time
import uuid

sys.path.insert(0, "/home/jia/merism-app")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "merism.settings.dev")

import django
django.setup()

from dotenv import load_dotenv
load_dotenv("/home/jia/merism-app/.env")


async def main() -> None:
    from django.contrib.auth import get_user_model
    from langgraph.checkpoint.memory import InMemorySaver
    from merism.conductor.transcript_helpers import has_clean_transcript
    from merism.conductor.graph import build_graph
    from merism.conductor.persistence import finalize_to_session
    from merism.conductor.runner import (
        answer_interview,
        get_interrupt_payload,
        start_interview,
    )
    from merism.conductor.schema import Outline, Question, Section
    from merism.models import (
        InterviewGuide,
        InterviewSession,
        Organization,
        Participant,
        Participation,
        Study,
        Team,
    )

    User = get_user_model()
    suffix = uuid.uuid4().hex[:8]
    print(f"=== Setup test session (suffix={suffix}) ===")

    from asgiref.sync import sync_to_async

    def _setup():
        admin = User.objects.create_superuser(
            username=f"v3-postsess-{suffix}@merism.test",
            email=f"v3-postsess-{suffix}@merism.test",
            password="x",
        )
        org = Organization.objects.create(name=f"PostSess {suffix}", slug=f"postsess-{suffix}")
        team = Team.objects.create(name="R", organization=org)
        study = Study.objects.create(
            team=team,
            created_by=admin,
            name="V3 post_session test",
            research_goal="验证 v3 transcript 兼容现有清洗管线",
            interview_mode=Study.InterviewMode.TEXT,
            estimated_minutes=10,
        )
        guide = InterviewGuide.objects.create(
            team=team,
            study=study,
            version="3.0.0",
            is_current=True,
            sections={"version": "v3", "sections": []},
        )
        participant = Participant.objects.create(team=team, external_id=f"v3p-{suffix}", name="V3 Tester")
        participation = Participation.objects.create(team=team, study=study, participant=participant)
        session = InterviewSession.objects.create(
            team=team,
            study=study,
            guide=guide,
            participation=participation,
            status=InterviewSession.Status.ACTIVE,
            mode=InterviewSession.Mode.TEXT,
        )
        return session

    session = await sync_to_async(_setup)()
    print(f"  session id={session.id}")

    # ── Run a small v3 interview ──
    print("\n=== Run v3 interview (3 questions, off mode) ===")
    outline = Outline(
        sections=[
            Section(
                id="background",
                title="背景",
                questions=[
                    Question(id="role", ask="你是做什么工作的?", follow_up_mode="off"),
                    Question(id="problem", ask="工作中最头疼什么?", follow_up_mode="off"),
                    Question(id="wishlist", ask="希望什么改进?", follow_up_mode="off"),
                ],
            ),
        ],
    )

    graph = build_graph(checkpointer=InMemorySaver())
    thread_id = str(session.id)
    result = await sync_to_async(start_interview)(
        graph, outline=outline, thread_id=thread_id, follow_up_mode="off"
    )

    answers = ["产品经理", "需求频繁变更", "希望能预测风险"]
    for ans in answers:
        payload = get_interrupt_payload(result)
        if payload is None:
            break
        print(f"  AI: {payload['question']}")
        print(f"  USER: {ans}")
        result = await sync_to_async(answer_interview)(graph, user_answer=ans, thread_id=thread_id)

    print(f"\n  graph done={result.get('done')}, transcript turns={len(result.get('transcript', []))}")

    # ── Finalize to session ──
    print("\n=== Finalize → InterviewSession.transcript ===")
    ok = await finalize_to_session(graph, thread_id)
    print(f"  finalize ok={ok}")

    await sync_to_async(session.refresh_from_db)()
    print(f"  session.status={session.status}")
    print(f"  session.transcript len={len(session.transcript)} (v1-compat 应为 v3 turns × 2)")
    print(f"  session.transcript[0]={session.transcript[0] if session.transcript else None}")
    print(f"  session.moderator_state.engine={session.moderator_state.get('engine')}")
    print(f"  session.moderator_state.v3_transcript len={len(session.moderator_state.get('v3_transcript', []))}")

    # ── Verify v1 helpers don't choke ──
    print("\n=== v1 helpers 兼容性 ===")
    # has_clean_transcript expects each turn to have role + text_clean
    print(f"  has_clean_transcript: {has_clean_transcript(session.transcript)}")
    print("    (False = transcript 还没 polished, 这是正常状态)")

    # ── Run post_session pipeline ──
    print("\n=== 跑 post_session.process_session_transcripts ===")
    from merism.conductor.post_session import process_session_transcripts

    t0 = time.time()
    try:
        result = await process_session_transcripts(session.id)
        elapsed = time.time() - t0
        print(f"  ✅ 跑通, {elapsed:.1f}s, 返回: {result}")
    except Exception as exc:
        elapsed = time.time() - t0
        print(f"  ❌ 失败 ({elapsed:.1f}s): {type(exc).__name__}: {exc}")
        import traceback
        traceback.print_exc()
        return

    # ── Inspect cleaned transcript ──
    await sync_to_async(session.refresh_from_db)()
    print(f"\n=== 清洗后 ===")
    cleaned_count = sum(1 for t in session.transcript if t.get("text_clean"))
    print(f"  transcript turns = {len(session.transcript)}")
    print(f"  其中带 text_clean = {cleaned_count}")
    print(f"  has_clean_transcript: {has_clean_transcript(session.transcript)}")

    # ── Check SessionInsight generated ──
    from merism.models import SessionInsight
    insights = await sync_to_async(lambda: list(SessionInsight.objects.filter(session=session)))()
    print(f"\n=== SessionInsight ===")
    print(f"  生成数量: {len(insights)}")
    for ins in insights:
        print(f"    - {ins.kind}: {ins.title or '(no title)'}")


if __name__ == "__main__":
    asyncio.run(main())
