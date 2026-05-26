/**
 * Lazy-load IBM Plex Mono. Used for Ask Merism / Knowledge Explore
 * citations that render in monospace (design-system spec Req 4.3-4.4).
 *
 * Implementation memoises the import so repeated calls from different
 * components do not re-trigger a network request.
 */
let _promise: Promise<void> | null = null;

export function loadPlexMono(): Promise<void> {
  if (_promise !== null) {
    return _promise;
  }
  _promise = (async () => {
    await Promise.all([
      import("@fontsource/ibm-plex-mono/400.css"),
      import("@fontsource/ibm-plex-mono/500.css"),
    ]);
  })();
  return _promise;
}
