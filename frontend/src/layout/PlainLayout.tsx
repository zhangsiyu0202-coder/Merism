import type { ReactNode } from "react"

/**
 * PlainLayout — full-bleed centered content with no app chrome.
 *
 * Used by Login + Error404 + other single-task screens.
 */
export function PlainLayout({ children }: { children: ReactNode }): JSX.Element {
    return (
        <div className="flex min-h-screen w-screen items-center justify-center bg-merism-bg p-6 text-merism-text">
            <div className="w-full max-w-md">{children}</div>
        </div>
    )
}
