import { useValues, useActions } from "kea"
import { useState } from "react"
import { useTranslation } from "react-i18next"

import {
    ChatPanel,
    Illustration,
    PageTopBar,
    type ChatMessage,
} from "~/lib/merism"

import { askLogic } from "./askLogic"
import { CitationStrip } from "./CitationStrip"
import { ChartRenderer } from "./ChartRenderer"
import type { AskMerismMessage } from "./types"

type AskTab = "chat" | "history" | "saved"



/**
 * Ask Merism surface.
 *
 * Cross-study Q&A. Spec refs:
 *   - PRODUCT.md §3.6 (Custom Report shape)
 *   - PRODUCT.md §3.7 (Knowledge Explore)
 *
 * Chat / History / Saved sub-tabs; only Chat is wired today.
 */
export default function AskPage(): JSX.Element {
    const { t } = useTranslation()
    const { messages, isSending } = useValues(askLogic)
    const { askQuestion } = useActions(askLogic)
    const [tab, setTab] = useState<AskTab>("chat")

    const TABS = [
        { value: "chat", label: t("ask.tabs.chat") },
        { value: "history", label: t("ask.tabs.history") },
        { value: "saved", label: t("ask.tabs.saved") },
    ]
    const EXAMPLES = (t("ask.suggestions", { returnObjects: true }) as string[]) ?? []

    const chatMessages: ChatMessage[] = messages.map(toChatMessage)

    return (
        <div className="flex h-full flex-col gap-8">
            <PageTopBar
                title={t("ask.title")}
                lede={t("ask.lede")}
                tabs={TABS}
                activeTab={tab}
                onTabChange={(v) => setTab(v as AskTab)}
            />

            {tab === "chat" && (
                <ChatPanel
                    title={t("ask.title")}
                    messages={chatMessages}
                    onSend={askQuestion}
                    isSending={isSending}
                    placeholder={t("ask.placeholder")}
                    emptyState={
                        <div className="flex flex-col items-center gap-5 text-center">
                            <Illustration
                                name="fast-internet"
                                size="md"
                                className="text-merism-text"
                            />
                            <div className="flex flex-col gap-3">
                                <p className="text-merism-body font-medium text-merism-text">
                                    {t("ask.empty_hero_title")}
                                </p>
                                <ul className="flex flex-col gap-1.5 text-left text-merism-body-sm">
                                    {EXAMPLES.map((ex) => (
                                        <li key={ex}>
                                            <button
                                                type="button"
                                                onClick={() => askQuestion(ex)}
                                                className="text-left text-merism-accent hover:underline"
                                            >
                                                {ex}
                                            </button>
                                        </li>
                                    ))}
                                </ul>
                            </div>
                        </div>
                    }
                    footer={
                        <span>{t("ask.lede")}</span>
                    }
                    className="min-h-0 flex-1"
                />
            )}

            {tab === "history" && (
                <ComingSoon label={t("ask.history_coming_soon")} />
            )}
            {tab === "saved" && <ComingSoon label={t("ask.saved_coming_soon")} />}
        </div>
    )
}

function ComingSoon({ label }: { label: string }): JSX.Element {
    return (
        <div className="rounded-merism-lg bg-merism-surface p-16 text-center text-merism-text-muted shadow-merism-card ring-1 ring-[color:var(--merism-hairline)]">
            {label}
        </div>
    )
}

function toChatMessage(m: AskMerismMessage): ChatMessage {
    if (m.role === "user") {
        return { id: m.id, role: "user", content: m.content }
    }
    return {
        id: m.id,
        role: "assistant",
        streaming: m.streaming,
        content: m.content || (m.streaming ? "" : "(no answer)"),
        footer:
            !m.streaming && (m.chart || (m.citations && m.citations.length > 0))
                ? (
                      <div className="flex flex-col gap-2">
                          {m.chart && <ChartRenderer chart={m.chart} />}
                          {m.citations && m.citations.length > 0 && (
                              <CitationStrip citations={m.citations} />
                          )}
                      </div>
                  )
                : undefined,
    }
}
