import { actions, kea, listeners, path, reducers } from "kea";

import type {
  InterviewMode,
  InterviewTurn,
  LocalAttachment,
  SessionStatus,
  Stimulus,
} from "./types";
import type { interviewRoomLogicType } from "./interviewRoomLogicType";

/**
 * interviewRoomLogic — participant-facing interview session state.
 *
 * Owns everything a participant in the room cares about:
 *   - mode selection (voice / video) before the session starts
 *   - session start (POST /api/sessions/ for the current participation)
 *   - SSE event stream (turn / phase_change / done)
 *   - local transcript buffer (rendered in the right column)
 *   - **attachments** the participant uploads from the right column
 *     (images / videos / PDFs) — stored locally first, backend upload
 *     is a later phase
 *   - **activeStimulus** — which stimulus is overlaid on the preview;
 *     can be pushed by the server (via a turn carrying ``stimulus_id``)
 *     or toggled locally by the close-X button
 *   - **previewMode** — toggled on by ``?preview=1`` in the URL;
 *     surfaces an orange "自测模式" badge in the bottom-right corner
 *
 * PRODUCT.md §2.2 flow:
 *   open link → consent → screener → preparation → room
 * The consent / screener / preparation steps live in sibling logics;
 * this logic only covers "in the room".
 */
export const interviewRoomLogic = kea<interviewRoomLogicType>([
  path(["scenes", "interview_room", "interviewRoomLogic"]),

  actions({
    selectMode: (mode: InterviewMode) => ({ mode }),
    startSession: true,
    setSessionId: (sessionId: string) => ({ sessionId }),
    appendTurn: (turn: InterviewTurn) => ({ turn }),
    setPhase: (phase: SessionStatus) => ({ phase }),
    setError: (error: string | null) => ({ error }),
    setPreviewMode: (enabled: boolean) => ({ enabled }),
    attachFile: (file: File) => ({ file }),
    removeAttachment: (id: string) => ({ id }),
    showStimulus: (stimulus: Stimulus) => ({ stimulus }),
    hideStimulus: true,
    clear: true,
  }),

  reducers({
    mode: [
      "voice" as InterviewMode,
      {
        selectMode: (_, { mode }) => mode,
      },
    ],
    sessionId: [
      null as string | null,
      {
        setSessionId: (_, { sessionId }) => sessionId,
        clear: () => null,
      },
    ],
    turns: [
      [] as InterviewTurn[],
      {
        appendTurn: (state, { turn }) => [...state, turn],
        clear: () => [],
      },
    ],
    phase: [
      "pending" as SessionStatus,
      {
        setPhase: (_, { phase }) => phase,
        clear: () => "pending",
      },
    ],
    error: [
      null as string | null,
      {
        setError: (_, { error }) => error,
        clear: () => null,
      },
    ],
    previewMode: [
      false,
      {
        setPreviewMode: (_, { enabled }) => enabled,
      },
    ],
    attachments: [
      [] as LocalAttachment[],
      {
        attachFile: (state, { file }) => [
          ...state,
          {
            id: `att_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`,
            file,
            kind: classify(file),
            previewUrl: URL.createObjectURL(file),
            createdAt: Date.now(),
          },
        ],
        removeAttachment: (state, { id }) => {
          const removed = state.find((a) => a.id === id);
          if (removed) URL.revokeObjectURL(removed.previewUrl);
          return state.filter((a) => a.id !== id);
        },
        clear: (state) => {
          for (const a of state) URL.revokeObjectURL(a.previewUrl);
          return [];
        },
      },
    ],
    activeStimulus: [
      null as Stimulus | null,
      {
        showStimulus: (_, { stimulus }) => stimulus,
        hideStimulus: () => null,
        clear: () => null,
      },
    ],
  }),

  listeners(({ actions: a }) => ({
    startSession: async () => {
      // Participants arrive at /interview/:sessionId after the
      // /i/:slug flow already created the InterviewSession
      // (see merism/participant/views.py::start_session). We just
      // pick up the session_id from the URL and attach the SSE stream.
      try {
        const match = window.location.pathname.match(
          /^\/interview\/([a-f0-9-]+)/i,
        );
        const sessionId = match?.[1];
        if (!sessionId) {
          throw new Error("No session id in URL — restart from /i/:slug.");
        }
        a.setSessionId(sessionId);
        a.setPhase("active");
        consumeSessionStream(sessionId, a);
      } catch (err) {
        a.setError(
          err instanceof Error ? err.message : "Could not start session.",
        );
      }
    },
  })),
]);

function classify(file: File): "image" | "video" | "pdf" | "other" {
  if (file.type.startsWith("image/")) return "image";
  if (file.type.startsWith("video/")) return "video";
  if (file.type === "application/pdf") return "pdf";
  return "other";
}

async function consumeSessionStream(
  sessionId: string,
  a: {
    appendTurn: (turn: InterviewTurn) => void;
    setPhase: (phase: SessionStatus) => void;
    setError: (error: string | null) => void;
  },
): Promise<void> {
  try {
    const response = await fetch(`/api/sessions/${sessionId}/stream/`);
    if (!response.body) throw new Error("No SSE body");

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });

      const events = buffer.split("\n\n");
      buffer = events.pop() ?? "";

      for (const raw of events) {
        const parsed = parseSSEBlock(raw);
        if (!parsed) continue;
        if (parsed.event === "turn") {
          a.appendTurn(parsed.data as unknown as InterviewTurn);
        } else if (parsed.event === "phase_change") {
          const phase =
            (parsed.data.phase as SessionStatus | undefined) ?? "active";
          a.setPhase(phase);
        } else if (parsed.event === "error") {
          a.setError(String(parsed.data.message ?? "Unknown stream error"));
        }
      }
    }
  } catch (err) {
    a.setError(err instanceof Error ? err.message : "Stream disconnected");
  }
}

interface ParsedSSE {
  event: string;
  data: Record<string, unknown>;
}

function parseSSEBlock(raw: string): ParsedSSE | null {
  let event = "message";
  let data = "";
  for (const line of raw.split("\n")) {
    if (line.startsWith("event:")) event = line.slice(6).trim();
    else if (line.startsWith("data:")) data += line.slice(5).trim();
  }
  if (!data) return null;
  try {
    return { event, data: JSON.parse(data) };
  } catch {
    return null;
  }
}
