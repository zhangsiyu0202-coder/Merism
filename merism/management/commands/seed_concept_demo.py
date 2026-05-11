"""Seed a concept-testing demo study + session URL for manual PTT smoke.

Creates:
- One Study ("Concept Testing Demo").
- Three Stimulus rows (simple link-kind stand-ins).
- One ConceptBlock with three Concepts, ``random_per_session`` rotation.
- One InterviewGuide whose sections exercise every scope:
    global warmup → per_concept reactions → comparative closing.
- One Participant + Participation + voice InterviewSession, ready to
  connect at ``/interview/:id``.

Usage::

    python manage.py seed_concept_demo
"""

from __future__ import annotations

from uuid import uuid4

from django.core.management.base import BaseCommand

from merism.models.concept import Concept, ConceptBlock
from merism.models.interview import (
    InterviewGuide,
    InterviewSession,
    Participant,
    Participation,
)
from merism.models.stimulus import Stimulus
from merism.models.study import Study


class Command(BaseCommand):
    help = "Create a ConceptBlock-enabled study + session for manual testing."

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

        # 1. Three stimuli — use link kind so we don't need uploaded assets.
        stimuli: list[Stimulus] = []
        for i, (title, url) in enumerate(
            [
                ("Concept A · 可持续设计", "https://picsum.photos/seed/conceptA/640/360"),
                ("Concept B · 尖端科技", "https://picsum.photos/seed/conceptB/640/360"),
                ("Concept C · 怀旧配色", "https://picsum.photos/seed/conceptC/640/360"),
            ]
        ):
            s = Stimulus.objects.create(
                team=team,
                study=study,
                kind=Stimulus.Kind.IMAGE,
                title=title,
                description=f"Demo stimulus {i + 1}",
                content={"url": url},
            )
            stimuli.append(s)

        # 2. Concept block + three concepts.
        block = ConceptBlock.objects.create(
            team=team,
            study=study,
            title="Package designs",
            description="Participants compare three draft package designs.",
            rotation=ConceptBlock.Rotation.RANDOM,
        )
        concepts: list[Concept] = []
        for i, s in enumerate(stimuli):
            c = Concept.objects.create(
                block=block,
                stimulus=s,
                label=f"Concept {chr(ord('A') + i)}",
                rank=i,
                notes=f"Design {i + 1}: {s.title.split(' · ')[-1]}.",
            )
            concepts.append(c)

        # 3. Guide: warmup (global) → reactions (per_concept) → close (comparative).
        # Previous guide versions may exist from earlier seed runs; mark
        # them inactive + bump version for deterministic re-runs.
        InterviewGuide.objects.filter(study=study).update(is_current=False)
        guide = InterviewGuide.objects.create(
            team=team,
            study=study,
            version=f"demo-{uuid4().hex[:6]}",
            language="zh",
            is_current=True,
            sections=[
                {
                    "id": "warmup",
                    "title": "热身",
                    "scope": "global",
                    "questions": [
                        {
                            "id": "q_intro",
                            "text": "你好！简单说说你平时怎么挑选零食包装。",
                            "followup_depth": 1,
                        }
                    ],
                },
                {
                    "id": "reactions",
                    "title": "概念反应",
                    "scope": "per_concept",
                    "concept_block_id": str(block.id),
                    "questions": [
                        {
                            "id": "q_first",
                            "text": "看到这个包装的第一感受是什么？",
                            "followup_depth": 1,
                        },
                        {
                            "id": "q_intent",
                            "text": "如果在货架上看到，你会拿起来看吗？为什么？",
                            "followup_depth": 1,
                        },
                    ],
                },
                {
                    "id": "closing",
                    "title": "对比",
                    "scope": "comparative",
                    "questions": [
                        {
                            "id": "q_winner",
                            "text": "刚才三款你最喜欢哪一款？为什么？",
                            "followup_depth": 2,
                        }
                    ],
                },
            ],
        )

        # 4. Participant + session.
        participant = Participant.objects.create(
            team=team,
            email=f"concept-demo-{uuid4().hex[:8]}@merism.test",
            name="Concept Demo Participant",
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

        self.stdout.write(self.style.SUCCESS("\n  Concept-testing session ready.\n"))
        self.stdout.write(f"    Study:        {study.name}  (team: {team.name})")
        self.stdout.write(f"    Block:        {block.title}  ({block.rotation})")
        self.stdout.write(
            f"    Concepts:     {', '.join(c.label for c in concepts)}"
        )
        self.stdout.write(f"    Session ID:   {session.id}")
        self.stdout.write(
            f"    Participant URL: http://localhost:5180/interview/{session.id}"
        )
        self.stdout.write(
            f"    Study UI:     http://localhost:5180/studies/{study.id}/stimuli"
        )
