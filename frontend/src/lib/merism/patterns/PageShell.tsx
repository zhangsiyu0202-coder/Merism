import { motion } from "motion/react"
import { type ReactNode } from "react"

import { cn } from "../utils/cn"

/**
 * PageShell — the app chrome for every authed Merism surface.
 *
 * Layout: fixed-height flex column with a top nav bar (56 px) and a main
 * scroll region. An optional sidebar slot renders on the right at
 * `--spacing-merism-sidebar` (22 rem) width.
 *
 * Motion: a 200ms fade-in-up on mount so screen transitions feel
 * intentional but never delay perceived load. Respects
 * `prefers-reduced-motion` via globals.css.
 */
export interface PageShellProps {
    nav: ReactNode
    sidebar?: ReactNode
    children: ReactNode
    className?: string
    /** Narrow surfaces (e.g., Ask Merism) look better with a centered column. */
    centered?: boolean
}

export function PageShell({
    nav,
    sidebar,
    children,
    className,
    centered = false,
}: PageShellProps) {
    return (
        <div className="flex h-full min-h-0 flex-col bg-merism-bg text-merism-text">
            <header className="flex h-14 shrink-0 items-center border-b border-[color:var(--merism-hairline)] bg-merism-surface px-6">
                {nav}
            </header>
            <div className="flex min-h-0 flex-1">
                <motion.main
                    initial={{ opacity: 0, y: 4 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{
                        duration: 0.2,
                        ease: [0.22, 0.61, 0.36, 1],
                    }}
                    className={cn(
                        "min-h-0 flex-1 overflow-y-auto p-6",
                        centered && "mx-auto w-full max-w-3xl",
                        className,
                    )}
                >
                    {children}
                </motion.main>
                {sidebar && (
                    <aside className="hidden w-[var(--spacing-merism-sidebar)] shrink-0 border-l border-[color:var(--merism-hairline)] bg-merism-surface p-4 lg:block">
                        {sidebar}
                    </aside>
                )}
            </div>
        </div>
    )
}
