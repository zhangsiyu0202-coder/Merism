import * as ToastPrimitive from "@radix-ui/react-toast"
import { X } from "lucide-react"
import {
    createContext,
    useCallback,
    useContext,
    useMemo,
    useState,
    type ReactNode,
} from "react"

import { cn } from "../utils/cn"

/**
 * Toast — notification primitive.
 *
 * Usage::
 *
 *     const { toast } = useToast()
 *     toast({ title: "Saved", tone: "success" })
 *
 * Tones map to the same status palette the Tag primitive uses, so
 * notifications match the rest of the system visually.
 *
 * Motion: slides in from top-right, stacks up to 4 visible. Auto-
 * dismiss after 4.5 s; hover on a toast pauses its countdown
 * (Radix default).
 */

export type ToastTone = "neutral" | "success" | "warning" | "danger" | "info"

export interface ToastInput {
    title: string
    description?: string
    tone?: ToastTone
    /** Override default (4500 ms). Use ``Infinity`` for sticky toasts. */
    durationMs?: number
}

interface ToastRecord extends ToastInput {
    id: string
}

interface ToastContextValue {
    toast: (input: ToastInput) => void
}

const ToastContext = createContext<ToastContextValue | null>(null)

export function useToast(): ToastContextValue {
    const ctx = useContext(ToastContext)
    if (!ctx) {
        // Non-provider fallback: silent no-op so calling sites don't crash.
        // Apps that want to hear about missing providers should wrap the
        // tree in <ToastProvider> at the root (see app/providers.tsx).
        return { toast: () => undefined }
    }
    return ctx
}

export function ToastProvider({ children }: { children: ReactNode }): JSX.Element {
    const [items, setItems] = useState<ToastRecord[]>([])

    const toast = useCallback((input: ToastInput) => {
        const id = Math.random().toString(36).slice(2, 10)
        setItems((prev) => [...prev, { ...input, id }])
    }, [])

    const dismiss = useCallback((id: string) => {
        setItems((prev) => prev.filter((t) => t.id !== id))
    }, [])

    const value = useMemo(() => ({ toast }), [toast])

    return (
        <ToastContext.Provider value={value}>
            <ToastPrimitive.Provider swipeDirection="right" duration={4500}>
                {children}
                {items.map((item) => (
                    <ToastItem key={item.id} record={item} onDismiss={dismiss} />
                ))}
                <ToastPrimitive.Viewport
                    className={cn(
                        "fixed top-4 right-4 z-[100] flex w-96 max-w-[calc(100vw-2rem)]",
                        "flex-col gap-2 outline-none",
                    )}
                />
            </ToastPrimitive.Provider>
        </ToastContext.Provider>
    )
}

// ── Single toast row ────────────────────────────────────

const TONE_CLASSES: Record<ToastTone, string> = {
    neutral: "bg-merism-surface ring-[color:var(--merism-hairline-strong)]",
    success:
        "bg-[color:var(--merism-status-success-bg)] ring-[color:var(--merism-status-success)]/30",
    warning:
        "bg-[color:var(--merism-status-warning-bg)] ring-[color:var(--merism-status-warning)]/30",
    danger:
        "bg-[color:var(--merism-status-danger-bg)] ring-[color:var(--merism-status-danger)]/30",
    info: "bg-[color:var(--merism-status-info-bg)] ring-[color:var(--merism-status-info)]/30",
}

const TONE_DOT_COLOURS: Record<ToastTone, string> = {
    neutral: "bg-merism-text-subtle",
    success: "bg-[color:var(--merism-status-success)]",
    warning: "bg-[color:var(--merism-status-warning)]",
    danger: "bg-[color:var(--merism-status-danger)]",
    info: "bg-[color:var(--merism-status-info)]",
}

function ToastItem({
    record,
    onDismiss,
}: {
    record: ToastRecord
    onDismiss: (id: string) => void
}): JSX.Element {
    const tone: ToastTone = record.tone ?? "neutral"
    return (
        <ToastPrimitive.Root
            duration={record.durationMs ?? 4500}
            onOpenChange={(open) => {
                if (!open) onDismiss(record.id)
            }}
            className={cn(
                "flex items-start gap-3 rounded-merism-lg px-4 py-3 shadow-merism-float ring-1",
                "data-[state=open]:animate-in data-[state=closed]:animate-out",
                "data-[state=open]:slide-in-from-right-full",
                "data-[state=closed]:fade-out",
                TONE_CLASSES[tone],
            )}
        >
            <span
                aria-hidden="true"
                className={cn(
                    "mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full",
                    TONE_DOT_COLOURS[tone],
                )}
            />
            <div className="flex min-w-0 flex-1 flex-col gap-0.5">
                <ToastPrimitive.Title className="text-merism-body-sm font-medium text-merism-text">
                    {record.title}
                </ToastPrimitive.Title>
                {record.description && (
                    <ToastPrimitive.Description className="text-merism-caption text-merism-text-muted">
                        {record.description}
                    </ToastPrimitive.Description>
                )}
            </div>
            <ToastPrimitive.Close
                aria-label="Close"
                className="flex h-6 w-6 shrink-0 items-center justify-center rounded-merism-md text-merism-text-subtle transition-colors hover:bg-merism-bg-subtle hover:text-merism-text"
            >
                <X className="h-3.5 w-3.5" />
            </ToastPrimitive.Close>
        </ToastPrimitive.Root>
    )
}
