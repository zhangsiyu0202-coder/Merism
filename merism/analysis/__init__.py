"""Cross-session pattern analysis.

Three capabilities:

1. ``themes/`` — cluster quotes across sessions to surface recurring
   ideas that no single session reveals.
2. ``coverage/`` — measure how well each StudyGoal has been answered
   by completed sessions; detect gaps.
3. ``cohort/`` — define participation subsets for A/B theme comparison.

Everything runs **after** quotes have been extracted by the existing
:mod:`merism.memai.agents.quote_extractor`. The analysis layer is a
read-only consumer of ``SessionQuote`` rows.
"""
