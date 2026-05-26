import { Provider as TooltipProvider } from "@radix-ui/react-tooltip";
import type { ReactNode } from "react";

import { ToastProvider } from "~/lib/merism";

import { AppCommandPalette } from "./AppCommandPalette";

/**
 * Providers — app-level React Context wrappers.
 *
 * Kept thin: only things every scene needs. Scene-specific providers
 * (MSW bindings, per-scene contexts) live inside that scene.
 */
export function Providers({ children }: { children: ReactNode }): JSX.Element {
  return (
    <TooltipProvider delayDuration={250} skipDelayDuration={50}>
      <ToastProvider>
        {children}
        <AppCommandPalette />
      </ToastProvider>
    </TooltipProvider>
  );
}
