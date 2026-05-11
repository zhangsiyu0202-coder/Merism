import { Component, type ErrorInfo, type ReactNode } from "react"

import { Button } from "~/lib/merism/primitives/Button"

interface State {
    error: Error | null
}

/**
 * ErrorBoundary — React class boundary (can't be a hook).
 *
 * Renders the editorial-style fallback on throws. In dev, ``error``
 * details are printed to console; in prod we keep the message concise
 * and let the user retry by reloading.
 */
export class ErrorBoundary extends Component<{ children: ReactNode }, State> {
    state: State = { error: null }

    static getDerivedStateFromError(error: Error): State {
        return { error }
    }

    override componentDidCatch(error: Error, errorInfo: ErrorInfo): void {
        // eslint-disable-next-line no-console
        console.error("[merism] unhandled scene error:", error, errorInfo)
    }

    reset = (): void => this.setState({ error: null })

    render(): ReactNode {
        if (this.state.error) {
            return (
                <div className="flex min-h-screen w-screen items-center justify-center bg-merism-bg p-6 text-merism-text">
                    <div className="flex max-w-md flex-col gap-4 text-center">
                        <div className="font-mono text-merism-caption uppercase tracking-merism-caps text-merism-text-subtle">
                            Error
                        </div>
                        <h1 className="font-display text-[length:var(--text-merism-headline)] font-[450] tracking-tight">
                            Something didn't render.
                        </h1>
                        <p className="text-merism-body text-merism-text-muted">
                            {this.state.error.message}
                        </p>
                        <div className="mx-auto">
                            <Button onClick={() => window.location.reload()}>Reload</Button>
                        </div>
                    </div>
                </div>
            )
        }
        return this.props.children
    }
}
