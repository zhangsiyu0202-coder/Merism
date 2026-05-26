import type { ReactNode } from "react";

import { AskSidePanel } from "./AskSidePanel";
import { NavigationSidebar } from "./NavigationSidebar";
import { SidePanel } from "./SidePanel";
import { TopBar } from "./TopBar";
import { useLayoutShortcuts } from "./useLayoutShortcuts";

/**
 * AppLayout — researcher chrome: left sidebar + topbar + content + right side panel.
 *
 * Layout interactions adopted from PostHog (kept Merism's visuals):
 *   - Left sidebar collapses/expands with 100ms width transition
 *   - Right side panel slides in with 100ms width transition
 *   - Keyboard shortcuts: ⌘/ toggles sidebar, ⌘. toggles Ask panel
 */
export function AppLayout({ children }: { children: ReactNode }): JSX.Element {
  useLayoutShortcuts();

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-merism-bg text-merism-text">
      <NavigationSidebar />
      <div className="flex min-w-0 flex-1 flex-col">
        <TopBar />
        <main className="flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden">
          <div className="flex min-h-0 w-full flex-1 flex-col overflow-y-auto px-[var(--spacing-merism-gutter)] pb-6 pt-6 [&>*]:min-h-0 [&>*]:flex-1">
            {children}
          </div>
        </main>
      </div>
      <SidePanel>
        <AskSidePanel />
      </SidePanel>
    </div>
  );
}
