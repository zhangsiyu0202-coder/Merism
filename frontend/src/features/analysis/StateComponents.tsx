import { FileSearch, Loader2, Sparkles } from "lucide-react"
import type { ReactNode } from "react"

import { Button } from "~/lib/merism"

export function EmptyState({
    icon,
    title,
    description,
    action,
}: {
    icon?: ReactNode
    title: string
    description: string
    action?: { label: string; onClick: () => void }
}): JSX.Element {
    return (
        <div className="flex flex-col items-center justify-center gap-4 py-20 text-center">
            <div className="flex h-12 w-12 items-center justify-center rounded-full bg-merism-bg-subtle text-merism-text-muted">
                {icon ?? <FileSearch className="h-6 w-6" />}
            </div>
            <h3 className="text-merism-title font-medium text-merism-text">{title}</h3>
            <p className="max-w-sm text-merism-body-sm text-merism-text-muted">{description}</p>
            {action && (
                <Button variant="primary" size="sm" onClick={action.onClick}>
                    {action.label}
                </Button>
            )}
        </div>
    )
}

export function LoadingState({ message = "Loading..." }: { message?: string }): JSX.Element {
    return (
        <div className="flex flex-col items-center justify-center gap-3 py-20" role="status" aria-label={message}>
            <Loader2 className="h-6 w-6 animate-spin text-merism-accent" />
            <p className="text-merism-body-sm text-merism-text-muted">{message}</p>
        </div>
    )
}

export function GeneratingState({
    title = "AI is analyzing your research data",
    description = "This may take a few minutes depending on the amount of interview data.",
}: {
    title?: string
    description?: string
}): JSX.Element {
    return (
        <div className="flex flex-col items-center justify-center gap-4 py-20" role="status" aria-busy="true">
            <div className="relative flex h-14 w-14 items-center justify-center">
                <span className="absolute inset-0 animate-ping rounded-full bg-merism-accent/20" />
                <Sparkles className="h-7 w-7 text-merism-accent" />
            </div>
            <h3 className="text-merism-title font-medium text-merism-text">{title}</h3>
            <p className="max-w-sm text-center text-merism-body-sm text-merism-text-muted">
                {description}
            </p>
            <div className="flex items-center gap-2 text-merism-caption text-merism-text-subtle">
                <Loader2 className="h-3 w-3 animate-spin" />
                <span>Generating...</span>
            </div>
        </div>
    )
}
