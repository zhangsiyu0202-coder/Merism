import { render, type RenderOptions, type RenderResult } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { resetContext } from "kea"
import { type ReactElement, type ReactNode } from "react"

import { TooltipProvider } from "~/lib/merism"

/**
 * Shared test `render()` — wraps the UI in every provider a Merism
 * component might need. Tests should import from here, never from
 * `@testing-library/react` directly:
 *
 *     import { render, screen } from "~/test/render"
 *
 *     const { user } = render(<MyComponent />)
 *     await user.click(screen.getByRole("button"))
 *
 * Adding a provider: put it in `Providers` below, document why, add a
 * test that covers the new coupling.
 */

interface MerismRenderResult extends RenderResult {
    user: ReturnType<typeof userEvent.setup>
}

function Providers({ children }: { children: ReactNode }): ReactElement {
    // Reset Kea's global context before each render so logic state doesn't
    // bleed across tests. Equivalent to `resetContext()` in a setupFiles
    // hook but scoped to actually used tests — cheaper.
    resetContext({ createStore: true })

    return <TooltipProvider delayDuration={0}>{children}</TooltipProvider>
}

export function renderWithProviders(
    ui: ReactElement,
    options?: Omit<RenderOptions, "wrapper">,
): MerismRenderResult {
    const user = userEvent.setup()
    const result = render(ui, { wrapper: Providers, ...options })
    return { ...result, user }
}

// Re-export the RTL surface so test files only import from here.
export * from "@testing-library/react"
export { renderWithProviders as render }
