import chillTime from "./svg/chill-time.svg?raw"
import fastInternet from "./svg/fast-internet.svg?raw"
import flag from "./svg/flag.svg?raw"
import jumping from "./svg/jumping.svg?raw"
import loadingTime from "./svg/loading-time.svg?raw"
import painting from "./svg/painting.svg?raw"
import peace from "./svg/peace.svg?raw"
import planningATrip from "./svg/planning-a-trip.svg?raw"

import { cn } from "../utils/cn"

/**
 * Illustration — hand-drawn monochrome SVGs (Notioly pack).
 *
 * Every source SVG has had its base fill rewritten from ``#231f20``
 * to ``currentColor`` at import time, so the caller controls tone
 * via any ``text-*`` utility. Opacity layers inside the SVG stay
 * intact — those give the illustration its depth.
 *
 * Usage::
 *
 *     <Illustration name="planning-a-trip" size="lg" className="text-merism-accent" />
 *
 * Size tokens snap to the 8pt grid:
 *   sm  96  (h-24)
 *   md  128 (h-32)
 *   lg  192 (h-48)
 *   xl  256 (h-64)
 *   2xl 320 (h-80)
 *
 * Attribution: illustrations are from the Notioly free pack
 * (https://notioly.com/) — MIT-style, free for commercial use.
 */

export const ILLUSTRATIONS = {
    "chill-time": chillTime,
    "fast-internet": fastInternet,
    flag,
    jumping,
    "loading-time": loadingTime,
    painting,
    peace,
    "planning-a-trip": planningATrip,
} as const

export type IllustrationName = keyof typeof ILLUSTRATIONS

export type IllustrationSize = "sm" | "md" | "lg" | "xl" | "2xl"

const SIZE_CLASSES: Record<IllustrationSize, string> = {
    sm: "h-24 w-24",
    md: "h-32 w-32",
    lg: "h-48 w-48",
    xl: "h-64 w-64",
    "2xl": "h-80 w-80",
}

export interface IllustrationProps {
    name: IllustrationName
    size?: IllustrationSize
    /** Hidden from AT by default (decorative); pass ``label`` to make it meaningful. */
    label?: string
    className?: string
}

export function Illustration({
    name,
    size = "md",
    label,
    className,
}: IllustrationProps): JSX.Element {
    const svg = ILLUSTRATIONS[name]
    return (
        <div
            role={label ? "img" : undefined}
            aria-label={label}
            aria-hidden={label ? undefined : true}
            className={cn(
                // Inner <svg> inherits via currentColor + width/height 100%.
                "shrink-0 [&_svg]:h-full [&_svg]:w-full",
                SIZE_CLASSES[size],
                className,
            )}
            dangerouslySetInnerHTML={{ __html: svg }}
        />
    )
}
