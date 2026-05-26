import {
  actions,
  afterMount,
  kea,
  listeners,
  path,
  reducers,
  selectors,
} from "kea";
import { loaders } from "kea-loaders";
import { router } from "kea-router";

import { urls } from "~/app/routes";
import { getBackendOrigin } from "~/lib/backendOrigin";

import type { participantEntryLogicType } from "./participantEntryLogicType";

/**
 * participantEntryLogic — drives the /i/:slug flow.
 *
 * State machine:
 *   resolve -> (next_step from backend)
 *     consent  -> POST /consent -> (next_step again)
 *     screener -> GET questions, POST answers -> (next_step again)
 *     session  -> POST /start -> navigate /interview/<session_id>
 */

export type ParticipantStep =
  | "loading"
  | "consent"
  | "screener"
  | "session"
  | "thanks"
  | "dropped"
  | "error";

export interface ParticipantContext {
  link_mode: "anonymous" | "named";
  participation: {
    id: string;
    status: string;
    is_preview: boolean;
  };
  study: {
    id: string;
    name: string;
    research_goal: string;
    interview_mode: string;
    estimated_minutes: number;
  };
}

export interface ScreenerQuestion {
  id: string;
  text: string;
  kind?: "single" | "multi" | "number" | "text";
  options?: string[];
}

async function _getJson(url: string): Promise<any> {
  const res = await fetch(url, { credentials: "include" });
  const body = await res.json().catch(() => ({}));
  if (!res.ok)
    throw Object.assign(new Error(body.error_code || `HTTP ${res.status}`), {
      body,
      status: res.status,
    });
  return body;
}

async function _postJson(url: string, payload?: unknown): Promise<any> {
  const res = await fetch(url, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: payload ? JSON.stringify(payload) : undefined,
  });
  const body = await res.json().catch(() => ({}));
  if (!res.ok)
    throw Object.assign(new Error(body.error_code || `HTTP ${res.status}`), {
      body,
      status: res.status,
    });
  return body;
}

function participantApiPath(pathname: string): string {
  return `${getBackendOrigin()}${pathname}`;
}

export const participantEntryLogic = kea<participantEntryLogicType>([
  path(["features", "participant", "participantEntryLogic"]),

  actions({
    setSlug: (slug: string) => ({ slug }),
    submitConsent: (data?: { name?: string; contact?: string }) => ({
      data: data ?? {},
    }),
    submitScreener: (answers: Record<string, unknown>) => ({ answers }),
    startSession: true,
  }),

  reducers({
    slug: [
      "" as string,
      {
        setSlug: (_, { slug }) => slug,
      },
    ],
    errorCode: [
      null as string | null,
      {
        setSlug: () => null,
      },
    ],
  }),

  loaders(({ values }) => ({
    context: [
      null as ParticipantContext | null,
      {
        loadContext: async () => {
          const previewQs =
            new URLSearchParams(window.location.search).get("preview") === "1"
              ? "?preview=1"
              : "";
          const body = await _getJson(
            participantApiPath(`/i/${values.slug}/${previewQs}`),
          );
          return body as ParticipantContext;
        },
      },
    ],
    nextStep: [
      "loading" as ParticipantStep,
      {
        setNextStep: (step: ParticipantStep) => step,
      },
    ],
    screenerQuestions: [
      [] as ScreenerQuestion[],
      {
        loadScreener: async () => {
          const body = await _getJson(
            participantApiPath(`/i/${values.slug}/screener/`),
          );
          return (body.questions as ScreenerQuestion[]) ?? [];
        },
      },
    ],
  })),

  listeners(({ actions, values }) => ({
    setSlug: ({ slug }) => {
      if (slug) actions.loadContext();
    },
    loadContextSuccess: ({ context }) => {
      const step = (context as any)?.next_step as ParticipantStep | undefined;
      if (step) actions.setNextStep(step);
      if (step === "screener") actions.loadScreener();
    },
    loadContextFailure: ({ errorObject }) => {
      const code = (errorObject as any)?.body?.error_code ?? "unknown";
      actions.setNextStep("error");
      (actions as any).setErrorCode?.(code); // future hook
    },
    submitConsent: async ({ data }) => {
      try {
        const body = await _postJson(
          participantApiPath(`/i/${values.slug}/consent/`),
          data,
        );
        const step = body.next_step as ParticipantStep;
        actions.setNextStep(step);
        if (step === "screener") actions.loadScreener();
      } catch (e) {
        actions.setNextStep("error");
      }
    },
    submitScreener: async ({ answers }) => {
      try {
        const body = await _postJson(
          participantApiPath(`/i/${values.slug}/screener/`),
          { answers },
        );
        actions.setNextStep(body.next_step as ParticipantStep);
      } catch (e) {
        actions.setNextStep("error");
      }
    },
    startSession: async () => {
      try {
        const body = await _postJson(
          participantApiPath(`/i/${values.slug}/start/`),
        );
        if (body.session_id) {
          const url = urls.interviewRoom(body.session_id);
          const mode = values.context?.study.interview_mode;
          const target = mode === "text" ? `${url}?mode=text` : url;
          router.actions.push(target);
        }
      } catch (e) {
        actions.setNextStep("error");
      }
    },
  })),

  afterMount(({ actions, values }) => {
    if (values.slug) actions.loadContext();
  }),

  selectors({
    studyName: [(s) => [s.context], (c) => c?.study.name ?? ""],
  }),
]);
