/**
 * Kea context initialization.
 *
 * Plugins — each one matches an entry in ``package.json``:
 *   - router:        URL ↔ actions
 *   - loaders:       async load* actions + *Loading selectors
 *   - subscriptions: value-change listeners
 *   - waitfor:       ``waitForAction`` helper
 *   - forms:         field-level validation for wizards
 *   - localStorage:  persist specific reducers to localStorage
 *
 * Call exactly once at app startup (see :file:`index.tsx`).
 */

import { resetContext } from "kea"
import { formsPlugin } from "kea-forms"
import { loadersPlugin } from "kea-loaders"
import { localStoragePlugin } from "kea-localstorage"
import { routerPlugin } from "kea-router"
import { subscriptionsPlugin } from "kea-subscriptions"
import { waitForPlugin } from "kea-waitfor"

export function initKea(): void {
    resetContext({
        plugins: [
            localStoragePlugin(),
            routerPlugin({
                urlPatternOptions: {
                    segmentValueCharset: "a-zA-Z0-9-_~ %.@()!'|:",
                },
            }),
            formsPlugin,
            loadersPlugin({
                onFailure: ({ error, logic, actionKey }) => {
                    // eslint-disable-next-line no-console
                    console.warn(`[kea] ${logic.pathString}.${actionKey} failed:`, error)
                },
            }),
            subscriptionsPlugin,
            waitForPlugin,
        ],
    })
}
