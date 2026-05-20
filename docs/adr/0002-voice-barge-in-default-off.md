# ADR 0002 — Voice barge-in: default off, per-study flag

**Status:** Accepted (2026-05-10)
**Deciders:** Jia
**Supersedes:** nothing
**Superseded by:** nothing

## Context

Merism runs AI-moderated voice interviews. In voice UX design, "barge-in"
means a user can interrupt the AI while it's speaking — the system stops
TTS playback, starts STT, and the agent takes the interruption as the next
turn.

Every modern voice AI (Deepgram, ElevenLabs Conversational AI, OpenAI
Realtime, Google Gemini Live) ships with barge-in on by default. Should
Merism?

## Decision

**Barge-in is disabled by default, but the protocol and model fully
support it.** Researchers enable it per-study via `Study.barge_in_enabled`.

## Why not default on

1. **Interview data quality.** Qualitative research interviews live or
   die on answer depth. In default-on voice agents, participants tend to
   interrupt the AI reactively, which produces shallow, choppy answers —
   exactly what Merism is built NOT to collect.
2. **Moderator contract.** PRODUCT.md §5.2 makes the moderator a
   2-node (decide → generate) per-turn pipeline. A "turn" is the
   participant's complete answer followed by the AI's complete next
   question. Barge-in breaks this — the LLM has to decide what to do
   with a half-delivered question, which complicates `next_action` logic
   and `remaining_followups`
   accounting.
3. **Participant mental model.** Turn-taking gives participants a clear
   contract: "the AI finishes, then I speak." It reduces freezing (people
   unsure if they may interrupt) and over-talking (people who interrupt
   every sentence). A human moderator's silence after a question is a
   powerful cue — barge-in removes that.
4. **Pilots first, decisions later.** We need real participant data to
   decide whether barge-in helps or hurts answer depth. Default-off gives
   us a control group.

## Why not default off and ban it forever

1. **UX research.** Some studies investigate conversational AI itself.
   Those studies legitimately want barge-in on to study how participants
   interrupt agents.
2. **Accessibility.** Some participants with speech or cognitive
   differences benefit from barge-in (they can redirect an AI that's
   going the wrong way without waiting for a polite handoff).
3. **Future-proofing.** Building the protocol without barge-in support
   would be a migration tax later.

## Implementation contract

### Data model

`Study.barge_in_enabled: bool = False` — set by researcher in Settings tab.

### WebSocket protocol (client ↔ server)

Client sends voice-activity events **always**:

```json
{ "type": "vad_speaking_start", "ts": 1.234 }
{ "type": "vad_speaking_end",   "ts": 1.890 }
```

Server reacts based on `session.study.barge_in_enabled`:

- **False** (default): VAD events are logged but **do not** interrupt
  the active TTS stream. The AI finishes what it's saying. User audio
  that arrives during AI speech is still streamed to Paraformer; the
  STT output is queued and fed into the moderator call AFTER the AI
  finishes.
- **True**: on `vad_speaking_start`, the server cancels the active TTS
  task and the active moderator stream (if any). The current turn is
  marked `interrupted: true` in `moderator_state` so the next
  moderator call sees the context.

### UI contract

- Default-off studies: the Interview Room shows a "your turn" indicator
  after AI finishes. This prevents ambiguity.
- Barge-in-on studies: the UI shows a subtle `🎙 interrupt ok` badge so
  participants know they may interrupt.

## Consequences

### Positive

- Clean research data by default. MVP researchers don't get a surprise
  "why are answers so short?" problem.
- Protocol and model allow flipping on without rework.
- One ADR captures the reasoning; nobody has to re-debate this.

### Negative

- First iteration of voice UX feels less "natural" than default-on
  competitors. Justified by research-quality ADR; document for participants
  in the Consent page ("the AI will speak without interruption; please
  wait for your turn").
- Extra flag surface in Study Settings. One checkbox + tooltip.

### Neutral

- Server-side barge-in logic (task cancellation + interrupt marker)
  must be written even though it's default-off. Necessary so the flip
  is instant per-study.

## Revisit conditions

- 100+ real interviews completed with default-off voice mode. If the
  data shows participants routinely interrupt despite the UI cue, and
  the resulting interruptions degrade quality, this ADR may stay.
- If researchers consistently enable `barge_in_enabled` and data
  quality metrics hold, consider flipping the default.
