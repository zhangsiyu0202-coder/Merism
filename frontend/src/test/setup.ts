import "@testing-library/jest-dom/vitest";

import { cleanup } from "@testing-library/react";
import { afterAll, afterEach, beforeAll } from "vitest";

import { server } from "./msw/server";

// MSW lifecycle. Use `bypass` so any unmocked request blows up the test
// loudly — you never want a test silently hitting the network.
beforeAll(() => server.listen({ onUnhandledRequest: "error" }));

// Reset handlers between tests so one test's per-test override can't leak
// into the next. `cleanup` unmounts any React trees RTL left behind.
afterEach(() => {
  cleanup();
  server.resetHandlers();
});

afterAll(() => server.close());

// JSDOM doesn't implement matchMedia — polyfill it enough for Radix
// primitives that query prefers-reduced-motion.
if (typeof window !== "undefined" && !window.matchMedia) {
  Object.defineProperty(window, "matchMedia", {
    writable: true,
    value: (query: string) => ({
      matches: false,
      media: query,
      onchange: null,
      addEventListener: () => {},
      removeEventListener: () => {},
      addListener: () => {},
      removeListener: () => {},
      dispatchEvent: () => false,
    }),
  });
}

// Radix Dialog uses ResizeObserver; JSDOM doesn't ship one.
if (typeof window !== "undefined" && !window.ResizeObserver) {
  window.ResizeObserver = class {
    observe() {}
    unobserve() {}
    disconnect() {}
  } as unknown as typeof ResizeObserver;
}
