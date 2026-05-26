import { actions, kea, listeners, path, reducers } from "kea";

import type {
  AskMerismChart as CustomReportChart,
  AskMerismCitation as CustomReportCitation,
} from "~/features/ask";

import type { customReportLogicType } from "./customReportLogicType";

/**
 * customReportLogic — Analysis tab sidebar.
 *
 * Scoped to one study (unlike Ask Merism which is cross-study). POSTs to
 * /api/custom-report-queries/ which creates the record synchronously then
 * streams the answer via SSE to /api/custom-report-queries/<id>/stream/.
 *
 * Shape mirrors the Ask Merism answer because they share the Pydantic
 * CustomReportAnswer schema on the server — we only import the types.
 */

export interface CustomReportMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  streaming?: boolean;
  chart?: CustomReportChart;
  citations?: CustomReportCitation[];
  errored?: boolean;
  pinned?: boolean;
}

export const customReportLogic = kea<customReportLogicType>([
  path(["scenes", "custom_report", "customReportLogic"]),

  actions({
    openFor: (studyId: string) => ({ studyId }),
    close: true,
    askQuestion: (question: string) => ({ question }),
    pushMessage: (message: CustomReportMessage) => ({ message }),
    updateMessage: (id: string, patch: Partial<CustomReportMessage>) => ({
      id,
      patch,
    }),
    setSending: (sending: boolean) => ({ sending }),
    togglePin: (id: string) => ({ id }),
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
    messages: [
      [] as CustomReportMessage[],
      {
        pushMessage: (state, { message }) => [...state, message],
        updateMessage: (state, { id, patch }) =>
          state.map((m) => (m.id === id ? { ...m, ...patch } : m)),
        togglePin: (state, { id }) =>
          state.map((m) => (m.id === id ? { ...m, pinned: !m.pinned } : m)),
        openFor: () => [],
      },
    ],
    isSending: [
      false,
      {
        setSending: (_, { sending }) => sending,
      },
    ],
  }),

  listeners(({ actions: a, values }) => ({
    askQuestion: async ({ question }) => {
      if (values.isSending || !values.studyId) return;

      const userId = crypto.randomUUID();
      const assistantId = crypto.randomUUID();
      a.pushMessage({ id: userId, role: "user", content: question });
      a.pushMessage({
        id: assistantId,
        role: "assistant",
        content: "",
        streaming: true,
      });
      a.setSending(true);

      try {
        const response = await fetch("/api/custom-report-queries/", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            study: values.studyId,
            question,
          }),
        });
        if (!response.ok) {
          throw new Error(`Custom report failed: ${response.status}`);
        }
        const data = (await response.json()) as {
          answer_markdown?: string;
          chart?: CustomReportChart | null;
          citations?: CustomReportCitation[];
        };
        a.updateMessage(assistantId, {
          content: data.answer_markdown ?? "",
          chart: data.chart ?? undefined,
          citations: data.citations ?? [],
          streaming: false,
        });
      } catch (err) {
        a.updateMessage(assistantId, {
          content: err instanceof Error ? err.message : "Something went wrong.",
          streaming: false,
          errored: true,
        });
      } finally {
        a.setSending(false);
      }
    },
  })),
]);
