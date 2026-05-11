/**
 * Typed fetch wrapper for the Merism API.
 *
 * Mirrors the ergonomics of PostHog's ``lib/api.ts`` (``api.get<T>()``,
 * ``api.create<T>()``) in a much smaller surface. One day we'll replace
 * this with the auto-generated ``openapi-zod-client`` output; keep the
 * public methods stable so that swap is mechanical.
 */

import type { ApiError, Paginated } from "~/types"

import { readCookie } from "./hooks/useCSRFToken"

export type QueryParams = Record<string, string | number | boolean | null | undefined>

export interface RequestInitExtra extends Omit<RequestInit, "body"> {
    query?: QueryParams
    body?: unknown
}

/** Non-2xx HTTP response wrapped. */
export class ApiRequestError extends Error {
    constructor(
        public status: number,
        public response: Response,
        public detail?: ApiError,
    ) {
        super(detail?.detail ?? `Request failed: ${status}`)
        this.name = "ApiRequestError"
    }
}

const UNSAFE_METHODS = new Set(["POST", "PUT", "PATCH", "DELETE"])

function encodeQuery(params?: QueryParams): string {
    if (!params) return ""
    const usp = new URLSearchParams()
    for (const [key, value] of Object.entries(params)) {
        if (value === undefined || value === null) continue
        usp.append(key, String(value))
    }
    const encoded = usp.toString()
    return encoded ? `?${encoded}` : ""
}

async function request<T>(url: string, init: RequestInitExtra = {}): Promise<T> {
    const { query, body, headers, method = "GET", ...rest } = init
    const finalHeaders = new Headers(headers)
    // Inject Django CSRF for any unsafe method without forcing callers to
    // remember. Same-origin via Vite proxy means the csrftoken cookie is
    // already set after the first GET.
    if (UNSAFE_METHODS.has(method.toUpperCase())) {
        const token = readCookie("csrftoken")
        if (token && !finalHeaders.has("X-CSRFToken")) {
            finalHeaders.set("X-CSRFToken", token)
        }
    }
    let finalBody: BodyInit | undefined
    if (body !== undefined) {
        if (body instanceof FormData || body instanceof Blob || typeof body === "string") {
            finalBody = body as BodyInit
        } else {
            finalBody = JSON.stringify(body)
            if (!finalHeaders.has("Content-Type")) {
                finalHeaders.set("Content-Type", "application/json")
            }
        }
    }
    const response = await fetch(url + encodeQuery(query), {
        ...rest,
        method,
        body: finalBody,
        headers: finalHeaders,
        credentials: rest.credentials ?? "include",
    })
    if (!response.ok) {
        let detail: ApiError | undefined
        try {
            detail = (await response.json()) as ApiError
        } catch {
            // body not json
        }
        throw new ApiRequestError(response.status, response, detail)
    }
    if (response.status === 204) return undefined as T
    const contentType = response.headers.get("content-type") ?? ""
    if (contentType.includes("application/json")) {
        return (await response.json()) as T
    }
    return (await response.text()) as unknown as T
}

export const api = {
    /** GET a single resource or a list. */
    get<T>(url: string, query?: QueryParams): Promise<T> {
        return request<T>(url, { method: "GET", query })
    },
    /** GET a paginated list. Same as get<Paginated<T>> — named for clarity. */
    list<T>(url: string, query?: QueryParams): Promise<Paginated<T>> {
        return request<Paginated<T>>(url, { method: "GET", query })
    },
    /** POST create. */
    create<T>(url: string, body?: unknown, init?: RequestInitExtra): Promise<T> {
        return request<T>(url, { ...init, method: "POST", body })
    },
    /** PATCH partial update. */
    update<T>(url: string, body: unknown, init?: RequestInitExtra): Promise<T> {
        return request<T>(url, { ...init, method: "PATCH", body })
    },
    /** PUT full replace. */
    replace<T>(url: string, body: unknown, init?: RequestInitExtra): Promise<T> {
        return request<T>(url, { ...init, method: "PUT", body })
    },
    /** DELETE. */
    delete(url: string, init?: RequestInitExtra): Promise<void> {
        return request<void>(url, { ...init, method: "DELETE" })
    },
    /** Call a DRF ``@action`` route. */
    action<T>(url: string, body?: unknown, init?: RequestInitExtra): Promise<T> {
        return request<T>(url, { ...init, method: "POST", body })
    },
    /** Low-level escape hatch. */
    raw<T>(url: string, init?: RequestInitExtra): Promise<T> {
        return request<T>(url, init)
    },
}
