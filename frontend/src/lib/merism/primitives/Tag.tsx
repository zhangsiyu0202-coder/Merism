import { cva, type VariantProps } from "class-variance-authority"
import { X } from "lucide-react"
import type { HTMLAttributes, ReactNode } from "react"
import { forwardRef } from "react"

import { cn } from "../utils/cn"

/**
 * Tag — status chip with a unified material contract.
 *
 * 2026-05-10 Stripe-algorithm rewrite:
 *
 *   BEFORE (pastel mistake)            AFTER (alpha-core)
 *   ─────────────────────────────────────────────────────────
 *   bg = arbitrary light tint          bg = core colour @ 8-9 % alpha
 *   fg = same-hue darker tint          fg = same core colour @ full
 *   outline = solid 1 px gray          edge = unified inset shadow
 *                                             rgba(15,23,42,0.04)
 *   dot = 6 px (competing w/ type)     dot = 5 px (subordinate)
 *   font = medium                      font = medium (kept)
 *   tracking = normal                  tracking = normal (kept)
 *   h-6 · px-3 · gap-6                 h-6 · px-[10px] · gap-[6px]
 *
 * Why single-colour cores:
 *   Pastel fills (what we had) can't transmit the underlying
 *   surface. Alpha-core fills let the Slate background tint through
 *   so chips feel like *annotations on paper* instead of stickers
 *   pasted on top — that's the Outset.ai signature.
 *
 * Edge rule:
 *   Every variant (including the previously-inconsistent ``outline``
 *   and ``inverse``) now shares ONE edge treatment:
 *   ``box-shadow: inset 0 0 0 1px rgba(15,23,42,0.04)``. The variant
 *   colour owns the surface; the edge is a systemic constant.
 */

const tagVariants = cva(
    // BASE
    "inline-flex shrink-0 items-center whitespace-nowrap " +
        "rounded-merism-full font-sans font-medium antialiased " +
        "tabular-nums tracking-normal " +
        "[-webkit-font-smoothing:antialiased] [-moz-osx-font-smoothing:grayscale] " +
        // Unified 1 px inset edge — same for every variant
        "shadow-[var(--merism-status-edge)]",
    {
        variants: {
            variant: {
                // ALPHA-CORE VARIANTS — bg is always the matching 8-9% alpha
                neutral:
                    "bg-[color:var(--merism-status-neutral-bg)] " +
                    "text-[color:var(--merism-status-neutral)]",
                accent:
                    "bg-[color:var(--merism-status-accent-bg)] " +
                    "text-[color:var(--merism-status-accent)]",
                success:
                    "bg-[color:var(--merism-status-success-bg)] " +
                    "text-[color:var(--merism-status-success)]",
                warning:
                    "bg-[color:var(--merism-status-warning-bg)] " +
                    "text-[color:var(--merism-status-warning)]",
                danger:
                    "bg-[color:var(--merism-status-danger-bg)] " +
                    "text-[color:var(--merism-status-danger)]",
                info:
                    "bg-[color:var(--merism-status-info-bg)] " +
                    "text-[color:var(--merism-status-info)]",

                // OUTLINE — transparent bg, neutral text, SAME inset edge
                // (no more solid gray border; the systemic edge does the work).
                outline:
                    "bg-transparent text-[color:var(--merism-status-neutral)]",

                // GLASS (Outset) — translucent surface + backdrop blur
                glass:
                    "bg-white/55 text-[color:var(--merism-text)] " +
                    "backdrop-blur-[12px] " +
                    "dark:bg-white/10",
            },
            size: {
                // h-5 · 20 px · dense filter chip
                sm: "h-5 gap-1 px-2 text-[11px]",
                // h-6 · 24 px · DEFAULT
                md: "h-6 gap-[6px] px-[10px] text-[12px]",
                // h-7 · 28 px · prominent status
                lg: "h-7 gap-2 px-3 text-[13px]",
            },
            case: {
                capitalize: "capitalize",
                normal: "normal-case",
            },
        },
        defaultVariants: {
            variant: "neutral",
            size: "md",
            case: "capitalize",
        },
    },
)

export interface TagProps
    extends Omit<HTMLAttributes<HTMLSpanElement>, "color">,
        VariantProps<typeof tagVariants> {
    /**
     * Render a 5 px status dot before the text, in the same colour
     * as the text. Defaults to ``true`` for semantic variants and
     * ``false`` for structural ones (neutral / outline / glass).
     */
    withDot?: boolean
    /** Leading icon slot (replaces the dot when present). */
    icon?: ReactNode
    removable?: boolean
    onRemove?: () => void
}

const SEMANTIC_VARIANTS = new Set([
    "accent",
    "success",
    "warning",
    "danger",
    "info",
])

export const Tag = forwardRef<HTMLSpanElement, TagProps>(
    (
        {
            className,
            variant,
            size,
            case: caseProp,
            withDot,
            icon,
            removable,
            onRemove,
            children,
            ...props
        },
        ref,
    ) => {
        const resolvedDot =
            withDot ?? SEMANTIC_VARIANTS.has(variant ?? "neutral")

        return (
            <span
                ref={ref}
                className={cn(
                    tagVariants({ variant, size, case: caseProp }),
                    className,
                )}
                {...props}
            >
                {icon ? (
                    <span
                        aria-hidden="true"
                        className="inline-flex shrink-0 items-center"
                    >
                        {icon}
                    </span>
                ) : resolvedDot ? (
                    <span
                        aria-hidden="true"
                        // 5 px dot. Sub-grid is deliberate for this micro
                        // component — the systemic 4pt rule holds elsewhere.
                        className="inline-block h-[5px] w-[5px] shrink-0 rounded-full bg-current"
                    />
                ) : null}

                <span className="truncate">{children}</span>

                {removable && (
                    <button
                        type="button"
                        aria-label="Remove"
                        onClick={onRemove}
                        className={
                            "-mr-1 ml-1 inline-flex h-3 w-3 shrink-0 items-center justify-center " +
                            "rounded-merism-full opacity-60 transition-opacity " +
                            "duration-[var(--merism-duration-fast)] hover:opacity-100"
                        }
                    >
                        <X className="h-3 w-3" strokeWidth={2.2} />
                    </button>
                )}
            </span>
        )
    },
)

Tag.displayName = "Tag"

export { tagVariants }
