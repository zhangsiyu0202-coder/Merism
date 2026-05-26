import { Button } from "~/lib/merism";
import { HeroDemo } from "./HeroDemo";
import { FeatureGrid } from "./FeatureGrid";
import { HowItWorks } from "./HowItWorks";
import { StatsBar } from "./StatsBar";
import { Footer } from "./Footer";

export default function WelcomePage(): JSX.Element {
  return (
    <div className="min-h-screen bg-merism-bg">
      {/* ─── Nav ─── */}
      <nav className="fixed top-0 z-50 w-full border-b border-[color:var(--merism-hairline)] bg-[var(--merism-glass-surface)] backdrop-blur-[var(--merism-glass-blur)]">
        <div className="mx-auto flex h-14 max-w-[1200px] items-center justify-between px-[var(--spacing-merism-fluid-gutter)]">
          <span className="font-display text-[18px] font-semibold tracking-merism-tight text-merism-text">
            Merism
          </span>
          <div className="flex items-center gap-6">
            <a
              href="#features"
              className="text-merism-body-sm text-merism-text-muted hover:text-merism-text transition-colors"
            >
              功能
            </a>
            <a
              href="#how-it-works"
              className="text-merism-body-sm text-merism-text-muted hover:text-merism-text transition-colors"
            >
              流程
            </a>
            <a
              href="/login"
              className="text-merism-body-sm text-merism-text-muted hover:text-merism-text transition-colors"
            >
              登录
            </a>
            <Button size="sm" asChild>
              <a href="/login?next=/">开始使用</a>
            </Button>
          </div>
        </div>
      </nav>

      {/* ─── Hero ─── */}
      <section className="relative overflow-hidden pt-32 pb-20 md:pt-40 md:pb-28">
        {/* Subtle gradient orb */}
        <div
          aria-hidden="true"
          className="pointer-events-none absolute -top-40 left-1/2 h-[600px] w-[800px] -translate-x-1/2 rounded-full opacity-30 blur-[120px]"
          style={{
            background:
              "radial-gradient(ellipse, var(--merism-accent-soft) 0%, transparent 70%)",
          }}
        />
        <div className="relative mx-auto max-w-[1200px] px-[var(--spacing-merism-fluid-gutter)]">
          <div className="flex flex-col items-center gap-16 lg:flex-row lg:items-center lg:justify-between">
            {/* Copy */}
            <div className="max-w-[540px] text-center lg:text-left">
              <p className="mb-4 inline-flex items-center gap-2 rounded-merism-full bg-merism-accent-soft px-3 py-1 text-merism-label font-medium text-merism-accent">
                <span className="h-1.5 w-1.5 rounded-full bg-merism-accent" />
                AI 驱动的用户研究平台
              </p>
              <h1 className="font-display text-merism-hero font-bold tracking-merism-display text-merism-text">
                写一句研究目标，
                <br />
                <span className="text-merism-accent">AI 帮你完成全部。</span>
              </h1>
              <p className="mt-6 text-merism-subtitle leading-relaxed text-merism-text-muted">
                从访谈提纲生成、AI
                主持人实时对话、到自动分析与结构化报告——Merism 让定性研究快 10
                倍，成本降 90%。
              </p>
              <div className="mt-10 flex flex-wrap items-center gap-4 justify-center lg:justify-start">
                <Button size="lg" asChild>
                  <a href="/login?next=/">免费开始</a>
                </Button>
                <Button variant="secondary" size="lg" asChild>
                  <a href="#how-it-works">了解流程</a>
                </Button>
              </div>
            </div>
            {/* Demo */}
            <div className="shrink-0">
              <HeroDemo />
            </div>
          </div>
        </div>
      </section>

      {/* ─── Stats ─── */}
      <StatsBar />

      {/* ─── Features ─── */}
      <section id="features" className="py-[var(--spacing-merism-section-xl)]">
        <div className="mx-auto max-w-[1200px] px-[var(--spacing-merism-fluid-gutter)]">
          <div className="mb-16 text-center">
            <h2 className="font-display text-merism-display font-bold tracking-merism-display text-merism-text">
              一个平台，覆盖全流程
            </h2>
            <p className="mt-4 text-merism-body text-merism-text-muted max-w-[600px] mx-auto">
              从研究设计到洞察交付，不再需要在 5 个工具之间切换。
            </p>
          </div>
          <FeatureGrid />
        </div>
      </section>

      {/* ─── How it works ─── */}
      <section
        id="how-it-works"
        className="py-[var(--spacing-merism-section-xl)] bg-merism-bg-subtle"
      >
        <div className="mx-auto max-w-[1200px] px-[var(--spacing-merism-fluid-gutter)]">
          <div className="mb-16 text-center">
            <h2 className="font-display text-merism-display font-bold tracking-merism-display text-merism-text">
              四步完成一次研究
            </h2>
            <p className="mt-4 text-merism-body text-merism-text-muted max-w-[600px] mx-auto">
              从目标到洞察，最快 24 小时。
            </p>
          </div>
          <HowItWorks />
        </div>
      </section>

      {/* ─── Final CTA ─── */}
      <section className="py-[var(--spacing-merism-section-xl)]">
        <div className="mx-auto max-w-[680px] px-[var(--spacing-merism-fluid-gutter)] text-center">
          <h2 className="font-display text-merism-headline font-bold tracking-merism-display text-merism-text">
            准备好让 AI 帮你做研究了吗？
          </h2>
          <p className="mt-4 text-merism-body text-merism-text-muted">
            无需信用卡，免费开始你的第一个研究项目。
          </p>
          <div className="mt-8">
            <Button size="lg" asChild>
              <a href="/login?next=/">立即开始</a>
            </Button>
          </div>
        </div>
      </section>

      {/* ─── Footer ─── */}
      <Footer />
    </div>
  );
}
