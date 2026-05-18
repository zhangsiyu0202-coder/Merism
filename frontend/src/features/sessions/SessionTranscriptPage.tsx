import { useValues } from "kea"
import { ArrowLeft } from "lucide-react"
import { useEffect, useState } from "react"
import { useTranslation } from "react-i18next"

import { urls } from "~/app/routes"
import { sceneLogic } from "~/app/sceneLogic"
import { api } from "~/lib/api"
import { Button, PageHeading, Tag } from "~/lib/merism"

interface TranscriptTurn {
    role: "user" | "assistant"
    text: string
    timestamp?: string
}

interface SessionDetail {
    id: string
    status: string
    started_at: string | null
    ended_at: string | null
    transcript: TranscriptTurn[]
    participant_name?: string
    study?: string
}

/**
 * SessionTranscriptPage — full-page transcript viewer.
 *
 * Design reference: Dovetail transcript view.
 * - Left-aligned speaker labels with role distinction
 * - AI questions in neutral surface, participant answers in accent-soft
 * - Timestamps where available
 * - Back button to return to study sessions tab
 */
export default function SessionTranscriptPage(): JSX.Element {
    const { t } = useTranslation()
    const { sceneParams } = useValues(sceneLogic)
    const sessionId = sceneParams.params.sessionId as string | undefined

    const [session, setSession] = useState<SessionDetail | null>(null)
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState<string | null>(null)

    useEffect(() => {
        if (!sessionId) return
        setLoading(true)
        api.get<SessionDetail>(`/api/sessions/${sessionId}/`)
            .then((data) => {
                setSession(data)
                setError(null)
            })
            .catch((err) => setError(err.message ?? "加载失败"))
            .finally(() => setLoading(false))
    }, [sessionId])

    if (!sessionId) {
        return <div className="p-8 text-merism-text-muted">无效的访谈 ID</div>
    }

    if (loading) {
        return (
            <div className="flex min-h-64 items-center justify-center text-merism-text-muted">
                加载中…
            </div>
        )
    }

    if (error) {
        return (
            <div className="p-8 text-merism-danger">
                {error}
            </div>
        )
    }

    const transcript = session?.transcript ?? []
    const studyId = session?.study

    return (
        <div className="flex flex-col gap-6">
            {/* Header */}
            <div className="flex items-center gap-4">
                {studyId && (
                    <a href={urls.study(studyId, "sessions")}>
                        <Button variant="ghost" size="sm">
                            <ArrowLeft className="h-4 w-4" />
                        </Button>
                    </a>
                )}
                <PageHeading
                    eyebrow={`访谈转写稿 · ${sessionId.slice(0, 8)}`}
                    title={session?.participant_name || `访谈 ${sessionId.slice(0, 8)}`}
                    lede={session?.started_at ? `开始于 ${new Date(session.started_at).toLocaleString("zh-CN")}` : ""}
                    status={
                        session && (
                            <Tag variant={session.status === "completed" ? "success" : "neutral"}>
                                {session.status}
                            </Tag>
                        )
                    }
                />
            </div>

            {/* Transcript body */}
            {transcript.length === 0 ? (
                <div className="rounded-merism-lg bg-merism-surface px-8 py-16 text-center text-merism-text-muted ring-1 ring-[color:var(--merism-hairline)]">
                    暂无转写内容
                </div>
            ) : (
                <div className="w-full max-w-4xl space-y-1">
                    {transcript.map((turn, i) => (
                        <TranscriptBubble key={i} turn={turn} />
                    ))}
                </div>
            )}
        </div>
    )
}

function TranscriptBubble({ turn }: { turn: TranscriptTurn }): JSX.Element {
    const isAI = turn.role === "assistant"

    return (
        <div className={`flex gap-4 px-4 py-3 rounded-merism-md transition-colors hover:bg-merism-surface/60 ${isAI ? "" : "bg-merism-accent-soft/20"}`}>
            {/* Speaker label */}
            <div className="w-20 shrink-0 pt-0.5">
                <span
                    className={`inline-block rounded-merism-sm px-2 py-0.5 font-mono text-[11px] uppercase tracking-merism-caps ${
                        isAI
                            ? "bg-merism-surface text-merism-text-subtle ring-1 ring-[color:var(--merism-hairline)]"
                            : "bg-merism-accent/10 text-merism-accent"
                    }`}
                >
                    {isAI ? "AI" : "参与者"}
                </span>
            </div>

            {/* Content */}
            <div className="min-w-0 flex-1">
                <p className="text-[15px] leading-[2] text-merism-text whitespace-pre-wrap">
                    {turn.text}
                </p>
                {turn.timestamp && (
                    <span className="mt-1 block font-mono text-[10px] text-merism-text-subtle">
                        {turn.timestamp}
                    </span>
                )}
            </div>
        </div>
    )
}
