/**
 * Hook for copying a study link to clipboard and recording the share event.
 *
 * Usage:
 *   const { copyLink, copied } = useLinkShare(slug)
 *   <button onClick={copyLink}>Copy</button>
 */

import { useCallback, useRef, useState } from "react";

import { api } from "~/lib/api";

export interface UseLinkShareResult {
  copyLink: () => Promise<void>;
  shareLink: (action?: "copy" | "share_api" | "forward") => Promise<void>;
  copied: boolean;
}

export function useLinkShare(slug: string): UseLinkShareResult {
  const [copied, setCopied] = useState(false);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const shareLink = useCallback(
    async (action: "copy" | "share_api" | "forward" = "copy") => {
      try {
        await api.create(`/i/${slug}/share/`, { action });
      } catch {
        // Non-critical — don't block the user if tracking fails
      }
    },
    [slug],
  );

  const copyLink = useCallback(async () => {
    const url = `${window.location.origin}/i/${slug}`;
    await navigator.clipboard.writeText(url);
    setCopied(true);
    if (timerRef.current) clearTimeout(timerRef.current);
    timerRef.current = setTimeout(() => setCopied(false), 1500);
    // Fire-and-forget share event
    void shareLink("copy");
  }, [slug, shareLink]);

  return { copyLink, shareLink, copied };
}
