/**
 * Footer — minimal marketing footer.
 */

export function Footer(): JSX.Element {
    return (
        <footer className="border-t border-[var(--merism-hairline)] bg-merism-surface py-10">
            <div className="mx-auto flex max-w-[1200px] flex-col items-center gap-4 px-[var(--spacing-merism-fluid-gutter)] md:flex-row md:justify-between">
                <span className="font-display text-merism-body font-semibold tracking-merism-tight text-merism-text">
                    Merism
                </span>
                <p className="text-merism-body-sm text-merism-text-subtle">
                    © {new Date().getFullYear()} Merism. AI 驱动的用户研究平台。
                </p>
                <div className="flex gap-6">
                    <a
                        href="/login"
                        className="text-merism-body-sm text-merism-text-muted hover:text-merism-text transition-colors"
                    >
                        登录
                    </a>
                    <a
                        href="mailto:hello@merism.ai"
                        className="text-merism-body-sm text-merism-text-muted hover:text-merism-text transition-colors"
                    >
                        联系我们
                    </a>
                </div>
            </div>
        </footer>
    )
}
