import { useEffect, useState } from "react"

/**
 * React hook — exposes the Django CSRF token for fetch-based POSTs.
 *
 * How Django CSRF works when the frontend and backend sit on different
 * origins (Vite on :5173, Django on :8000):
 *
 *   1. First request (usually a GET) → Django sets a ``csrftoken`` cookie.
 *   2. Subsequent unsafe methods (POST/PUT/PATCH/DELETE) must include
 *      the same token in the ``X-CSRFToken`` HTTP header.
 *
 * This hook reads the cookie synchronously; if it's missing, it
 * triggers a GET to ``/accounts/login/`` (cheap, always returns a
 * fresh cookie) and re-reads.
 *
 * Usage::
 *
 *   const csrf = useCSRFToken()
 *   await fetch("/accounts/login/", {
 *       method: "POST",
 *       credentials: "include",
 *       headers: { "X-CSRFToken": csrf ?? "" },
 *       body,
 *   })
 */
export function useCSRFToken(): string | null {
    const [token, setToken] = useState<string | null>(() => readCookie("csrftoken"))

    useEffect(() => {
        if (token) return
        const controller = new AbortController()
        void primeToken(controller.signal).then((value) => {
            if (value) setToken(value)
        })
        return () => controller.abort()
    }, [token])

    return token
}

/** Read a cookie value, or ``null`` if absent. */
export function readCookie(name: string): string | null {
    const prefix = `${name}=`
    const cookie = document.cookie.split(";").find((c) => c.trim().startsWith(prefix))
    return cookie ? decodeURIComponent(cookie.trim().slice(prefix.length)) : null
}

async function primeToken(signal: AbortSignal): Promise<string | null> {
    try {
        await fetch("/accounts/login/", {
            method: "GET",
            credentials: "include",
            signal,
        })
    } catch {
        return null
    }
    return readCookie("csrftoken")
}

/**
 * Convenience wrapper — returns ``fetch`` init with CSRF + credentials
 * already set. Use for any unsafe-method request.
 */
export async function csrfFetch(
    input: RequestInfo | URL,
    init: RequestInit = {},
): Promise<Response> {
    let token = readCookie("csrftoken")
    if (!token) {
        await primeToken(AbortSignal.timeout(5000))
        token = readCookie("csrftoken")
    }
    const headers = new Headers(init.headers)
    headers.set("X-CSRFToken", token ?? "")
    return fetch(input, {
        ...init,
        credentials: init.credentials ?? "include",
        headers,
    })
}
