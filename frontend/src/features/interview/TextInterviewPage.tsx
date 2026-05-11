import { useActions, useValues } from "kea"
import { Send } from "lucide-react"
import { useEffect, useRef } from "react"

import { Button } from "~/lib/merism"

import { textInterviewLogic } from "./textInterviewLogic"

/**
 * TextInterviewPage — typed-conversation interview.
 *
 * Participants in ``study.interview_mode == "text"`` are routed here.
 * The page hits ``POST /api/sessions/:id/message/`` which streams an SSE
 * sequence of ``delta`` (incremental partial) + ``done`` (final decision)
 * events. The same ``stream_turn`` code path powers voice — text mode is
 * not a separate flow, it's the same flow without speech I/O.
 */
export default function TextInterviewPage(): JSX.Element {
    const { sessionId, turns, draft, isSending, isCompleted, error } = useValues(textInterviewLogic)
    const { setDraft, sendMessage, bootstrapFromUrl } = useActions(textInterviewLogic)

    const endRef = useRef<HTMLDivElement | null>(null)
    useEffect(() => {
        bootstrapFromUrl()
    }, [bootstrapFromUrl])
    useEffect(() => {
        endRef.current?.scrollIntoView({ behavior: "smooth" })
    }, [turns.length])

    if (!sessionId) {
        return (
            <main className="flex min-h-screen items-center justify-center bg-merism-bg p-6">
                <p className="text-merism-body text-merism-text-muted">Loading interview…</p>
            </main>
        )
    }

    return (
        <main className="min-h-screen bg-merism-bg">
            <div className="mx-auto flex max-w-2xl flex-col gap-4 px-6 py-10">
                <header className="flex items-center gap-3">
                    <div className="flex h-8 w-8 items-center justify-center rounded-merism-sm bg-merism-accent text-white">
                        <span className="font-display text-merism-body-sm font-[600]">M</span>
                    </div>
                    <span className="font-display text-merism-subtitle font-[500]">Merism</span>
                </header>

                <section className="flex-1 overflow-y-auto rounded-merism-lg bg-merism-surface p-6 shadow-merism-card ring-1 ring-[color:var(--merism-hairline)]">
                    <ul className="flex flex-col gap-4">
                        {turns.map((t, i) => (
                            <li
                                key={i}
                                className={`flex flex-col gap-1 ${
                                    t.role === "user" ? "items-end" : "items-start"
                                }`}
                            >
                                <span className="text-merism-caption text-merism-text-subtle">
                                    {t.role === "user" ? "You" : "Interviewer"}
                                </span>
                                <div
                                    className={`max-w-[80%] rounded-merism-md px-4 py-3 text-merism-body ${
                                        t.role === "user"
                                            ? "bg-merism-accent text-white"
                                            : "bg-merism-bg-subtle text-merism-text"
                                    }`}
                                >
                                    {t.text || (t.streaming ? <em className="opacity-60">…</em> : "")}
                                </div>
                            </li>
                        ))}
                        <div ref={endRef} />
                    </ul>
                </section>

                {error && (
                    <div
                        role="alert"
                        className="rounded-merism-md bg-[color:var(--merism-status-danger-bg)] px-4 py-2 text-merism-body-sm text-[color:var(--merism-status-danger)]"
                    >
                        {error}
                    </div>
                )}

                {isCompleted ? (
                    <div className="rounded-merism-lg bg-merism-surface p-6 text-center shadow-merism-card ring-1 ring-[color:var(--merism-hairline)]">
                        <p className="font-display text-merism-subtitle font-[500] text-merism-text">
                            Thank you — your session is complete.
                        </p>
                    </div>
                ) : (
                    <form
                        className="flex items-end gap-2 rounded-merism-lg bg-merism-surface p-3 shadow-merism-card ring-1 ring-[color:var(--merism-hairline)]"
                        onSubmit={(e) => {
                            e.preventDefault()
                            if (draft.trim() && !isSending) sendMessage()
                        }}
                    >
                        <textarea
                            className="flex-1 resize-none bg-transparent p-2 text-merism-body outline-none"
                            placeholder="Type your answer…"
                            rows={2}
                            value={draft}
                            onChange={(e) => setDraft(e.target.value)}
                            onKeyDown={(e) => {
                                if (e.key === "Enter" && !e.shiftKey) {
                                    e.preventDefault()
                                    if (draft.trim() && !isSending) sendMessage()
                                }
                            }}
                            disabled={isSending}
                        />
                        <Button
                            type="submit"
                            disabled={!draft.trim() || isSending}
                            iconLeft={<Send className="h-4 w-4" />}
                        >
                            {isSending ? "…" : "Send"}
                        </Button>
                    </form>
                )}
            </div>
        </main>
    )
}
