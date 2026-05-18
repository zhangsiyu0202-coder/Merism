import { connect, kea, listeners, path } from "kea"
import { forms } from "kea-forms"
import { router } from "kea-router"

import { urls } from "~/app/routes"
import { csrfFetch } from "~/lib/hooks/useCSRFToken"

import type { loginLogicType } from './loginLogicType'

export interface LoginFormValues {
    email: string
    password: string
}

/**
 * loginLogic — owns the /login/ form state.
 *
 * On submit we POST to Django allauth's ``/accounts/login/`` with a
 * urlencoded body (what allauth's default form expects) + the CSRF
 * token in the header. allauth sets a session cookie on success; we
 * then navigate into the app.
 */
export const loginLogic = kea<loginLogicType>([
    path(["features", "authentication", "loginLogic"]),

    connect({ actions: [router, ["push"]] }),

    forms(() => ({
        login: {
            defaults: { email: "", password: "" } as LoginFormValues,
            errors: ({ email, password }) => ({
                email: !email.includes("@") ? "Enter a valid email" : undefined,
                password: password.length < 4 ? "Password is too short" : undefined,
            }),
            submit: async (formValues) => {
                const body = new URLSearchParams()
                body.set("login", formValues.email)
                body.set("password", formValues.password)
                const response = await csrfFetch("/accounts/login/", {
                    method: "POST",
                    headers: {
                        "Content-Type": "application/x-www-form-urlencoded",
                        "X-Requested-With": "XMLHttpRequest",
                    },
                    body: body.toString(),
                    redirect: "manual",
                })
                // allauth returns 302 on success. ``redirect: "manual"`` makes
                // fetch surface the 302 without auto-following (would try to
                // hit the internal redirect URL cross-origin).
                if (response.status !== 302 && response.status !== 200) {
                    throw new Error(
                        response.status === 400
                            ? "Invalid email or password."
                            : `Login failed (${response.status}).`,
                    )
                }
                window.location.href = urls.ask()
            },
        },
    })),

    listeners(() => ({
        submitLoginFailure: ({ error }) => {
            // Errors surface automatically in ``loginHasErrors``; we log so
            // devtools has a trace.
            // eslint-disable-next-line no-console
            console.warn("[login] submit failed", error)
        },
    })),
])
