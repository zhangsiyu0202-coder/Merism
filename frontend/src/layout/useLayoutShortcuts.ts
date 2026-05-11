import { useActions } from "kea"
import { useEffect } from "react"

import { sidebarLogic } from "./sidebarLogic"

/**
 * useLayoutShortcuts — global layout keyboard shortcuts.
 *
 * ⌘/ (Ctrl+/ on Windows)  toggle sidebar collapse
 * ⌘. (Ctrl+. on Windows)  toggle Ask Merism side panel
 *
 * Ignored when the user is focused in an input / textarea / contenteditable —
 * avoid hijacking typing.
 */
export function useLayoutShortcuts(): void {
    const { toggleCollapsed, toggleSidePanel } = useActions(sidebarLogic)

    useEffect(() => {
        const isTypingContext = (target: EventTarget | null): boolean => {
            if (!(target instanceof HTMLElement)) return false
            const tag = target.tagName
            if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return true
            if (target.isContentEditable) return true
            return false
        }

        const onKeyDown = (e: KeyboardEvent): void => {
            // Any platform: Cmd on mac, Ctrl on win/linux
            const hasModifier = e.metaKey || e.ctrlKey
            if (!hasModifier) return
            if (isTypingContext(e.target)) return

            if (e.key === "/") {
                e.preventDefault()
                toggleCollapsed()
            } else if (e.key === ".") {
                e.preventDefault()
                toggleSidePanel("ask")
            }
        }

        window.addEventListener("keydown", onKeyDown)
        return () => window.removeEventListener("keydown", onKeyDown)
    }, [toggleCollapsed, toggleSidePanel])
}
