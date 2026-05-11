import * as DialogPrimitive from "@radix-ui/react-dialog"
import { AnimatePresence, motion } from "motion/react"
import { Search } from "lucide-react"
import { useTranslation } from "react-i18next"
import {
    useCallback,
    useEffect,
    useMemo,
    useRef,
    useState,
    type KeyboardEvent,
    type ReactNode,
} from "react"

import { cn } from "../utils/cn"

/**
 * CommandPalette — Cmd+K / Ctrl+K quick-action surface.
 *
 * Patterned after Linear / Raycast: a modal dialog that opens from a
 * keyboard shortcut and offers a fuzzy-searchable list of commands.
 *
 * Usage — mount once near the app root::
 *
 *     <CommandPalette commands={[
 *         { id: "go-home", label: "Go to Home", onRun: () => nav("/") },
 *         ...
 *     ]} />
 *
 * The component owns its open/close state and key binding internally,
 * so callers only need to pass the command list. For programmatic
 * control (e.g. "open palette pre-filtered for studies"), pass
 * ``isOpen`` / ``onOpenChange`` props.
 */

export interface CommandPaletteCommand {
    id: string
    label: string
    /** Optional secondary text shown to the right (keyboard hint, category). */
    hint?: string
    /** Optional icon (20×20 Lucide). */
    icon?: ReactNode
    /** Category label — used for section headings. */
    section?: string
    /** Extra search terms beyond the label. */
    keywords?: string[]
    onRun: () => void
}

export interface CommandPaletteProps {
    commands: CommandPaletteCommand[]
    /** Controlled open state. If omitted, the component opens itself on Cmd+K. */
    isOpen?: boolean
    onOpenChange?: (open: boolean) => void
    placeholder?: string
}

export function CommandPalette({
    commands,
    isOpen: controlledOpen,
    onOpenChange,
    placeholder,
}: CommandPaletteProps): JSX.Element {
    const { t } = useTranslation()
    const effectivePlaceholder = placeholder ?? t("command_palette.placeholder")
    const [uncontrolledOpen, setUncontrolledOpen] = useState(false)
    const open = controlledOpen ?? uncontrolledOpen
    const setOpen = useCallback(
        (next: boolean) => {
            if (onOpenChange) onOpenChange(next)
            else setUncontrolledOpen(next)
        },
        [onOpenChange],
    )

    // Register global Cmd/Ctrl+K toggle.
    useEffect(() => {
        const onKey = (e: globalThis.KeyboardEvent): void => {
            if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
                e.preventDefault()
                setOpen(!open)
            }
        }
        window.addEventListener("keydown", onKey)
        return () => window.removeEventListener("keydown", onKey)
    }, [open, setOpen])

    const [query, setQuery] = useState("")
    const [focusIndex, setFocusIndex] = useState(0)
    const inputRef = useRef<HTMLInputElement>(null)

    // Reset query + focus when opened.
    useEffect(() => {
        if (open) {
            setQuery("")
            setFocusIndex(0)
            window.setTimeout(() => inputRef.current?.focus(), 50)
        }
    }, [open])

    const filtered = useMemo(() => {
        const q = query.trim().toLowerCase()
        if (!q) return commands
        return commands.filter((cmd) => {
            const haystack = [
                cmd.label,
                cmd.section,
                cmd.hint,
                ...(cmd.keywords ?? []),
            ]
                .filter(Boolean)
                .join(" ")
                .toLowerCase()
            return haystack.includes(q)
        })
    }, [commands, query])

    // Keep focus index within filtered bounds.
    useEffect(() => {
        if (focusIndex >= filtered.length) setFocusIndex(0)
    }, [filtered.length, focusIndex])

    const runCommand = useCallback(
        (cmd: CommandPaletteCommand) => {
            setOpen(false)
            // Defer the handler so Dialog finishes closing first.
            window.setTimeout(() => cmd.onRun(), 0)
        },
        [setOpen],
    )

    const onInputKey = useCallback(
        (e: KeyboardEvent<HTMLInputElement>) => {
            if (e.key === "ArrowDown") {
                e.preventDefault()
                setFocusIndex((i) => Math.min(filtered.length - 1, i + 1))
            } else if (e.key === "ArrowUp") {
                e.preventDefault()
                setFocusIndex((i) => Math.max(0, i - 1))
            } else if (e.key === "Enter") {
                e.preventDefault()
                const cmd = filtered[focusIndex]
                if (cmd) runCommand(cmd)
            }
        },
        [filtered, focusIndex, runCommand],
    )

    // Group commands by section for display headings.
    const grouped = useMemo(() => {
        const groups: Array<{ section: string; items: CommandPaletteCommand[] }> = []
        for (const cmd of filtered) {
            const section = cmd.section ?? "Commands"
            const existing = groups.find((g) => g.section === section)
            if (existing) existing.items.push(cmd)
            else groups.push({ section, items: [cmd] })
        }
        return groups
    }, [filtered])

    return (
        <DialogPrimitive.Root open={open} onOpenChange={setOpen}>
            <AnimatePresence>
                {open && (
                    <DialogPrimitive.Portal forceMount>
                        <DialogPrimitive.Overlay asChild>
                            <motion.div
                                className="fixed inset-0 z-[90] bg-[color:var(--merism-text)]/20 backdrop-blur-sm"
                                initial={{ opacity: 0 }}
                                animate={{ opacity: 1 }}
                                exit={{ opacity: 0 }}
                                transition={{ duration: 0.15, ease: [0.22, 0.61, 0.36, 1] }}
                            />
                        </DialogPrimitive.Overlay>
                        <DialogPrimitive.Content asChild>
                            <motion.div
                                className={cn(
                                    "fixed left-1/2 top-[18vh] z-[100] w-[640px] max-w-[calc(100vw-2rem)]",
                                    "-translate-x-1/2 rounded-merism-xl bg-merism-surface shadow-merism-pop ring-1",
                                    "ring-[color:var(--merism-hairline-strong)] outline-none",
                                )}
                                initial={{ opacity: 0, y: -12, scale: 0.98 }}
                                animate={{ opacity: 1, y: 0, scale: 1 }}
                                exit={{ opacity: 0, y: -8, scale: 0.98 }}
                                transition={{ duration: 0.2, ease: [0.22, 0.61, 0.36, 1] }}
                            >
                                <DialogPrimitive.Title className="sr-only">
                                    Command palette
                                </DialogPrimitive.Title>

                                <div className="flex items-center gap-3 border-b border-[color:var(--merism-hairline)] px-4 py-3">
                                    <Search className="h-4 w-4 shrink-0 text-merism-text-subtle" />
                                    <input
                                        ref={inputRef}
                                        value={query}
                                        onChange={(e) => {
                                            setQuery(e.target.value)
                                            setFocusIndex(0)
                                        }}
                                        onKeyDown={onInputKey}
                                        placeholder={effectivePlaceholder}
                                        className="flex-1 bg-transparent text-merism-body text-merism-text placeholder:text-merism-text-subtle focus:outline-none"
                                    />
                                    <kbd className="rounded-merism-sm bg-merism-bg-subtle px-1.5 py-0.5 font-mono text-[10px] text-merism-text-muted">
                                        {t("command_palette.hint_esc")}
                                    </kbd>
                                </div>

                                <div className="max-h-[60vh] overflow-y-auto py-2">
                                    {filtered.length === 0 ? (
                                        <div className="px-4 py-10 text-center text-merism-body-sm text-merism-text-subtle">
                                            {t("command_palette.no_matches", { query })}
                                        </div>
                                    ) : (
                                        grouped.map((group) => (
                                            <div key={group.section} className="mb-2 last:mb-0">
                                                <div className="px-4 pt-1 pb-1 font-mono text-merism-caption uppercase tracking-merism-caps text-merism-text-subtle">
                                                    {group.section}
                                                </div>
                                                {group.items.map((cmd) => {
                                                    const absIndex = filtered.indexOf(cmd)
                                                    const isActive = absIndex === focusIndex
                                                    return (
                                                        <button
                                                            key={cmd.id}
                                                            type="button"
                                                            onMouseEnter={() => setFocusIndex(absIndex)}
                                                            onClick={() => runCommand(cmd)}
                                                            className={cn(
                                                                "flex w-full items-center gap-3 px-4 py-2 text-left text-merism-body-sm transition-colors",
                                                                isActive
                                                                    ? "bg-merism-accent-soft text-merism-text"
                                                                    : "text-merism-text hover:bg-merism-bg-subtle",
                                                            )}
                                                        >
                                                            {cmd.icon && (
                                                                <span className="flex h-5 w-5 shrink-0 items-center justify-center text-merism-text-muted">
                                                                    {cmd.icon}
                                                                </span>
                                                            )}
                                                            <span className="flex-1 truncate">{cmd.label}</span>
                                                            {cmd.hint && (
                                                                <span className="shrink-0 font-mono text-merism-caption text-merism-text-subtle">
                                                                    {cmd.hint}
                                                                </span>
                                                            )}
                                                        </button>
                                                    )
                                                })}
                                            </div>
                                        ))
                                    )}
                                </div>

                                <div className="flex items-center justify-between border-t border-[color:var(--merism-hairline)] px-4 py-2 font-mono text-[10px] uppercase tracking-merism-caps text-merism-text-subtle">
                                    <span>{t("command_palette.footer")}</span>
                                    <span className="flex items-center gap-2">
                                        <kbd className="rounded-merism-sm bg-merism-bg-subtle px-1.5 py-0.5">↑↓</kbd>
                                        {t("command_palette.hint_navigate")}
                                        <kbd className="rounded-merism-sm bg-merism-bg-subtle px-1.5 py-0.5">↵</kbd>
                                        {t("command_palette.hint_run")}
                                    </span>
                                </div>
                            </motion.div>
                        </DialogPrimitive.Content>
                    </DialogPrimitive.Portal>
                )}
            </AnimatePresence>
        </DialogPrimitive.Root>
    )
}
