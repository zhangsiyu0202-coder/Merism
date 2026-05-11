import * as TooltipPrimitive from "@radix-ui/react-tooltip"
import { forwardRef, type ComponentPropsWithoutRef, type ElementRef } from "react"

import { cn } from "../utils/cn"

/**
 * Tooltip — thin wrapper around Radix. The Provider must be mounted once near
 * the app root (see src/app/AppShell.tsx).
 */
export const TooltipProvider = TooltipPrimitive.Provider
export const TooltipRoot = TooltipPrimitive.Root
export const TooltipTrigger = TooltipPrimitive.Trigger

export const TooltipContent = forwardRef<
    ElementRef<typeof TooltipPrimitive.Content>,
    ComponentPropsWithoutRef<typeof TooltipPrimitive.Content>
>(({ className, sideOffset = 6, ...props }, ref) => (
    <TooltipPrimitive.Portal>
        <TooltipPrimitive.Content
            ref={ref}
            sideOffset={sideOffset}
            className={cn(
                "z-50 rounded-merism-md bg-merism-text px-2 py-1 text-xs text-merism-surface shadow-merism-md",
                className,
            )}
            {...props}
        />
    </TooltipPrimitive.Portal>
))
TooltipContent.displayName = "TooltipContent"

/** Convenience: wrap a child in a Trigger + Content. */
export interface TooltipProps {
    label: string
    children: React.ReactNode
}
export function Tooltip({ label, children }: TooltipProps) {
    return (
        <TooltipRoot>
            <TooltipTrigger asChild>{children}</TooltipTrigger>
            <TooltipContent>{label}</TooltipContent>
        </TooltipRoot>
    )
}
