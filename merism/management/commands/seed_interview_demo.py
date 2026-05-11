"""Create a fresh voice-ready InterviewSession for manual PTT testing.

Usage::

    python manage.py seed_interview_demo

Prints the session URL so you can paste it into the browser. Safe to
re-run — every call produces a new session.
"""

from __future__ import annotations

from uuid import uuid4

from django.core.management.base import BaseCommand

from merism.models.interview import (
    InterviewGuide,
    InterviewSession,
    Participant,
    Participation,
)
from merism.models.study import Study


class Command(BaseCommand):
    help = "Create a voice-ready InterviewSession + print the test URL."

    def handle(self, *args: object, **options: object) -> None:
        study = Study.objects.first()
        if study is None:
            self.stderr.write(
                self.style.ERROR(
                    "No study found. Run `make seed` first to create the demo team + studies."
                )
            )
            return

        team = study.team

        guide, _ = InterviewGuide.objects.get_or_create(
            study=study,
            is_current=True,
            defaults={
                "team": team,
                "language": "zh",
                "sections": [
                    {
                        "id": "warmup",
                        "title": "热身",
                        "questions": [
                            {
                                "id": "q1",
                                "text": "你好！先简单自我介绍一下吧。",
                                "type": "open",
                            }
                        ],
                    },
                    {
                        "id": "core",
                        "title": "主访",
                        "questions": [
                            {
                                "id": "q2",
                                "text": "聊聊你最近一次用 AI 助手完成工作的经历。",
                                "type": "open",
                            }
                        ],
                    },
                ],
            },
        )

        participant = Participant.objects.create(
            team=team,
            email=f"demo-{uuid4().hex[:8]}@merism.test",
            name="Demo Participant",
        )
        participation = Participation.objects.create(
            team=team,
            study=study,
            participant=participant,
            browser_token=uuid4(),
        )
        session = InterviewSession.objects.create(
            team=team,
            study=study,
            participation=participation,
            guide=guide,
            mode="voice",
            status="pending",
        )

        self.stdout.write(self.style.SUCCESS("\n  Interview session ready.\n"))
        self.stdout.write(f"    Session ID:   {session.id}")
        self.stdout.write(f"    Study:        {study.name}  (team: {team.name})")
        self.stdout.write(f"    Frontend URL: http://localhost:5173/interview/{session.id}")
        self.stdout.write(
            f"    WS endpoint:  ws://localhost:8000/ws/sessions/{session.id}/voice/"
        )
        self.stdout.write(
            "\n  Tip: the browser will prompt for mic permission. Press Space or the"
        )
        self.stdout.write("       PTT button at the bottom of the live room to talk.\n")
