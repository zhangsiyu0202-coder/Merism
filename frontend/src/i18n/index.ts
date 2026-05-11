/**
 * i18n — Merism internationalisation bootstrap.
 *
 * - Default language: English.
 * - Fallback: English.
 * - User preference persisted in ``localStorage["merism-locale"]``.
 * - Supported locales: "en" | "zh-CN".
 *
 * To translate a string in a component::
 *
 *     import { useTranslation } from "react-i18next"
 *     const { t } = useTranslation()
 *     return <h1>{t("studies.title")}</h1>
 *
 * Non-React code (e.g. kea logic) should import ``i18n`` directly and
 * call ``i18n.t("...")``. See react-i18next docs for full API.
 */

import i18n from "i18next"
import { initReactI18next } from "react-i18next"

import en from "./locales/en.json"
import zhCN from "./locales/zh-CN.json"

const LOCAL_STORAGE_KEY = "merism-locale"

export type MerismLocale = "en" | "zh-CN"

export const SUPPORTED_LOCALES: readonly MerismLocale[] = ["en", "zh-CN"] as const

function detectInitialLocale(): MerismLocale {
    if (typeof window === "undefined") return "en"
    const stored = window.localStorage.getItem(LOCAL_STORAGE_KEY)
    if (stored && SUPPORTED_LOCALES.includes(stored as MerismLocale)) {
        return stored as MerismLocale
    }
    // Browser fallback — take the first matching prefix.
    const browser = (navigator.language || "en").toLowerCase()
    if (browser.startsWith("zh")) return "zh-CN"
    return "en"
}

void i18n.use(initReactI18next).init({
    resources: {
        en: { translation: en },
        "zh-CN": { translation: zhCN },
    },
    lng: detectInitialLocale(),
    fallbackLng: "en",
    interpolation: { escapeValue: false },
    returnNull: false,
})

export function setLocale(locale: MerismLocale): void {
    void i18n.changeLanguage(locale)
    if (typeof window !== "undefined") {
        window.localStorage.setItem(LOCAL_STORAGE_KEY, locale)
    }
}

export { i18n }
export default i18n
