import { useActions, useValues } from "kea"
import { MessageSquare, X } from "lucide-react"
import { useCallback, useEffect, useRef } from "react"

import { cn } from "~/lib/merism/utils/cn"

import { sidebarLogic } from "./sidebarLogic"

/**
 * SidePanel — right-side slide-out container with resizable handle.
 *
 * Animation pattern adapted from PostHog:
 *   - `transition-[width]` 100ms ease-out
 *   - Absolute positioning, slides in from the right edge
 *   - Resizer handle on the left border for drag-to-resize
 *   - Persisted width/open state via sidebarLogic (localStorage)
 *
 * Merism visual style is preserved — radius, color, fonts unchanged.
 */

interface SidePanelProps {
    children?: React.ReactNode
}

export function SidePanel({ children }: SidePanelProps): JSX.Element | null {
    const { sidePanel } = useValues(sidebarLogic)
    const { closeSidePanel, setSidePanelWidth } = useActions(sidebarLogic)

    const { tab, isOpen, width } = sidePanel

    // Nothing to show
    if (!tab) return null

    return (
        <>
            {/* Resize handle — only when open */}
            {isOpen && (
                <ResizeHandle
                    width={width}
                    onResize={setSidePanelWidth}
                />
            )}
            <aside
                className={cn(
                    "flex shrink-0 flex-col border-l border-[color:var(--merism-hairline)] bg-merism-surface",
                    "transition-[width] ease-[var(--merism-ease)] will-change-[width] overflow-hidden",
                )}
                style={{
                    width: isOpen ? `${width}px` : "0px",
                    transitionDuration: "var(--merism-duration-layout)",
                }}
            >
                {isOpen && tab === "ask" && (
                    <PanelShell
                        title="Ask Merism"
                        icon={<MessageSquare className="h-4 w-4" />}
                        onClose={closeSidePanel}
                    >
                        {children}
                    </PanelShell>
                )}
            </aside>
        </>
    )
}

function PanelShell({
    title,
    icon,
    onClose,
    children,
}: {
    title: string
    icon?: React.ReactNode
    onClose: () => void
    children?: React.ReactNode
}): JSX.Element {
    return (
        <div className="flex h-full min-w-0 flex-col">
            {/* Header */}
            <div className="flex items-center justify-between gap-2 border-b border-[color:var(--merism-hairline)] px-4 py-3">
                <div className="flex items-center gap-2 text-merism-text">
                    {icon && <span className="text-merism-text-subtle">{icon}</span>}
                    <span className="text-merism-label font-medium">{title}</span>
                </div>
                <button
                    type="button"
                    onClick={onClose}
                    aria-label="Close"
                    title="Close"
                    className="inline-flex h-7 w-7 items-center justify-center rounded-merism-md text-merism-text-subtle transition-colors hover:bg-merism-bg-subtle hover:text-merism-text"
                >
                    <X className="h-3.5 w-3.5" strokeWidth={2} />
                </button>
            </div>
            {/* Content */}
            <div className="flex min-h-0 flex-1 flex-col overflow-hidden">
                {children}
            </div>
        </div>
    )
}

function ResizeHandle({
    width,
    onResize,
}: {
    width: number
    onResize: (w: number) => void
}): JSX.Element {
    const dragStateRef = useRef<{ startX: number; startWidth: number } | null>(null)

    const handleMouseMove = useCallback((e: MouseEvent) => {
        const state = dragStateRef.current
        if (!state) return
        const delta = state.startX - e.pageX
        const newWidth = state.startWidth + delta
        onResize(newWidth)
    }, [onResize])

    const handleMouseUp = useCallback(() => {
        dragStateRef.current = null
        document.body.style.cursor = ""
        document.body.style.userSelect = ""
        window.removeEventListener("mousemove", handleMouseMove)
        window.removeEventListener("mouseup", handleMouseUp)
    }, [handleMouseMove])

    const handleMouseDown = (e: React.MouseEvent) => {
        if (e.button !== 0) return
        e.preventDefault()
        dragStateRef.current = { startX: e.pageX, startWidth: width }
        document.body.style.cursor = "col-resize"
        document.body.style.userSelect = "none"
        window.addEventListener("mousemove", handleMouseMove)
        window.addEventListener("mouseup", handleMouseUp)
    }

    useEffect(() => {
        return () => {
            window.removeEventListener("mousemove", handleMouseMove)
            window.removeEventListener("mouseup", handleMouseUp)
        }
    }, [handleMouseMove, handleMouseUp])

    return (
        <div
            role="separator"
            aria-orientation="vertical"
            aria-label="Resize panel"
            onMouseDown={handleMouseDown}
            className={cn(
                "group absolute top-0 bottom-0 z-10 w-[6px] -ml-[3px] cursor-col-resize",
                "hover:bg-merism-accent/10",
            )}
            style={{
                right: `${width}px`,
            }}
        >
            <div className="absolute inset-y-0 left-1/2 w-[1px] -translate-x-1/2 bg-[color:var(--merism-hairline)] transition-colors group-hover:bg-merism-accent group-active:bg-merism-accent" />
        </div>
    )
}
