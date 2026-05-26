// Spacing scale — 4px grid. Custom `merism-*` steps for compact layouts
// (e.g., Interview Room canvas gutters) live alongside standard Tailwind-ish
// steps.

export const spacing = {
  "0": "0",
  px: "1px",
  "0.5": "0.125rem",
  "1": "0.25rem",
  "2": "0.5rem",
  "3": "0.75rem",
  "4": "1rem",
  "5": "1.25rem",
  "6": "1.5rem",
  "8": "2rem",
  "10": "2.5rem",
  "12": "3rem",
  "16": "4rem",
  "20": "5rem",
  "24": "6rem",
  "32": "8rem",
  // Merism-specific named steps:
  "merism-gutter": "1.25rem",
  "merism-canvas-y": "3.5rem",
  "merism-sidebar": "22rem",
} as const;

export const space = spacing; // alias for readability
