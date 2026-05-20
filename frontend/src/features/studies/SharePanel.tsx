import { Copy, Eye, Link2 } from "lucide-react"
import { useState } from "react"

import { Button } from "~/lib/merism"

/**
 * SharePanel — the single canonical share-URL surface for a Study.
 *
 * Per the 2026-05-20 simplification, every Study auto-creates one
 * ``primary_link`` and we surface that one link here. No "Create link"
 * button, no list of links — Study = one link.
 *
 * Two actions:
 *   - 复制链接 — copy the full URL to clipboard
 *   - 预览     — open the link with ``?preview=1`` so the researcher
 *                walks the participant flow without writing any data
 */
export default function SharePanel({
    shareUrl,
}: {
    shareUrl: string | null | undefined
}): JSX.Element | null {
    const [copied, setCopied] = useState(false)
    if (!shareUrl) return null

    const fullUrl = shareUrl.startsWith("http")
        ? shareUrl
        : `${window.location.origin}${shareUrl}`

    async function handleCopy(): Promise<void> {
        try {
            await navigator.clipboard.writeText(fullUrl)
            setCopied(true)
            window.setTimeout(() => setCopied(false), 1500)
        } catch {
            // Best-effort; clipboard API may be blocked in some browsers.
        }
    }

    function handlePreview(): void {
        const previewUrl = fullUrl.includes("?")
            ? `${fullUrl}&preview=1`
            : `${fullUrl}?preview=1`
        window.open(previewUrl, "_blank", "noopener")
    }

    return (
        <section className="flex items-center gap-3 rounded-merism-lg bg-merism-surface px-4 py-3 shadow-merism-card ring-1 ring-[color:var(--merism-hairline)]">
            <Link2 className="h-4 w-4 shrink-0 text-merism-text-subtle" />
            <div className="min-w-0 flex-1">
                <div className="font-mono text-merism-caption uppercase tracking-merism-caps text-merism-text-subtle">
                    访谈链接
                </div>
                <code className="block truncate font-mono text-merism-label text-merism-text">
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
    )
}
