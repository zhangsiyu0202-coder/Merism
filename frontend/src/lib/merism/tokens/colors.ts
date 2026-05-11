// Color tokens.
//
// Three layers:
//   1. slate          — neutral grey ramp (50-950)
//   2. functional     — accent / danger / success / warning scales
//   3. semantic       — semantic tokens the CSS variable bridge uses
//
// Only semantic tokens are consumed by primitives. The scales exist so
// future themes (e.g. white-label) can pick different shades without
// rewriting primitives.

export const slate = {
    50: "#F8FAFC",
    100: "#F1F5F9",
    200: "#E2E8F0",
    300: "#CBD5E1",
    400: "#94A3B8",
    500: "#64748B",
    600: "#475569",
    700: "#334155",
    800: "#1E293B",
    900: "#0F172A",
    950: "#020617",
} as const

export const functional = {
    accent: {
        50: "#F0F4FF",
        100: "#E0E8FE",
        500: "#5468FF",
        600: "#4052E5",
        700: "#3142C2",
    },
    danger: {
        50: "#FEF2F2",
        500: "#DC2626",
        600: "#B91C1C",
    },
    success: {
        50: "#ECFDF5",
        500: "#10B981",
        600: "#059669",
    },
    warning: {
        50: "#FFFBEB",
        500: "#F59E0B",
        600: "#D97706",
    },
    quote: {
        50: "#FAF5FF",
        500: "#8B5CF6",
    },
} as const

// Semantic tokens — light mode. Names mirror the CSS variables under :root.
export const semantic = {
    bg: slate[50],
    bgSubtle: slate[100],
    surface: "#FFFFFF",
    text: slate[900],
    textMuted: slate[500],
    border: slate[200],
    accent: functional.accent[500],
    accentForeground: "#FFFFFF",
    danger: functional.danger[500],
    success: functional.success[500],
    warning: functional.warning[500],
    quote: functional.quote[500],
} as const

// Semantic tokens — dark mode. Names mirror the CSS variables under html.dark.
export const semanticDark = {
    bg: slate[950],
    bgSubtle: slate[900],
    surface: slate[800],
    text: slate[50],
    textMuted: slate[400],
    border: slate[700],
    accent: functional.accent[500],
    accentForeground: "#FFFFFF",
    danger: functional.danger[500],
    success: functional.success[500],
    warning: functional.warning[500],
    quote: functional.quote[500],
} as const

export type SemanticColorToken = keyof typeof semantic
