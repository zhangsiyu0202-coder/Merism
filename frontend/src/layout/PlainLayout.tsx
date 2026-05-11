import type { ReactNode } from "react"

/**
 * PlainLayout — full-bleed centered content with no app chrome.
 *
 * Used by Login + Error404 + other single-task screens.
 */
export function PlainLayout({ children }: { children: ReactNode }): JSX.Element {
    return (
        <div className="min-h-screen w-screen bg-merism-bg text-merism-text">
            {children}
        </div>
    )
}
