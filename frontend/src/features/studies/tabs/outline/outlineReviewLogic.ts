import { actions, kea, listeners, path, reducers } from "kea";

import type {
  OutlineOp,
  OutlineReviewChatMessage,
  OutlineReviewResponse,
  OutlineSection,
} from "./types";
import type { outlineReviewLogicType } from "./outlineReviewLogicType";

/**
 * outlineReviewLogic — owns the Outline Review sidebar conversation.
 *
 * Posts researcher messages to /api/studies/<id>/review-outline/ and
 * appends the LLM's reply + proposed_changes to the transcript. Applying
 * a proposed change is a separate backend call
 * (/api/guides/<id>/apply-proposed-changes/) owned by the Outline tab —
 * this logic only tracks state, never mutates the guide.
 */
export const outlineReviewLogic = kea<outlineReviewLogicType>([
  path(["scenes", "outline_review", "outlineReviewLogic"]),

  actions({
    openFor: (studyId: string, initialSections: OutlineSection[]) => ({
      studyId,
      initialSections,
    }),
    close: true,
    send: (text: string) => ({ text }),
    pushMessage: (message: OutlineReviewChatMessage) => ({ message }),
    markApplied: (messageId: string) => ({ messageId }),
    setSending: (sending: boolean) => ({ sending }),
    setError: (error: string | null) => ({ error }),
  }),

  reducers({
    open: [
      false,
      {
        openFor: () => true,
        close: () => false,
      },
    ],
    studyId: [
      null as string | null,
      {
        openFor: (_, { studyId }) => studyId,
        close: () => null,
      },
    ],
    sections: [
      [] as OutlineSection[],
      {
        openFor: (_, { initialSections }) => initialSections,
      },
    ],
    messages: [
      [] as OutlineReviewChatMessage[],
      {
        pushMessage: (state, { message }) => [...state, message],
        markApplied: (state, { messageId }) =>
          state.map((m) =>
            m.id === messageId ? { ...m, proposed_changes: [] } : m,
          ),
        openFor: () => [],
      },
    ],
    isSending: [
      false,
      {
        setSending: (_, { sending }) => sending,
      },
    ],
    error: [
      null as string | null,
      {
        setError: (_, { error }) => error,
      },
    ],
  }),

  listeners(({ actions: a, values }) => ({
    send: async ({ text }) => {
      if (values.isSending || !values.studyId) return;
      const trimmed = text.trim();
      if (!trimmed) return;

      a.pushMessage({
        id: crypto.randomUUID(),
        role: "researcher",
        text: trimmed,
      });
      a.setSending(true);

      try {
        const response = await fetch(
          `/api/studies/${values.studyId}/review-outline/`,
          {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              message: trimmed,
              sections: values.sections,
              chat_history: values.messages.map((m) => ({
                role: m.role === "researcher" ? "user" : "assistant",
                content: m.text,
              })),
            }),
          },
        );
        if (!response.ok) {
          throw new Error(`Review request failed: ${response.status}`);
        }
        const data: OutlineReviewResponse = await response.json();
        a.pushMessage({
          id: crypto.randomUUID(),
          role: "assistant",
          text: data.reply_markdown,
          proposed_changes: data.proposed_changes,
        });
      } catch (err) {
        a.setError(err instanceof Error ? err.message : "Review failed.");
        a.pushMessage({
          id: crypto.randomUUID(),
          role: "assistant",
          text: "I couldn't complete the review. Please try again.",
        });
      } finally {
        a.setSending(false);
      }
    },
  })),
]);

export type { OutlineOp, OutlineReviewChatMessage, OutlineSection };
