import type { ReactNode } from "react"

/**
 * ParticipantLayout — chrome for the participant-facing Interview Room.
 *
 * Intentionally stripped down: no navigation, no branding chrome. The
 * participant sees ONLY the interview surface + a subtle footer with
 * the study brand.
 */
export function ParticipantLayout({ children }: { children: ReactNode }): JSX.Element {
    return (
        <div className="flex min-h-screen w-screen flex-col bg-merism-bg text-merism-text">
            <main className="flex flex-1 flex-col">{children}</main>
            <footer className="border-t border-[color:var(--merism-hairline)] px-6 py-3 text-center font-mono text-merism-caption uppercase tracking-merism-caps text-merism-text-subtle">
                Moderated by Merism
            </footer>
        </div>
    )
}
