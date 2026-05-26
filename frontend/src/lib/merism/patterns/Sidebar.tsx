import * as DialogPrimitive from "@radix-ui/react-dialog";
import { X } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { type ReactNode } from "react";

import { cn } from "../utils/cn";

/**
 * Sidebar — right-side drawer.
 *
 * Built on Radix Dialog's non-modal mode (``modal=false``) so it layers
 * over the main view without blocking scroll / clicks behind it. Used by
 * Outline Review Agent (Outline tab) and Custom Report (Analysis page).
 *
 * Motion: 200 ms slide-in from right, respects ``prefers-reduced-motion``
 * via the global CSS rule in globals.css.
 */

export interface SidebarProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: ReactNode;
  description?: ReactNode;
  children: ReactNode;
  /** When false, Escape / X button is suppressed. Defaults to true. */
  dismissible?: boolean;
  /** Pixel width of the sidebar. Default 22rem (= --spacing-merism-sidebar). */
  width?: string;
  className?: string;
}

export function Sidebar({
  open,
  onOpenChange,
  title,
  description,
  children,
  dismissible = true,
  width = "22rem",
  className,
}: SidebarProps) {
  return (
    <DialogPrimitive.Root open={open} onOpenChange={onOpenChange} modal={false}>
      <AnimatePresence>
        {open && (
          <DialogPrimitive.Portal forceMount>
            <DialogPrimitive.Content
              asChild
              onEscapeKeyDown={(e) => !dismissible && e.preventDefault()}
              onPointerDownOutside={(e) => e.preventDefault()}
              onInteractOutside={(e) => e.preventDefault()}
            >
              <motion.aside
                initial={{ x: "100%" }}
                animate={{ x: 0 }}
                exit={{ x: "100%" }}
                transition={{
                  duration: 0.2,
                  ease: [0.22, 0.61, 0.36, 1],
                }}
                style={{ width }}
                className={cn(
                  "fixed inset-y-0 right-0 z-40 flex flex-col border-l " +
                    "border-merism-border bg-merism-surface shadow-merism-lg " +
                    "focus-visible:outline-none",
                  className,
                )}
              >
                <header className="flex shrink-0 items-start justify-between gap-3 border-b border-[color:var(--merism-hairline)] px-4 py-3">
                  <div className="flex min-w-0 flex-col gap-1">
                    <DialogPrimitive.Title className="truncate text-sm font-semibold text-merism-text">
                      {title}
                    </DialogPrimitive.Title>
                    {description && (
                      <DialogPrimitive.Description className="truncate text-xs text-merism-text-muted">
                        {description}
                      </DialogPrimitive.Description>
                    )}
                  </div>
                  {dismissible && (
                    <DialogPrimitive.Close asChild>
                      <button
                        type="button"
                        aria-label="Close sidebar"
                        className="rounded-merism-md p-1 text-merism-text-muted hover:bg-merism-bg-subtle hover:text-merism-text focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-merism-accent/60"
                      >
                        <X className="h-4 w-4" />
                      </button>
                    </DialogPrimitive.Close>
                  )}
                </header>

                <div className="flex min-h-0 flex-1 flex-col">{children}</div>
              </motion.aside>
            </DialogPrimitive.Content>
          </DialogPrimitive.Portal>
        )}
      </AnimatePresence>
    </DialogPrimitive.Root>
  );
}
