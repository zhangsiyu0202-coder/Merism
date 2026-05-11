"""Transcript cleaning pipeline — multi-stage quality refinement.

Stage order (each optional, each independent):

1. ``stage1_asr_correct`` — ASR nearest-neighbor fixes using a glossary
   (product names, proper nouns).
2. ``stage2_speaker_fix`` — future; speaker diarization overlap fixes.
3. ``stage3_normalize``   — zh/en mixed text, numbers, dates → canonical.
4. ``stage4_fillers``     — regex-based filler removal (delegates to
   existing ``merism.conductor.rule_clean``).
5. ``stage5_grammar``     — batched LLM grammar polish (delegates to
   existing ``merism.conductor.llm_polish``).
6. ``stage6_merge``       — optional semantic merge of fragmented utterances.

The pipeline is orchestrated in ``merism.cleaning.pipeline``. Each stage
is a plain function ``stage(turns, context) -> turns`` so we can
swap/skip stages per study.
"""
