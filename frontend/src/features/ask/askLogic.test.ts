import { http, HttpResponse } from "msw";
import { resetContext } from "kea";
import { beforeEach, describe, expect, it } from "vitest";

import { server } from "~/test/msw/server";

import { askLogic } from "./askLogic";

/**
 * Encode a sequence of SSE events as a ReadableStream of Uint8Arrays,
 * which is how fetch-body-reader works in tests.
 */
function streamBody(chunks: string[]): ReadableStream<Uint8Array> {
  const encoder = new TextEncoder();
  return new ReadableStream({
    start(controller) {
      for (const chunk of chunks) controller.enqueue(encoder.encode(chunk));
      controller.close();
    },
  });
}

describe("askLogic", () => {
  beforeEach(() => {
    resetContext({ createStore: true });
    askLogic.mount();
  });

  it("appends a user message and an assistant placeholder when sending", async () => {
    server.use(
      http.post("/api/ask/stream/", () =>
        HttpResponse.text(
          `event: done\ndata: {"answer_markdown":"ok","chart":null,"citations":[]}\n\n`,
          { headers: { "Content-Type": "text/event-stream" } },
        ),
      ),
    );
    askLogic.actions.askQuestion("What do users say about pricing?");
    // After the listener yields once, both messages should be present
    // even before the response arrives.
    await new Promise((r) => setTimeout(r, 0));
    expect(askLogic.values.messages).toHaveLength(2);
    expect(askLogic.values.messages[0]?.role).toBe("user");
    expect(askLogic.values.messages[1]?.role).toBe("assistant");
  });

  it("streams delta events into the assistant message", async () => {
    server.use(
      http.post("/api/ask/stream/", () => {
        return new HttpResponse(
          streamBody([
            `event: delta\ndata: {"text":"Hel"}\n\n`,
            `event: delta\ndata: {"text":"lo"}\n\n`,
            `event: done\ndata: {"answer_markdown":"Hello","chart":null,"citations":[]}\n\n`,
          ]),
          { headers: { "Content-Type": "text/event-stream" } },
        );
      }),
    );
    await askLogic.asyncActions.askQuestion("hi");
    const assistant = askLogic.values.messages.at(-1);
    expect(assistant?.content).toBe("Hello");
    expect(assistant?.streaming).toBe(false);
  });

  it("attaches chart + citations from the done event", async () => {
    server.use(
      http.post("/api/ask/stream/", () =>
        HttpResponse.text(
          `event: done\ndata: ${JSON.stringify({
            answer_markdown: "Three drivers…",
            chart: { type: "bar", title: "x", x: ["a"], y: [1], unit: null },
            citations: [
              { session_id: "s1", ts: 12, quote: "cost", speaker: "Alice" },
            ],
          })}\n\n`,
          { headers: { "Content-Type": "text/event-stream" } },
        ),
      ),
    );
    await askLogic.asyncActions.askQuestion("why?");
    const assistant = askLogic.values.messages.at(-1);
    expect(assistant?.chart?.type).toBe("bar");
    expect(assistant?.citations?.[0]?.speaker).toBe("Alice");
  });

  it("marks the assistant message errored on failed response", async () => {
    server.use(
      http.post("/api/ask/stream/", () =>
        HttpResponse.json({ detail: "nope" }, { status: 500 }),
      ),
    );
    await askLogic.asyncActions.askQuestion("x");
    const assistant = askLogic.values.messages.at(-1);
    expect(assistant?.errored).toBe(true);
    expect(assistant?.streaming).toBe(false);
  });

  it("ignores duplicate sends while in-flight", async () => {
    // Use a never-resolving stream to keep isSending=true.
    server.use(
      http.post("/api/ask/stream/", () => {
        return new HttpResponse(new ReadableStream({ start: () => {} }), {
          headers: { "Content-Type": "text/event-stream" },
        });
      }),
    );
    askLogic.actions.askQuestion("a");
    askLogic.actions.askQuestion("b");
    await new Promise((r) => setTimeout(r, 0));
    // Only the first question should have been accepted.
    const userMessages = askLogic.values.messages.filter(
      (m) => m.role === "user",
    );
    expect(userMessages).toHaveLength(1);
    expect(userMessages[0]?.content).toBe("a");
  });
});
