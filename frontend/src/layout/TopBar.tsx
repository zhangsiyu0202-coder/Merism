import { useValues } from "kea"

import { sceneLogic } from "~/app/sceneLogic"
import { cn } from "~/lib/merism/utils/cn"

/**
 * TopBar — thin 52 px bar along the top of the app area.
 *
 * Intentionally sparse: the left side shows a mono-voice breadcrumb
 * ("workspace / studies / <id>") and the right side hosts any scene-
 * specific trailing actions via the ``trailing`` slot (rendered by
 * AppLayout via React context if needed; for now the slot is empty).
 */
export function TopBar({ className }: { className?: string }): JSX.Element {
    const { activeSceneConfig, sceneParams } = useValues(sceneLogic)

    return (
        <header
            className={cn(
                "flex h-[var(--spacing-merism-topbar)] shrink-0 items-center gap-3 " +
                    "border-b border-[color:var(--merism-hairline)] bg-merism-bg px-6",
                className,
            )}
        >
            <Breadcrumb name={activeSceneConfig.name} params={sceneParams.params} />
        </header>
    )
}

function Breadcrumb({
    name,
    params,
}: {
    name: string
    params: Record<string, string>
}): JSX.Element {
    const studyId = params["id"]
    const tab = params["tab"]

    return (
        <nav
            aria-label="Breadcrumb"
            className="flex items-center gap-2 font-mono text-merism-label uppercase tracking-merism-caps text-merism-text-muted"
        >
            <span>Workspace</span>
            <Divider />
            <span>{name}</span>
            {studyId && (
                <>
                    <Divider />
                    <span className="normal-case tracking-normal text-merism-text-muted">
                        {studyId.slice(0, 8)}
                    </span>
                </>
            )}
            {tab && (
                <>
                    <Divider />
                    <span>{tab}</span>
                </>
            )}
        </nav>
    )
}

function Divider(): JSX.Element {
    return (
        <span aria-hidden="true" className="text-merism-border-strong">
            /
        </span>
    )
}
