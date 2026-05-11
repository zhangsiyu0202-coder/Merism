import { ArrowRight } from "lucide-react"

import { Button, StatusDot, Tag, Tooltip } from "../primitives"

export interface SessionRowProps {
    id: string
    participantName: string
    participantExternalId?: string
    durationSeconds?: number
    mode: "voice" | "video" | "text" | "offline"
    status: "pending" | "active" | "completed" | "failed"
    tags?: string[]
    onOpen: (id: string) => void
}

const STATUS_TO_DOT: Record<
    SessionRowProps["status"],
    { status: "ok" | "warn" | "error" | "neutral"; label: string }
> = {
    pending: { status: "neutral", label: "Pending" },
    active: { status: "warn", label: "Active" },
    completed: { status: "ok", label: "Completed" },
    failed: { status: "error", label: "Failed" },
}

function formatDuration(seconds?: number): string {
    if (seconds == null) return "—"
    const m = Math.floor(seconds / 60)
    const s = Math.floor(seconds % 60)
    return `${m}:${s.toString().padStart(2, "0")}`
}

export function SessionRow({
    id,
    participantName,
    participantExternalId,
    durationSeconds,
    mode,
    status,
    tags = [],
    onOpen,
}: SessionRowProps) {
    const dot = STATUS_TO_DOT[status]
    return (
        <div
            role="row"
            className="grid grid-cols-[auto_1fr_auto_auto_auto_auto] items-center gap-3 border-b border-[color:var(--merism-hairline)] px-3 py-2 text-sm hover:bg-merism-bg-subtle"
        >
            <StatusDot {...dot} />
            <div role="cell" className="min-w-0">
                <div className="truncate text-merism-text">{participantName}</div>
                {participantExternalId && (
                    <div className="truncate text-xs text-merism-text-muted">
                        {participantExternalId}
                    </div>
                )}
            </div>
            <Tooltip label={`${mode} mode`}>
                <Tag variant="neutral">{mode}</Tag>
            </Tooltip>
            <span role="cell" className="tabular-nums text-merism-text-muted">
                {formatDuration(durationSeconds)}
            </span>
            <div role="cell" className="flex gap-1">
                {tags.slice(0, 2).map((t) => (
                    <Tag key={t} variant="accent">
                        {t}
                    </Tag>
                ))}
            </div>
            <Button
                size="sm"
                variant="ghost"
                onClick={() => onOpen(id)}
                iconRight={<ArrowRight className="h-4 w-4" />}
            >
                View
            </Button>
        </div>
    )
}
