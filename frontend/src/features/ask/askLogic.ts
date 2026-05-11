import { actions, kea, listeners, path, reducers, selectors } from "kea"

import type { AskMerismAnswer, AskMerismMessage } from "./types"
import type { askLogicType } from './askLogicType'

/**
 * askLogic — state + side effects for the Ask Merism surface.
 *
 * Messages are the canonical history. When the user hits send we:
 *   1. Append the user message with a locally-generated id.
 *   2. Insert an assistant placeholder (streaming=true).
 *   3. POST /api/ask/stream/ and stream the chunks into the placeholder.
 *   4. On the final `done` event, swap the placeholder for the full answer
 *      with citations + chart attached.
 *
 * The fetch is raw Response parsing so we can handle SSE without dragging
 * in a SSE client library. Tests swap the fetch via `fetchImpl` action
 * (see askLogic.test.ts).
 */
export const askLogic = kea<askLogicType>([
    path(["scenes", "ask", "askLogic"]),

    actions({
        askQuestion: (question: string) => ({ question }),
        pushMessage: (message: AskMerismMessage) => ({ message }),
        updateMessage: (id: string, patch: Partial<AskMerismMessage>) => ({ id, patch }),
        setSending: (sending: boolean) => ({ sending }),
        clear: true,
    }),

    reducers({
        messages: [
            [] as AskMerismMessage[],
            {
                pushMessage: (state, { message }) => [...state, message],
                updateMessage: (state, { id, patch }) =>
                    state.map((m) => (m.id === id ? { ...m, ...patch } : m)),
                clear: () => [],
            },
        ],
        isSending: [
            false,
            {
                setSending: (_, { sending }) => sending,
            },
        ],
    }),

    selectors({
        messageCount: [(s) => [s.messages], (m) => m.length],
        lastAssistant: [
            (s) => [s.messages],
            (messages): AskMerismMessage | undefined =>
                [...messages].reverse().find((m) => m.role === "assistant"),
        ],
    }),

    listeners(({ actions: a, values }) => ({
        askQuestion: async ({ question }) => {
            if (values.isSending) return

            const userId = crypto.randomUUID()
            const assistantId = crypto.randomUUID()
            a.pushMessage({
                id: userId,
                role: "user",
                content: question,
            })
            a.pushMessage({
                id: assistantId,
                role: "assistant",
                content: "",
                streaming: true,
            })
            a.setSending(true)

            try {
                const response = await fetch("/api/ask/stream/", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ question }),
                })
                if (!response.ok || !response.body) {
                    throw new Error(`Ask stream failed: ${response.status}`)
                }
                const answer = await parseAskStream(response, (partial) => {
                    a.updateMessage(assistantId, { content: partial })
                })
                a.updateMessage(assistantId, {
                    content: answer.answer_markdown,
                    streaming: false,
                    chart: answer.chart ?? undefined,
                    citations: answer.citations ?? [],
                })
            } catch (err) {
                a.updateMessage(assistantId, {
                    content: err instanceof Error ? err.message : "Something went wrong.",
                    streaming: false,
                    errored: true,
                })
            } finally {
                a.setSending(false)
            }
        },
    })),
])

/**
 * Minimal SSE parser. Accepts a streaming Response and yields the final
 * AskMerismAnswer payload when the `done` event arrives. Calls
 * `onDelta(partial)` every `delta` event so the UI can render the partial
 * string as the model generates it.
 */
async function parseAskStream(
    response: Response,
    onDelta: (partial: string) => void,
): Promise<AskMerismAnswer> {
    const reader = response.body!.getReader()
    const decoder = new TextDecoder()
    let buffer = ""
    let partial = ""
    let final: AskMerismAnswer | null = null

    while (true) {
        const { value, done } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })

        const events = buffer.split("\n\n")
        buffer = events.pop() ?? ""

        for (const raw of events) {
            const parsed = parseSSEBlock(raw)
            if (!parsed) continue
            if (parsed.event === "delta" && typeof parsed.data.text === "string") {
                partial += parsed.data.text
                onDelta(partial)
            } else if (parsed.event === "done") {
                final = parsed.data as unknown as AskMerismAnswer
            } else if (parsed.event === "error") {
                throw new Error(String(parsed.data.message ?? "Ask stream error"))
            }
        }
    }

    if (!final) {
        return {
            answer_markdown: partial,
            chart: null,
            citations: [],
        }
    }
    return final
}

interface ParsedSSE {
    event: string
    data: Record<string, unknown>
}

function parseSSEBlock(raw: string): ParsedSSE | null {
    let event = "message"
    let data = ""
    for (const line of raw.split("\n")) {
        if (line.startsWith("event:")) event = line.slice(6).trim()
        else if (line.startsWith("data:")) data += line.slice(5).trim()
    }
    if (!data) return null
    try {
        return { event, data: JSON.parse(data) }
    } catch {
        return null
    }
}
