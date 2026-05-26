import { actions, kea, listeners, path, reducers } from "kea";

import type { textInterviewLogicType } from "./textInterviewLogicType";

/**
 * textInterviewLogic — drives the ``/interview/:sessionId`` page for
 * ``study.interview_mode == "text"`` studies.
 *
 * Wire format: the backend SSE stream sends ``event: delta`` with a
 * monotonically growing ``partial`` string, and a final ``event: done``
 * with the full ``assistant_text`` + structured ``decision``.
 *
 * The logic swallows the session-cookie auth (``/api/sessions/:id/message/``
 * identifies the participant by the browser_token cookie set by
 * ``/i/:slug/``) so nothing extra is passed from the page.
 */

export interface TextTurn {
  role: "user" | "assistant";
  text: string;
  streaming?: boolean;
}

export const textInterviewLogic = kea<textInterviewLogicType>([
  path(["features", "interview", "textInterviewLogic"]),
  actions({
    setSessionId: (sessionId: string) => ({ sessionId }),
    bootstrapFromUrl: true,
    setDraft: (draft: string) => ({ draft }),
    sendMessage: true,
    appendUserTurn: (text: string) => ({ text }),
    updateStreamingAssistant: (partial: string) => ({ partial }),
    finalizeAssistant: (finalText: string, sessionStatus: string) => ({
      finalText,
      sessionStatus,
    }),
    setError: (error: string | null) => ({ error }),
    setSending: (isSending: boolean) => ({ isSending }),
    setCompleted: (isCompleted: boolean) => ({ isCompleted }),
  }),
  reducers({
    sessionId: [
      "" as string,
      { setSessionId: (_, { sessionId }) => sessionId },
    ],
    turns: [
      [] as TextTurn[],
      {
        appendUserTurn: (state, { text }) => [
          ...state,
          { role: "user", text },
          { role: "assistant", text: "", streaming: true },
        ],
        updateStreamingAssistant: (state, { partial }) => {
          if (state.length === 0) return state;
          const copy = [...state];
          const last = copy[copy.length - 1];
          if (last && last.role === "assistant" && last.streaming) {
            copy[copy.length - 1] = { ...last, text: partial };
          }
          return copy;
        },
        finalizeAssistant: (state, { finalText }) => {
          if (state.length === 0) return state;
          const copy = [...state];
          const last = copy[copy.length - 1];
          if (last && last.role === "assistant" && last.streaming) {
            copy[copy.length - 1] = { role: "assistant", text: finalText };
          }
          return copy;
        },
      },
    ],
    draft: [
      "" as string,
      {
        setDraft: (_, { draft }) => draft,
        sendMessage: () => "",
      },
    ],
    isSending: [
      false,
      {
        setSending: (_, { isSending }) => isSending,
      },
    ],
    error: [
      null as string | null,
      {
        setError: (_, { error }) => error,
      },
    ],
    isCompleted: [
      false,
      {
        setCompleted: (_, { isCompleted }) => isCompleted,
      },
    ],
  }),
  listeners(({ actions, values }) => ({
    bootstrapFromUrl: () => {
      const match = window.location.pathname.match(
        /^\/interview\/([a-f0-9-]+)/i,
      );
      const sid = match?.[1];
      if (sid) actions.setSessionId(sid);
    },
    sendMessage: async () => {
      const text = values.draft.trim();
      if (!text) return;
      actions.appendUserTurn(text);
      actions.setSending(true);
      try {
        const response = await fetch(
          `/api/sessions/${values.sessionId}/message/`,
          {
            method: "POST",
            credentials: "include",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ message: text }),
          },
        );
        if (!response.ok || !response.body) {
          throw new Error(`HTTP ${response.status}`);
        }
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buf = "";
        // eslint-disable-next-line no-constant-condition
        while (true) {
          const { value, done } = await reader.read();
          if (done) break;
          buf += decoder.decode(value, { stream: true });
          let separatorIdx = buf.indexOf("\n\n");
          while (separatorIdx !== -1) {
            const block = buf.slice(0, separatorIdx);
            buf = buf.slice(separatorIdx + 2);
            const parsed = _parseSSE(block);
            if (parsed) _handleEvent(parsed, actions);
            separatorIdx = buf.indexOf("\n\n");
          }
        }
      } catch (err) {
        actions.setError(err instanceof Error ? err.message : "send failed");
        actions.finalizeAssistant("(couldn't reach the server)", "errored");
      } finally {
        actions.setSending(false);
      }
    },
  })),
]);

function _parseSSE(
  block: string,
): { event: string; data: Record<string, unknown> } | null {
  const lines = block.split("\n");
  let ev = "message";
  let data = "";
  for (const line of lines) {
    if (line.startsWith("event:")) ev = line.slice(6).trim();
    else if (line.startsWith("data:")) data += line.slice(5).trim();
  }
  if (!data) return null;
  try {
    return { event: ev, data: JSON.parse(data) as Record<string, unknown> };
  } catch {
    return null;
  }
}

function _handleEvent(
  ev: { event: string; data: Record<string, unknown> },
  actions: {
    updateStreamingAssistant: (partial: string) => void;
    finalizeAssistant: (finalText: string, sessionStatus: string) => void;
    setError: (error: string | null) => void;
    setCompleted: (isCompleted: boolean) => void;
  },
): void {
  if (ev.event === "delta") {
    actions.updateStreamingAssistant(String(ev.data.partial ?? ""));
  } else if (ev.event === "done") {
    const finalText = String(ev.data.assistant_text ?? "");
    const sessionStatus = String(ev.data.session_status ?? "");
    actions.finalizeAssistant(finalText, sessionStatus);
    if (sessionStatus === "completed") actions.setCompleted(true);
  } else if (ev.event === "error") {
    actions.setError(String(ev.data.message ?? "stream error"));
  }
}
