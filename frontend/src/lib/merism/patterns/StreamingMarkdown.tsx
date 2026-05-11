import ReactMarkdown from "react-markdown"
import remarkGfm from "remark-gfm"

import { cn } from "../utils/cn"

/**
 * StreamingMarkdown — render LLM output with Merism typography.
 *
 * Why a wrapper instead of raw react-markdown?
 *   - Applies the merism type scale (body / body-sm / mono) +
 *     colour tokens consistently — no component-level restyling.
 *   - Optional typing cursor animated at the end of the stream so
 *     users see the model "typing" rather than static text appearing
 *     in chunks.
 *   - One place to swap out for a heavier renderer later (add
 *     rehype-highlight for code syntax) without touching callers.
 *
 * Safety: react-markdown is sanitised by default — no raw HTML
 * execution. Code blocks are escaped.
 */

export interface StreamingMarkdownProps {
    text: string
    streaming?: boolean
    className?: string
}

export function StreamingMarkdown({
    text,
    streaming = false,
    className,
}: StreamingMarkdownProps): JSX.Element {
    return (
        <div
            className={cn(
                "text-merism-body leading-[var(--text-merism-body--line-height)] text-merism-text",
                "[&>*+*]:mt-3",
                "[&_p]:leading-[1.6]",
                "[&_strong]:font-[600] [&_strong]:text-merism-text",
                "[&_em]:italic",
                "[&_code]:rounded-merism-xs [&_code]:bg-merism-bg-subtle/70 [&_code]:px-1 [&_code]:py-[1px] [&_code]:font-mono [&_code]:text-[0.92em]",
                "[&_pre]:overflow-x-auto [&_pre]:rounded-merism-md [&_pre]:bg-merism-bg-subtle/70 [&_pre]:p-4",
                "[&_pre_code]:bg-transparent [&_pre_code]:p-0",
                "[&_h1]:mt-5 [&_h1]:text-merism-h2 [&_h1]:font-display [&_h1]:font-[500]",
                "[&_h2]:mt-5 [&_h2]:text-merism-title [&_h2]:font-display [&_h2]:font-[500]",
                "[&_h3]:mt-4 [&_h3]:text-merism-subtitle [&_h3]:font-display [&_h3]:font-[500]",
                "[&_ul]:list-disc [&_ul]:pl-5 [&_ol]:list-decimal [&_ol]:pl-5",
                "[&_li]:my-1",
                "[&_table]:w-full [&_table]:border-collapse [&_table]:text-merism-body-sm",
                "[&_th]:border-b [&_th]:border-[color:var(--merism-hairline)] [&_th]:px-3 [&_th]:py-2 [&_th]:text-left [&_th]:font-medium",
                "[&_td]:border-b [&_td]:border-[color:var(--merism-hairline)] [&_td]:px-3 [&_td]:py-2",
                "[&_blockquote]:border-l-2 [&_blockquote]:border-merism-accent [&_blockquote]:pl-4 [&_blockquote]:italic [&_blockquote]:text-merism-text-muted",
                "[&_a]:text-merism-accent [&_a]:underline [&_a]:underline-offset-4 [&_a:hover]:text-merism-accent-hover",
                "[&_hr]:border-0 [&_hr]:border-t [&_hr]:border-[color:var(--merism-hairline)] [&_hr]:my-6",
                className,
            )}
        >
            <ReactMarkdown remarkPlugins={[remarkGfm]}>
                {text || ""}
            </ReactMarkdown>
            {streaming && (
                <span
                    aria-hidden="true"
                    className="ml-0.5 inline-block h-[1em] w-[2px] animate-pulse bg-merism-text align-[-0.1em]"
                />
            )}
        </div>
    )
}
