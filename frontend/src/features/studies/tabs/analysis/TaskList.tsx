import { ExternalLink } from "lucide-react";

import { Tag } from "~/lib/merism";

import type { TopTask } from "./analysisLogic";

/**
 * TaskList — extracted action TODOs from session insights.
 *
 * Priority maps:  P0 → danger · P1 → accent · P2 → neutral.
 */
export function TaskList({ tasks }: { tasks: TopTask[] }): JSX.Element {
  if (tasks.length === 0) {
    return (
      <div className="flex h-32 items-center justify-center rounded-merism-lg bg-merism-surface text-merism-body-sm text-merism-text-muted shadow-merism-card ring-1 ring-[color:var(--merism-hairline)]">
        No action items extracted yet.
      </div>
    );
  }

  return (
    <ul className="flex flex-col divide-y divide-[color:var(--merism-hairline)] rounded-merism-lg bg-merism-surface shadow-merism-card ring-1 ring-[color:var(--merism-hairline)]">
      {tasks.map((task, i) => (
        <li
          key={`${task.session_id}-${i}`}
          className="group flex items-start gap-4 px-5 py-3"
        >
          <Tag
            variant={_priorityVariant(task.priority)}
            size="sm"
            case="normal"
          >
            {task.priority}
          </Tag>
          <div className="flex min-w-0 flex-1 flex-col gap-1">
            <span className="truncate text-merism-body font-medium text-merism-text">
              {task.title}
            </span>
            <span className="text-merism-caption text-merism-text-muted">
              {task.category} · session{" "}
              <code className="font-mono text-merism-caption">
                {task.session_id.slice(0, 8)}
              </code>
            </span>
          </div>
          {task.evidence_quote_id && (
            <ExternalLink
              className="mt-1 h-4 w-4 shrink-0 text-merism-text-subtle opacity-0 transition-opacity group-hover:opacity-100"
              strokeWidth={1.6}
            />
          )}
        </li>
      ))}
    </ul>
  );
}

function _priorityVariant(
  priority: TopTask["priority"],
): "danger" | "accent" | "neutral" {
  if (priority === "P0") return "danger";
  if (priority === "P1") return "accent";
  return "neutral";
}
