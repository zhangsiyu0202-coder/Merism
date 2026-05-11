import { useActions, useValues } from "kea"
import { Pin } from "lucide-react"

import { ChartRenderer, CitationStrip } from "~/features/ask"
import { Button, ChatPanel, Sidebar, type ChatMessage } from "~/lib/merism"

import { customReportLogic, type CustomReportMessage } from "./customReportLogic"

/**
 * Custom Report sidebar — Analysis tab right-drawer.
 *
 * Per PRODUCT.md §3.6, the researcher asks questions scoped to the
 * current study; answers render with markdown + optional chart + citations.
 * "Pin to dashboard" / "Save as insight" actions live on each answer.
 */
export function CustomReportSidebar() {
    const { open, messages, isSending } = useValues(customReportLogic)
    const { close, askQuestion, togglePin } = useActions(customReportLogic)

    const chatMessages: ChatMessage[] = messages.map((m) => toChatMessage(m, togglePin))

    return (
        <Sidebar
            open={open}
            onOpenChange={(next) => (!next ? close() : undefined)}
            title="Custom report"
            description="Ask anything about this study"
        >
            <ChatPanel
                messages={chatMessages}
                onSend={askQuestion}
                isSending={isSending}
                placeholder="What do you want to know?"
                emptyState={
                    <div className="flex flex-col gap-2 text-left">
                        <p className="text-merism-text-muted">Try:</p>
                        <ul className="space-y-1 text-sm">
                            <li>"What's the main reason participants don't recommend?"</li>
                            <li>"How does sentiment differ by age group?"</li>
                            <li>"Show me the top 5 mentions of pricing."</li>
                        </ul>
                    </div>
                }
                footer={
                    <span>
                        Answers cite specific interview timestamps. Pin useful answers to the
                        dashboard.
                    </span>
                }
                className="min-h-0 flex-1 border-0 shadow-none"
            />
        </Sidebar>
    )
}

function toChatMessage(
    m: CustomReportMessage,
    togglePin: (id: string) => void,
): ChatMessage {
    if (m.role === "user") {
        return { id: m.id, role: "user", content: m.content }
    }

    const hasExtras =
        !m.streaming &&
        ((m.chart !== undefined && m.chart !== null) ||
            (m.citations !== undefined && m.citations.length > 0) ||
            !m.errored)

    return {
        id: m.id,
        role: "assistant",
        streaming: m.streaming,
        content: m.content || (m.streaming ? "" : "(no answer)"),
        footer: hasExtras ? (
            <div className="flex flex-col gap-2">
                {m.chart && <ChartRenderer chart={m.chart} />}
                {m.citations && m.citations.length > 0 && (
                    <CitationStrip citations={m.citations} />
                )}
                {!m.errored && (
                    <div className="flex items-center gap-2 pt-1">
                        <Button
                            size="sm"
                            variant={m.pinned ? "secondary" : "ghost"}
                            iconLeft={<Pin className="h-4 w-4" />}
                            onClick={() => togglePin(m.id)}
                        >
                            {m.pinned ? "Pinned" : "Pin to dashboard"}
                        </Button>
                    </div>
                )}
            </div>
        ) : undefined,
    }
}
