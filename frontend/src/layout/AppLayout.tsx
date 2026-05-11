import type { ReactNode } from "react"

import { NavigationSidebar } from "./NavigationSidebar"
import { TopBar } from "./TopBar"

/**
 * AppLayout — researcher chrome: sidebar + topbar + content.
 *
 * Page gutter is ``--spacing-merism-gutter`` (48 px) — editorial spacing.
 * Content area has NO max-width; scenes with narrow-column intent apply
 * their own ``max-w-*`` inside.
 */
export function AppLayout({ children }: { children: ReactNode }): JSX.Element {
    return (
        <div className="flex h-screen w-screen overflow-hidden bg-merism-bg text-merism-text">
            <NavigationSidebar />
            <div className="flex min-w-0 flex-1 flex-col">
                <TopBar />
                <main className="min-w-0 flex-1 overflow-y-auto">
                    <div className="w-full px-[var(--spacing-merism-gutter)] pb-16 pt-6">
                        {children}
                    </div>
                </main>
            </div>
        </div>
    )
}
