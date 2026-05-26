import { Copy, Eye, Link2 } from "lucide-react";
import { useEffect, useState } from "react";

import { Button } from "~/lib/merism";
import { api } from "~/lib/api";
import type { Study } from "~/types";

/**
 * SharePanel — the single canonical share-URL surface for a Study.
 *
 * Per the 2026-05-20 simplification, every Study auto-creates one
 * ``primary_link`` and we surface that one link here. No "Create link"
 * button, no list of links — Study = one link.
 *
 * Three actions:
 *   - Accepting toggle — flips ``StudyLink.is_active``. Per the
 *     2026-05-23 access-control simplification, this is the **only**
 *     researcher-controlled access switch. ``Study.status=closed`` does
 *     not auto-block the link; researchers explicitly toggle this.
 *   - 复制链接 — copy the full URL to clipboard
 *   - 预览     — open the link with ``?preview=1`` so the researcher
 *                walks the participant flow without writing any data
 */
export default function SharePanel({ study }: { study: Study }): JSX.Element | null {
  const link = study.primary_link ?? null;
  const shareUrl = study.share_url ?? null;

  const [accepting, setAccepting] = useState<boolean>(link?.is_active ?? true);
  const [pending, setPending] = useState(false);
  const [copied, setCopied] = useState(false);

  // Re-sync local state when the study payload reloads (e.g. after a tab
  // switch). Without this, a stale toggle would override server state.
  useEffect(() => {
    setAccepting(link?.is_active ?? true);
  }, [link?.is_active]);

  if (!link || !shareUrl) return null;

  const fullUrl = shareUrl.startsWith("http")
    ? shareUrl
    : `${window.location.origin}${shareUrl}`;

  async function handleCopy(): Promise<void> {
    try {
      await navigator.clipboard.writeText(fullUrl);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1500);
    } catch {
      // Best-effort; clipboard API may be blocked in some browsers.
    }
  }

  function handlePreview(): void {
    const previewUrl = fullUrl.includes("?")
      ? `${fullUrl}&preview=1`
      : `${fullUrl}?preview=1`;
    window.open(previewUrl, "_blank", "noopener");
  }

  async function handleToggle(): Promise<void> {
    if (!link || pending) return;
    const next = !accepting;
    setAccepting(next); // optimistic
    setPending(true);
    try {
      await api.update(`/api/study-links/${link.id}/`, { is_active: next });
    } catch (err) {
      setAccepting(!next); // rollback
      // eslint-disable-next-line no-console
      console.error("study-link.toggle.failed", err);
    } finally {
      setPending(false);
    }
  }

  return (
    <section className="flex items-center gap-3 rounded-merism-lg bg-merism-surface px-4 py-3 shadow-merism-card ring-1 ring-[color:var(--merism-hairline)]">
      <Link2 className="h-4 w-4 shrink-0 text-merism-text-subtle" />
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2 font-mono text-merism-caption uppercase tracking-merism-caps text-merism-text-subtle">
          访谈链接
          <AcceptingSwitch
            accepting={accepting}
            disabled={pending}
            onToggle={handleToggle}
          />
        </div>
        <code
          className={
            "block truncate font-mono text-merism-label " +
            (accepting ? "text-merism-text" : "text-merism-text-subtle line-through")
          }
        >
          {fullUrl}
        </code>
      </div>
      <Button
        variant="ghost"
        size="sm"
        iconLeft={<Copy className="h-4 w-4" />}
        onClick={handleCopy}
      >
        {copied ? "已复制" : "复制链接"}
      </Button>
      <Button
        variant="ghost"
        size="sm"
        iconLeft={<Eye className="h-4 w-4" />}
        onClick={handlePreview}
      >
        预览
      </Button>
    </section>
  );
}

function AcceptingSwitch({
  accepting,
  disabled,
  onToggle,
}: {
  accepting: boolean;
  disabled: boolean;
  onToggle: () => void;
}): JSX.Element {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={accepting}
      aria-label={accepting ? "暂停接收新参与者" : "开始接收新参与者"}
      disabled={disabled}
      onClick={onToggle}
      className={
        "inline-flex h-4 w-7 shrink-0 items-center rounded-full transition-colors " +
        (accepting
          ? "bg-merism-accent"
          : "bg-merism-bg-subtle ring-1 ring-[color:var(--merism-hairline-strong)]") +
        (disabled ? " opacity-50 cursor-wait" : " cursor-pointer")
      }
    >
      <span
        className={
          "inline-block h-3 w-3 rounded-full bg-white shadow transition-transform " +
          (accepting ? "translate-x-3.5" : "translate-x-0.5")
        }
      />
      <span className="sr-only">
        {accepting ? "正在接收新参与者" : "已暂停"}
      </span>
    </button>
  );
}
