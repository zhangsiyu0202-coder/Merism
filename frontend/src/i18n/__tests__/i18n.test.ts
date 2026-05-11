import { describe, expect, it } from "vitest"
import i18n from "~/i18n"

describe("i18n runtime", () => {
    it("loads en by default and translates nav keys", () => {
        void i18n.changeLanguage("en")
        expect(i18n.t("nav.home")).toBe("Home")
        expect(i18n.t("studies.status.draft")).toBe("Draft")
    })
    it("switches to zh-CN", async () => {
        await i18n.changeLanguage("zh-CN")
        expect(i18n.t("nav.home")).toBe("首页")
        expect(i18n.t("studies.status.draft")).toBe("草稿")
        expect(i18n.t("login.heading")).toBe("欢迎回来。")
    })
})
