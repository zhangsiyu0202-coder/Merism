import { ArrowDown, ArrowUp, Minus } from "lucide-react"
import type { ReactNode } from "react"

/**
 * KpiCard — editorial big-number stat.
 *
 * Purpose:
 *   The first visual layer of any research report — the number
 *   the user sees when the page paints. Composition (caption →
 *   giant number → supporting line) is lifted from Google Cloud
 *   Insights, Airbnb Data Portal, and Linear Insights.
 *
 * Variants:
 *   - ``borderless`` (default) — Airbnb-style, separated only by
 *     column gap. Best as a 4-wide row at the top of a report.
 *   - ``card``                — Stripe-style bordered card; use
 *     for sub-sections where structure helps scanability.
 *
 * Number sizes (strict 8pt grid typography):
 *   - ``hero``    72px · dashboard masthead
 *   - ``display`` 48px · default
 *   - ``title``   20px · dense grid variant (8+ KPIs)
 *
 * Trend chip semantic:
 *   - ``up`` arrow   · Coral success by default
 *   - ``down`` arrow · Danger red by default
 *   - ``flat`` minus · muted
 *   Pass ``positive={false}`` to invert (e.g. bounce rate up is
 *   bad — reverse the colour).
 */

export type KpiSize = "hero" | "display" | "title"
export type KpiVariant = "borderless" | "card"

export interface KpiTrend {
    /** Pre-formatted value, e.g. ``"+12%"`` / ``"-4.2s"``. */
    value: string
    direction: "up" | "down" | "flat"
    /** Whether the direction is *semantically* good — flips colours. */
    positive?: boolean
    /** Override label, e.g. ``"vs last month"``. */
    label?: string
}

export interface KpiCardProps {
    /** Uppercase caption above the number, e.g. ``"AVG SESSION TIME"``. */
    label: string
    /** Main value as pre-formatted string — renders with ``font-display``. */
    value: string | number
    /** Line below the number — e.g. ``"across 42 sessions"``. */
    subtitle?: ReactNode
    /** Optional comparison chip. */
    trend?: KpiTrend
    /** Leading icon beside the caption — keep monochrome / lucide. */
    icon?: ReactNode
    size?: KpiSize
    variant?: KpiVariant
    /** Coral vertical rule on the left edge (borderless only). */
    accent?: boolean
    className?: string
}

const NUMBER_SIZE_CLASSES: Record<KpiSize, string> = {
    hero:
        "text-merism-hero leading-[var(--text-merism-hero--line-height)] " +
        "tracking-[var(--text-merism-hero--letter-spacing)]",
    display:
        "text-merism-display leading-[var(--text-merism-display--line-height)] " +
        "tracking-[var(--text-merism-display--letter-spacing)]",
    title:
        "text-merism-title leading-[var(--text-merism-title--line-height)] " +
        "tracking-[var(--text-merism-title--letter-spacing)]",
}

function TrendChip({ trend }: { trend: KpiTrend }): JSX.Element {
    const { direction, value, positive = true, label } = trend
    const Icon = direction === "up" ? ArrowUp : direction === "down" ? ArrowDown : Minus
    // "up" with positive=true OR "down" with positive=false → good (success)
    const isGood = direction === "flat" ? null : (direction === "up") === positive
    const colourClass =
        direction === "flat"
            ? "text-merism-text-subtle"
            : isGood
                ? "text-merism-success"
                : "text-merism-danger"
    return (
        <span
            className={
                "inline-flex items-center gap-1 font-mono text-merism-caption " +
                "tabular-nums " +
                colourClass
            }
        >
            <Icon className="h-3 w-3" aria-hidden="true" />
            <span>{value}</span>
            {label && (
                <span className="text-merism-text-subtle">· {label}</span>
            )}
        </span>
    )
}

export function KpiCard({
    label,
    value,
    subtitle,
    trend,
    icon,
    size = "display",
    variant = "borderless",
    accent = false,
    className,
}: KpiCardProps): JSX.Element {
    const isCard = variant === "card"

    const containerClass =
        (isCard
            ? "rounded-merism-lg bg-merism-surface p-6 " +
              "ring-1 ring-[color:var(--merism-hairline)] shadow-merism-card " +
              "transition-shadow duration-[var(--merism-duration-base)] " +
              "ease-[var(--merism-ease)] hover:shadow-merism-float"
            : accent
                ? "relative pl-6"
                : "") +
        " flex flex-col gap-2" +
        (className ? ` ${className}` : "")

    return (
        <article className={containerClass}>
            {accent && !isCard && (
                <span
                    aria-hidden="true"
                    className="absolute left-0 top-1 h-8 w-[2px] rounded-full bg-merism-accent"
                />
            )}

            <div className="flex items-center gap-2 text-merism-text-subtle">
                {icon && (
                    <span className="text-merism-text-muted" aria-hidden="true">
                        {icon}
                    </span>
                )}
                <span className="font-mono text-merism-caption uppercase tracking-merism-caps">
                    {label}
                </span>
            </div>

            <div
                className={
                    "font-display font-[450] tabular-nums text-merism-text " +
                    NUMBER_SIZE_CLASSES[size]
                }
            >
                {value}
            </div>

            {(subtitle || trend) && (
                <div className="flex flex-wrap items-baseline gap-x-4 gap-y-1">
                    {trend && <TrendChip trend={trend} />}
                    {subtitle && (
                        <span className="text-merism-body-sm leading-[var(--text-merism-body-sm--line-height)] text-merism-text-muted">
                            {subtitle}
                        </span>
                    )}
                </div>
            )}
        </article>
    )
}
