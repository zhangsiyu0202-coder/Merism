/**
 * Returns the backend origin for participant-facing API calls.
 * Empty string means same-origin (Vite proxy handles /i/ → Django).
 */
export function getBackendOrigin(): string {
    return ""
}
