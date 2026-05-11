import type { StorybookConfig } from "@storybook/react-vite"

/**
 * Storybook 10.x — Merism design system explorer.
 *
 * Scope: we show stories for primitives + patterns only. Features
 * (``features/``) should be tested via Vitest or Playwright, not
 * Storybook; stories there create visual noise and drift fast.
 */
const config: StorybookConfig = {
    stories: [
        "../src/lib/merism/**/*.stories.@(ts|tsx|mdx)",
    ],
    addons: [
        "@storybook/addon-a11y",
        "@storybook/addon-vitest",
    ],
    framework: {
        name: "@storybook/react-vite",
        options: {},
    },
    docs: {
        defaultName: "Docs",
    },
    typescript: {
        check: false,
        reactDocgen: "react-docgen-typescript",
    },
}

export default config
