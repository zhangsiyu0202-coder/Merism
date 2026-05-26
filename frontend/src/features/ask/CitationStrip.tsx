import { useEffect } from "react";

import { Tag, Tooltip, loadPlexMono } from "~/lib/merism";

import type { AskMerismCitation } from "./types";

export interface CitationStripProps {
  citations: AskMerismCitation[];
  onJumpToTranscript?: (citation: AskMerismCitation) => void;
}

/**
 * CitationStrip — inline numeric citations shown below an assistant answer.
 *
 *   Answer text... [1] [2] [3]
 *
 * Hover a badge to see the quote + speaker. Click to jump to the transcript
 * timestamp (parent wires onJumpToTranscript). Plex Mono is lazy-loaded on
 * mount because this is the one surface where mono type is meaningful
 * (quoting participant speech verbatim).
 */
export function CitationStrip({
  citations,
  onJumpToTranscript,
}: CitationStripProps) {
  useEffect(() => {
    void loadPlexMono();
  }, []);

  if (citations.length === 0) return null;

  return (
    <div className="flex flex-wrap gap-2">
      {citations.map((c, i) => (
        <Tooltip
          key={`${c.session_id}-${c.ts}-${i}`}
          label={formatTooltipLabel(c)}
        >
          <button
            type="button"
            onClick={() => onJumpToTranscript?.(c)}
            className="focus-visible:outline-none"
          >
            <Tag variant="accent" className="cursor-pointer font-merism-mono">
              [{i + 1}]
            </Tag>
          </button>
        </Tooltip>
      ))}
    </div>
  );
}

function formatTooltipLabel(c: AskMerismCitation): string {
  const prefix = c.study_name ? `${c.study_name} · ` : "";
  const mmss = formatMmSs(c.ts);
  return `${prefix}${c.speaker} (${mmss}): "${truncate(c.quote, 100)}"`;
}

function formatMmSs(ts: number): string {
  const m = Math.floor(ts / 60);
  const s = Math.floor(ts % 60);
  return `${m}:${s.toString().padStart(2, "0")}`;
}

function truncate(text: string, max: number): string {
  return text.length > max ? text.slice(0, max - 1) + "…" : text;
}
