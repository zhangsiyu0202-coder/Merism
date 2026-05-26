/**
 * Ambient module declarations for non-TS imports so ``tsc --noEmit``
 * doesn't complain about side-effectful CSS imports.
 */

declare module "*.css" {
  const content: string;
  export default content;
}

declare module "@fontsource/*/*.css" {
  const content: string;
  export default content;
}

// Vite ?raw suffix — string contents of the file at build time.
declare module "*?raw" {
  const content: string;
  export default content;
}

// SVG default import as URL string (Vite's default behaviour).
declare module "*.svg" {
  const content: string;
  export default content;
}
