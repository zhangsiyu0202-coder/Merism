import type { HTMLAttributes } from "react"

import { cn } from "../utils/cn"

/**
 * SectionLabel — the small uppercase / mono-tracked label that
 * announces a list section, a nav group, or a data-table column group.
 *
 * Google Cloud / Stripe / Cohere all converge on this treatment:
 *   ``font-mono text-merism-caption uppercase tracking-merism-caps text-subtle``
 *
 * Use SPARINGLY; overuse defeats the editorial intent.
 */

export function SectionLabel({
    className,
    ...props
}: HTMLAttributes<HTMLDivElement>): JSX.Element {
    return (
        <div
            {...props}
            className={cn(
                "font-mono text-merism-caption uppercase tracking-merism-caps text-merism-text-subtle",
                className,
            )}
        />
    )
}
