import { useActions, useValues } from "kea";
import { CheckCircle2, FileText, Flag } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import { Illustration, PageTopBar, Tag } from "~/lib/merism";

import { inboxLogic, type InboxItem as InboxItemType } from "./inboxLogic";

type InboxTab = "all" | "unread" | "flagged";

/**
 * InboxPage — researcher's inbox (PRODUCT.md §3.8).
 *
 * Items are written server-side by signal handlers in
 * :mod:`merism.conductor.inbox_signals`. The page just renders them.
 */
export default function InboxPage(): JSX.Element {
  const { t } = useTranslation();
  const [tab, setTab] = useState<InboxTab>("all");
  const { items, itemsLoading } = useValues(inboxLogic);
  const { markRead } = useActions(inboxLogic);

  const tabs = [
    { value: "all", label: "All" },
    { value: "unread", label: "Unread" },
  ];

  const filtered =
    tab === "unread" ? items.filter((it) => it.read_by.length === 0) : items;

  return (
    <div className="flex flex-col gap-8">
      <PageTopBar
        title={t("inbox.title")}
        lede={t("inbox.lede")}
        tabs={tabs}
        activeTab={tab}
        onTabChange={(v) => setTab(v as InboxTab)}
      />

      {itemsLoading && items.length === 0 ? (
        <div className="rounded-merism-lg bg-merism-surface p-6 text-center text-merism-body-sm text-merism-text-muted shadow-merism-card ring-1 ring-[color:var(--merism-hairline)]">
          Loading inbox…
        </div>
      ) : filtered.length === 0 ? (
        <EmptyState />
      ) : (
        <ul className="flex flex-col gap-3">
          {filtered.map((item) => (
            <InboxRow
              key={item.id}
              item={item}
              onRead={() => markRead(item.id)}
            />
          ))}
        </ul>
      )}
    </div>
  );
}

function InboxRow({
  item,
  onRead,
}: {
  item: InboxItemType;
  onRead: () => void;
}): JSX.Element {
  const unread = item.read_by.length === 0;
  const Icon = _iconFor(item.kind);

  return (
    <li
      className={`flex items-start gap-4 rounded-merism-lg px-5 py-4 shadow-merism-card ring-1 ring-[color:var(--merism-hairline)] transition-colors ${
        unread
          ? "bg-merism-surface"
          : "bg-merism-surface/70 text-merism-text-muted"
      }`}
    >
      <div className="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-merism-md bg-merism-bg-subtle text-merism-text">
        <Icon className="h-4 w-4" />
      </div>
      <div className="flex flex-1 flex-col gap-1">
        <div className="flex items-baseline gap-2">
          <span className="font-medium text-merism-body text-merism-text">
            {item.title}
          </span>
          {unread && (
            <Tag variant="accent" size="sm">
              new
            </Tag>
          )}
        </div>
        {item.body && (
          <p className="text-merism-body-sm text-merism-text-muted">
            {item.body}
          </p>
        )}
        <span className="font-mono text-merism-caption text-merism-text-subtle">
          {new Date(item.created_at).toLocaleString()}
        </span>
      </div>
      {unread && (
        <button
          type="button"
          onClick={onRead}
          className="rounded-merism-md px-3 py-1 text-merism-body-sm text-merism-text-muted transition-colors hover:bg-merism-bg-subtle hover:text-merism-text"
        >
          Mark read
        </button>
      )}
    </li>
  );
}

function _iconFor(kind: InboxItemType["kind"]): typeof CheckCircle2 {
  if (kind === "session_completed") return CheckCircle2;
  if (kind === "insight_ready") return FileText;
  return Flag;
}

function EmptyState(): JSX.Element {
  const { t } = useTranslation();
  return (
    <div className="mx-auto flex max-w-md flex-col items-center gap-6 rounded-merism-lg bg-merism-surface p-12 text-center shadow-merism-card ring-1 ring-[color:var(--merism-hairline)]">
      <Illustration name="chill-time" size="xl" className="text-merism-text" />
      <div className="flex flex-col gap-2">
        <h2 className="font-display text-merism-h2 font-[450] text-merism-text">
          {t("inbox.empty_title")}
        </h2>
        <p className="text-merism-body text-merism-text-muted">
          {t("inbox.empty_body")}
        </p>
      </div>
    </div>
  );
}
