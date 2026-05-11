// Typography tokens. Inter / Geist are eagerly loaded; Plex Mono lazy-loads
// only on the Ask Merism page (per design-system spec Req 4).

export const fontFamily = {
    sans: [
        "Inter Variable",
        "Inter",
        "ui-sans-serif",
        "system-ui",
        "-apple-system",
        "Segoe UI",
        "Roboto",
        "Helvetica Neue",
        "Arial",
        "sans-serif",
    ],
    display: [
        "Geist Variable",
        "Geist",
        "Inter Variable",
        "Inter",
        "ui-sans-serif",
        "system-ui",
        "sans-serif",
    ],
    mono: [
        "IBM Plex Mono",
        "ui-monospace",
        "SFMono-Regular",
        "Menlo",
        "Consolas",
        "monospace",
    ],
} as const

export const fontSize = {
    xs: "0.75rem",
    sm: "0.875rem",
    base: "1rem",
    lg: "1.125rem",
    xl: "1.25rem",
    "2xl": "1.5rem",
    "3xl": "1.875rem",
    "4xl": "2.25rem",
    "5xl": "3rem",
} as const

export const lineHeight = {
    tight: "1.25",
    snug: "1.375",
    normal: "1.5",
    relaxed: "1.625",
    loose: "2",
} as const

export const fontWeight = {
    regular: "400",
    medium: "500",
    semibold: "600",
    bold: "700",
} as const

export const letterSpacing = {
    tight: "-0.025em",
    normal: "0",
    wide: "0.025em",
} as const

// Named type presets, for places that need "use the body text style".
export const typePreset = {
    bodySm: { fontSize: fontSize.sm, lineHeight: lineHeight.normal },
    body: { fontSize: fontSize.base, lineHeight: lineHeight.normal },
    bodyLg: { fontSize: fontSize.lg, lineHeight: lineHeight.relaxed },
    caption: { fontSize: fontSize.xs, lineHeight: lineHeight.normal },
    h1: {
        fontSize: fontSize["3xl"],
        lineHeight: lineHeight.tight,
        fontWeight: fontWeight.semibold,
    },
    h2: {
        fontSize: fontSize["2xl"],
        lineHeight: lineHeight.tight,
        fontWeight: fontWeight.semibold,
    },
    h3: {
        fontSize: fontSize.xl,
        lineHeight: lineHeight.snug,
        fontWeight: fontWeight.semibold,
    },
    label: {
        fontSize: fontSize.sm,
        lineHeight: lineHeight.normal,
        fontWeight: fontWeight.medium,
    },
} as const

export type TypePresetKey = keyof typeof typePreset
