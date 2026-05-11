import { useValues } from "kea"
import {
    Building2,
    Languages,
    LogOut,
    Mail,
    Network,
    ShieldCheck,
    User,
} from "lucide-react"
import { useState } from "react"

import { urls } from "~/app/routes"
import {
    Button,
    PageTopBar,
    SettingsSection,
    Tag,
    ThreePaneLayout,
} from "~/lib/merism"
import { userLogic } from "~/models/userLogic"
import { useTranslation } from "react-i18next"
import { setLocale, type MerismLocale } from "~/i18n"
import { LLMGatewaySection } from "./llm-gateway/LLMGatewaySection"

/**
 * SettingsPage — per-team workspace settings.
 *
 * Two sub-pages driven by local state:
 *   - ``profile``   → current user details + session
 *   - ``workspace`` → team / org identity + compliance
 *
 * Platform-level operations (all-tenant view, CRUD on every model,
 * Celery queue health) live in the built-in Django admin at /admin/ —
 * reachable only by
 * Merism staff.
 */

type SettingsSectionKey = "profile" | "workspace" | "llm-gateway"

export default function SettingsPage(): JSX.Element {
    const { t } = useTranslation()
    const { user } = useValues(userLogic)
    const initial =
        (typeof window !== "undefined"
            ? new URLSearchParams(window.location.search).get("section")
            : null) as SettingsSectionKey | null
    const [section, setSection] = useState<SettingsSectionKey>(initial ?? "profile")

    return (
        <div className="flex flex-col gap-[var(--spacing-merism-section-y)]">
            <PageTopBar
                title={t("settings.title")}
                lede={t("settings.lede")}
            />

            <ThreePaneLayout
                left={<SectionNav current={section} onNavigate={setSection} />}
                middle={
                    <div className="flex flex-col gap-[var(--spacing-merism-section-y)]">
                        {section === "profile" && <ProfileSection user={user} />}
                        {section === "workspace" && <WorkspaceSection user={user} />}
                        {section === "llm-gateway" && <LLMGatewaySection />}
                    </div>
                }
            />
        </div>
    )
}

function SectionNav({
    current,
    onNavigate,
}: {
    current: SettingsSectionKey
    onNavigate: (s: SettingsSectionKey) => void
}): JSX.Element {
    const { t } = useTranslation()
    const items: Array<{
        key: SettingsSectionKey
        label: string
        icon: typeof User
    }> = [
        { key: "profile", label: t("settings.nav.profile"), icon: User },
        { key: "workspace", label: t("settings.nav.workspace"), icon: Building2 },
        { key: "llm-gateway", label: "LLM Gateway", icon: Network },
    ]
    return (
        <nav className="flex flex-col gap-1" aria-label="Settings sections">
            <span className="px-3 pb-2 font-mono text-merism-caption uppercase tracking-merism-caps text-merism-text-subtle">
                {t("common.sections")}
            </span>
            {items.map((item) => {
                const active = current === item.key
                const Icon = item.icon
                return (
                    <button
                        key={item.key}
                        type="button"
                        onClick={() => onNavigate(item.key)}
                        className={
                            "relative flex items-center gap-3 rounded-merism-md px-3 py-2 text-left " +
                            "text-merism-label transition-colors " +
                            "duration-[var(--merism-duration-fast)] " +
                            (active
                                ? "bg-merism-accent-soft text-merism-text"
                                : "text-merism-text-muted hover:bg-merism-bg-subtle hover:text-merism-text")
                        }
                    >
                        {active && (
                            <span
                                aria-hidden="true"
                                className="absolute left-0 top-1/2 h-5 w-[2px] -translate-y-1/2 rounded-full bg-merism-accent"
                            />
                        )}
                        <Icon
                            className={
                                "h-4 w-4 shrink-0 " +
                                (active
                                    ? "text-merism-accent"
                                    : "text-merism-text-subtle")
                            }
                            strokeWidth={1.6}
                        />
                        <span className="flex-1">{item.label}</span>
                    </button>
                )
            })}
        </nav>
    )
}

function ProfileSection({ user }: { user: ReturnType<typeof useValues>["user"] }): JSX.Element {
    const { t } = useTranslation()
    if (!user) {
        return (
            <SettingsSection title={t("settings.profile.title")}>
                <p className="text-merism-body-sm text-merism-text-muted">
                    {t("settings.profile.loading")}
                </p>
            </SettingsSection>
        )
    }
    const displayName =
        [user.first_name, user.last_name].filter(Boolean).join(" ") || user.email

    async function handleSignOut() {
        try {
            await fetch("/accounts/logout/", {
                method: "POST",
                credentials: "include",
            })
        } catch {
            /* best-effort */
        }
        window.location.assign(urls.login())
    }

    return (
        <>
            <SettingsSection title={t("settings.profile.title")} onEdit={() => { /* TODO */ }}>
                <div className="flex items-center gap-4">
                    <div className="flex h-12 w-12 items-center justify-center rounded-merism-full bg-merism-bg-subtle text-merism-text">
                        <span className="font-display text-merism-subtitle font-[600]">
                            {displayName[0]?.toUpperCase() ?? "U"}
                        </span>
                    </div>
                    <div className="flex flex-col gap-0.5">
                        <p className="text-merism-body font-medium text-merism-text">
                            {displayName}
                        </p>
                        <p className="flex items-center gap-1.5 text-merism-body-sm text-merism-text-muted">
                            <Mail className="h-3.5 w-3.5" />
                            {user.email}
                        </p>
                    </div>
                </div>
            </SettingsSection>

            <SettingsSection
                title={t("settings.profile.security_title")}
                description={t("settings.profile.security_description")}
            >
                <div className="flex items-center gap-3">
                    <Tag variant="success" size="sm" case="normal">
                        {t("settings.profile.active_session")}
                    </Tag>
                    <Button
                        type="button"
                        variant="secondary"
                        size="sm"
                        iconLeft={<LogOut className="h-4 w-4" />}
                        onClick={handleSignOut}
                    >
                        {t("common.sign_out")}
                    </Button>
                </div>
            </SettingsSection>
        </>
    )
}

function WorkspaceSection({ user }: { user: ReturnType<typeof useValues>["user"] }): JSX.Element {
    const { t } = useTranslation()
    const teamName = user?.team?.name ?? t("nav.workspace")
    const orgName = user?.organization?.name ?? "—"
    return (
        <>
            <SettingsSection
                title={t("settings.workspace.title")}
                onEdit={() => { /* TODO */ }}
            >
                <p className="text-merism-body text-merism-text">{teamName}</p>
                <p className="text-merism-body-sm text-merism-text-muted">
                    {t("settings.workspace.organisation", { name: orgName })}
                </p>
            </SettingsSection>

            <SettingsSection
                title={t("settings.workspace.members_title")}
                description={t("settings.workspace.members_description")}
            >
                <p className="text-merism-body-sm text-merism-text-muted">
                    {t("settings.workspace.members_body")}
                </p>
            </SettingsSection>

            <LocaleSection />

            <SettingsSection
                title={t("settings.workspace.compliance_title")}
                description={t("settings.workspace.compliance_description")}
            >
                <div className="flex items-center gap-2">
                    <ShieldCheck className="h-4 w-4 text-[color:var(--merism-status-success)]" />
                    <span className="text-merism-body-sm text-merism-text">
                        {t("settings.workspace.compliance_body")}
                    </span>
                </div>
            </SettingsSection>
        </>
    )
}


function LocaleSection(): JSX.Element {
    const { t, i18n } = useTranslation()
    const current = (i18n.language as MerismLocale | undefined) ?? "en"
    const OPTIONS: Array<{ value: MerismLocale; label: string }> = [
        { value: "en", label: "English" },
        { value: "zh-CN", label: "简体中文" },
    ]
    return (
        <SettingsSection
            title={t("settings.workspace.language_title")}
            description={t("settings.workspace.language_description")}
        >
            <div className="flex items-center gap-3">
                <Languages className="h-4 w-4 text-merism-text-subtle" />
                <div className="flex gap-1 rounded-merism-md bg-merism-bg-subtle p-1">
                    {OPTIONS.map((opt) => (
                        <button
                            key={opt.value}
                            type="button"
                            onClick={() => setLocale(opt.value)}
                            className={
                                "rounded-merism-sm px-3 py-1 text-merism-label transition-colors " +
                                (current === opt.value
                                    ? "bg-merism-surface text-merism-text shadow-merism-card"
                                    : "text-merism-text-muted hover:text-merism-text")
                            }
                        >
                            {opt.label}
                        </button>
                    ))}
                </div>
            </div>
        </SettingsSection>
    )
}
