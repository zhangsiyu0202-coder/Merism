import { setupServer } from "msw/node"

import { handlers } from "./handlers"

/**
 * MSW test server. Mocks Django REST API calls for unit and integration tests.
 *
 * Per-test overrides:
 *     import { server } from "~/test/msw/server"
 *     import { http, HttpResponse } from "msw"
 *
 *     server.use(
 *         http.get("/api/studies/", () => HttpResponse.json({ results: [] })),
 *     )
 */
export const server = setupServer(...handlers)
