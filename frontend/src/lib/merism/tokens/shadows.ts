// Elevation / depth tokens.

export const shadows = {
    none: "none",
    sm: "0 1px 2px rgb(0 0 0 / 0.05)",
    md: "0 4px 10px -2px rgb(0 0 0 / 0.08), 0 2px 4px -2px rgb(0 0 0 / 0.04)",
    lg: "0 12px 24px -6px rgb(0 0 0 / 0.10), 0 4px 8px -4px rgb(0 0 0 / 0.05)",
} as const

export type ShadowToken = keyof typeof shadows
