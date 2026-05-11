import * as DialogPrimitive from "@radix-ui/react-dialog"
import { forwardRef, type ComponentPropsWithoutRef, type ElementRef } from "react"

import { cn } from "../utils/cn"

export const Dialog = DialogPrimitive.Root
export const DialogTrigger = DialogPrimitive.Trigger
export const DialogPortal = DialogPrimitive.Portal
export const DialogClose = DialogPrimitive.Close

export const DialogOverlay = forwardRef<
    ElementRef<typeof DialogPrimitive.Overlay>,
    ComponentPropsWithoutRef<typeof DialogPrimitive.Overlay>
>(({ className, ...props }, ref) => (
    <DialogPrimitive.Overlay
        ref={ref}
        className={cn(
            "fixed inset-0 z-40 bg-black/40 backdrop-blur-[1px] " +
                "data-[state=open]:animate-in data-[state=closed]:animate-out " +
                "data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0",
            className,
        )}
        {...props}
    />
))
DialogOverlay.displayName = "DialogOverlay"

export interface DialogContentProps
    extends ComponentPropsWithoutRef<typeof DialogPrimitive.Content> {
    /** When false, Escape / overlay click does not close (spec Req 2.6). */
    dismissible?: boolean
}

export const DialogContent = forwardRef<
    ElementRef<typeof DialogPrimitive.Content>,
    DialogContentProps
>(({ className, dismissible = true, onEscapeKeyDown, onPointerDownOutside, ...props }, ref) => (
    <DialogPortal>
        <DialogOverlay />
        <DialogPrimitive.Content
            ref={ref}
            onEscapeKeyDown={(event) => {
                if (!dismissible) event.preventDefault()
                onEscapeKeyDown?.(event)
            }}
            onPointerDownOutside={(event) => {
                if (!dismissible) event.preventDefault()
                onPointerDownOutside?.(event)
            }}
            className={cn(
                "fixed left-1/2 top-1/2 z-50 w-[95vw] max-w-lg -translate-x-1/2 -translate-y-1/2 " +
                    "rounded-merism-lg bg-merism-surface ring-1 ring-[color:var(--merism-hairline)] shadow-merism-card p-6 shadow-merism-lg " +
                    "focus-visible:outline-none",
                className,
            )}
            {...props}
        />
    </DialogPortal>
))
DialogContent.displayName = "DialogContent"

export const DialogTitle = forwardRef<
    ElementRef<typeof DialogPrimitive.Title>,
    ComponentPropsWithoutRef<typeof DialogPrimitive.Title>
>(({ className, ...props }, ref) => (
    <DialogPrimitive.Title
        ref={ref}
        className={cn("text-lg font-semibold leading-tight", className)}
        {...props}
    />
))
DialogTitle.displayName = "DialogTitle"

export const DialogDescription = forwardRef<
    ElementRef<typeof DialogPrimitive.Description>,
    ComponentPropsWithoutRef<typeof DialogPrimitive.Description>
>(({ className, ...props }, ref) => (
    <DialogPrimitive.Description
        ref={ref}
        className={cn("text-sm text-merism-text-muted", className)}
        {...props}
    />
))
DialogDescription.displayName = "DialogDescription"
