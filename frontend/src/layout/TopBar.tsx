import { useActions, useValues } from "kea";
import { Sparkles } from "lucide-react";
import { router } from "kea-router";

import { sceneLogic } from "~/app/sceneLogic";
import { urls } from "~/app/routes";
import { studyLogic } from "~/features/studies/studyLogic";
import { cn } from "~/lib/merism/utils/cn";

import { sidebarLogic } from "./sidebarLogic";

/**
 * TopBar — thin bar along the top of the app area.
 *
 * Left: mono-voice breadcrumb.
 * Right: Ask Merism toggle (opens the right-side slide-out panel).
 */
export function TopBar({ className }: { className?: string }): JSX.Element {
  const { activeSceneConfig, sceneParams } = useValues(sceneLogic);
  const { sidePanel } = useValues(sidebarLogic);
  const { toggleSidePanel } = useActions(sidebarLogic);
  const isAskOpen = sidePanel.isOpen && sidePanel.tab === "ask";

  return (
    <header
      className={cn(
        "flex h-[var(--spacing-merism-topbar)] shrink-0 items-center gap-3 " +
          "border-b border-[color:var(--merism-hairline)] bg-merism-bg px-6",
        className,
      )}
    >
      <Breadcrumb name={activeSceneConfig.name} params={sceneParams.params} />

      <div className="ml-auto flex items-center gap-2">
        <button
          type="button"
          onClick={() => toggleSidePanel("ask")}
          aria-pressed={isAskOpen}
          title="Ask Merism"
          className={cn(
            "inline-flex items-center gap-2 rounded-merism-md border px-2.5 py-1 text-merism-label",
            "transition-colors duration-[var(--merism-duration-fast)] ease-[var(--merism-ease)]",
            isAskOpen
              ? "border-[color:var(--merism-accent)] bg-merism-accent-soft text-merism-text"
              : "border-[color:var(--merism-hairline-strong)] bg-merism-surface text-merism-text-muted hover:bg-merism-bg-subtle hover:text-merism-text",
          )}
        >
          <Sparkles
            className={cn(
              "h-3.5 w-3.5 shrink-0",
              isAskOpen ? "text-merism-accent" : "text-merism-text-subtle",
            )}
            strokeWidth={1.8}
          />
          <span>Ask</span>
        </button>
      </div>
    </header>
  );
}

function Breadcrumb({
  name,
  params,
}: {
  name: string;
  params: Record<string, string>;
}): JSX.Element {
  const { push } = useActions(router);
  const { study } = useValues(studyLogic);
  const studyId = params["id"];
  const tab = params["tab"];

  const handleWorkspaceClick = (): void => {
    push(urls.home());
  };

  const handleSceneClick = (): void => {
    if (name === "Study") {
      push(urls.home());
    } else if (name === "Insights") {
      push(urls.insights());
    } else if (name === "Reports") {
      push(urls.reports());
    } else if (name === "Repository") {
      push(urls.repository());
    } else if (name === "Settings") {
      push(urls.settings());
    } else if (name === "Ask Merism") {
      push(urls.ask());
    } else if (name === "Inbox") {
      push(urls.inbox());
    }
  };

  const handleStudyClick = (): void => {
    if (studyId) {
      push(urls.study(studyId, "outline"));
    }
  };

  // Determine if segments are clickable (intermediate segments should be clickable)
  const isSceneClickable = !!studyId;
  const isStudyClickable = !!tab;

  const studyDisplayName = study?.name || (studyId ? studyId.slice(0, 8) : "");

  return (
    <nav
      aria-label="Breadcrumb"
      className="flex items-center gap-2 font-mono text-merism-label uppercase tracking-merism-caps text-merism-text-muted"
    >
      <button
        type="button"
        onClick={handleWorkspaceClick}
        className="hover:text-merism-text hover:underline transition-colors focus:outline-none focus:ring-1 focus:ring-merism-accent rounded px-1 -mx-1"
      >
        Workspace
      </button>
      <Divider />
      {isSceneClickable ? (
        <button
          type="button"
          onClick={handleSceneClick}
          className="hover:text-merism-text hover:underline transition-colors focus:outline-none focus:ring-1 focus:ring-merism-accent rounded px-1 -mx-1"
        >
          {name}
        </button>
      ) : (
        <span>{name}</span>
      )}
      {studyId && (
        <>
          <Divider />
          {isStudyClickable ? (
            <button
              type="button"
              onClick={handleStudyClick}
              className="normal-case tracking-normal hover:text-merism-text hover:underline transition-colors focus:outline-none focus:ring-1 focus:ring-merism-accent rounded px-1 -mx-1"
            >
              {studyDisplayName}
            </button>
          ) : (
            <span className="normal-case tracking-normal">
              {studyDisplayName}
            </span>
          )}
        </>
      )}
      {tab && (
        <>
          <Divider />
          <span>{tab}</span>
        </>
      )}
    </nav>
  );
}

function Divider(): JSX.Element {
  return (
    <span aria-hidden="true" className="text-merism-border-strong">
      /
    </span>
  );
}
