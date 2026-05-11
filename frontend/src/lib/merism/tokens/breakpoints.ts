// Design system breakpoints.
// Match Tailwind defaults per design-system spec Req 1.2 so responsive
// utilities feel natural to developers who know Tailwind.

export const breakpoints = {
    sm: "640px",
    md: "768px",
    lg: "1024px",
    xl: "1280px",
    "2xl": "1536px",
} as const

export type Breakpoint = keyof typeof breakpoints
