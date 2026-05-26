import { http, HttpResponse } from "msw";

/**
 * Default MSW handlers.
 *
 * Keep this list SHORT. Each handler should return the "empty but healthy"
 * shape the UI can render against. Tests that exercise non-empty states
 * override via `server.use(...)`.
 *
 * As domain API views land, add one handler per endpoint here. Grouped by
 * Merism domain (study / interview / recruitment / report / memai).
 */
export const handlers = [
  // ── auth ───────────────────────────────────────────────
  http.get("/api/me/", () =>
    HttpResponse.json({
      id: "test-user",
      email: "test@merism.test",
      name: "Test User",
    }),
  ),

  // ── studies (empty list) ───────────────────────────────
  http.get("/api/studies/", () =>
    HttpResponse.json({
      count: 0,
      next: null,
      previous: null,
      results: [],
    }),
  ),
  http.get("/api/studies/:studyId/outline/", () =>
    HttpResponse.json({
      outline: {
        version: "v3",
        sections: [
          {
            id: "section-1",
            title: "Default outline",
            questions: [
              {
                id: "question-1",
                ask: "Tell me about your experience.",
                follow_up_mode: "standard",
                probe_instruction: null,
              },
            ],
          },
        ],
      },
    }),
  ),
  http.put("/api/studies/:studyId/outline/", async ({ request }) => {
    const body = (await request.json()) as {
      outline?: {
        version?: string;
        sections?: Array<{
          id?: string;
          title?: string;
          questions?: Array<{
            id?: string;
            ask?: string;
            follow_up_mode?: string;
            probe_instruction?: string | null;
          }>;
        }>;
      };
    };
    return HttpResponse.json({
      id: "outline-default",
      study: "study-default",
      version: body.outline?.version ?? "v3",
      is_current: true,
      language: "en",
      sections: body.outline ?? {
        version: "v3",
        sections: [],
      },
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    });
  }),

  // ── custom report queries (empty history) ──────────────
  http.get("/api/custom-report-queries/", () =>
    HttpResponse.json({ count: 0, results: [] }),
  ),

  // ── knowledge search (empty response) ──────────────────
  http.post("/api/knowledge/search/", () =>
    HttpResponse.json({ answer_markdown: "", chart: null, citations: [] }),
  ),

  // ── ask merism stream — default to a no-op SSE response ─
  http.post("/api/ask/stream/", () =>
    HttpResponse.text("event: done\ndata: {}\n\n", {
      headers: { "Content-Type": "text/event-stream" },
    }),
  ),
];
