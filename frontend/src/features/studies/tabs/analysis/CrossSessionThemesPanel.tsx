import { useEffect, useState } from "react";

import { api } from "~/lib/api";
import { SectionLabel, Tag } from "~/lib/merism";

import type { components } from "~/generated/api";

type Theme = components["schemas"]["Theme"];

interface Props {
  studyId: string;
}

/**
 * CrossSessionThemesPanel — HDBSCAN-clustered themes across sessions.
 *
 * Distinct from the existing legacy ``ThemeDistributionChart`` (which
 * reads quote-level tags). This reads the new /api/themes/ endpoint
 * backed by the HDBSCAN clusterer.
 */
export function CrossSessionThemesPanel({ studyId }: Props): JSX.Element {
  const [themes, setThemes] = useState<Theme[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    api
      .get<{ results: Theme[] }>("/api/themes/", { study: studyId })
      .then((r) => setThemes(r.results ?? (r as unknown as Theme[])))
      .finally(() => setLoading(false));
  }, [studyId]);

  if (loading) {
    return (
      <p className="text-merism-text-muted text-merism-body-sm">
        Loading themes…
      </p>
    );
  }

  if (themes.length === 0) {
    return (
      <div className="rounded-merism-lg border border-merism-border bg-merism-surface p-6">
        <p className="text-merism-body text-merism-text-muted">
          No cross-session themes yet. Themes emerge after 8+ quotes have been
          extracted across multiple sessions.
        </p>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-3">
      <SectionLabel>Cross-session themes</SectionLabel>
      <p className="text-merism-body-sm text-merism-text-muted">
        Patterns emerging from semantic clustering of quotes across all
        completed sessions. Sorted by how many sessions contributed.
      </p>
      {themes.map((t) => {
        const mix = (t.sentiment_mix ?? {}) as Record<string, number>;
        return (
          <div
            key={t.id}
            className="rounded-merism-md border border-merism-border bg-merism-surface p-4"
          >
            <div className="flex items-start justify-between gap-3 mb-2">
              <div>
                <h3 className="font-medium text-merism-text">{t.name}</h3>
                {t.description && (
                  <p className="text-merism-body-sm text-merism-text-muted mt-1">
                    {t.description}
                  </p>
                )}
              </div>
              <div className="flex flex-col items-end gap-1">
                <span className="font-mono tabular-nums text-merism-text">
                  {t.session_count} sess
                </span>
                <span className="text-merism-caption text-merism-text-muted">
                  {t.quote_count} quotes
                </span>
              </div>
            </div>
            {Object.keys(mix).length > 0 && (
              <div className="flex gap-2 mt-2 flex-wrap">
                {Object.entries(mix).map(([sent, n]) => (
                  <Tag key={sent}>
                    {sent}: {n}
                  </Tag>
                ))}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
