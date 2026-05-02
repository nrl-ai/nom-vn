import "@testing-library/jest-dom/vitest";

// jsdom@29 + vitest@2 ships an empty `localStorage` object without the
// Storage prototype on the `window` globalThis we get in tests. Components
// that read/write localStorage break with "setItem is not a function".
// Polyfill with a minimal in-memory implementation so component tests
// can exercise persistence end-to-end.
if (typeof localStorage === "object" && typeof (localStorage as Storage).setItem !== "function") {
  // Use a Map so we don't have to dynamically `delete` keys from a plain
  // object (lints to `@typescript-eslint/no-dynamic-delete` in our config).
  const _store = new Map<string, string>();
  const polyfill: Storage = {
    get length() {
      return _store.size;
    },
    key(i: number): string | null {
      return Array.from(_store.keys())[i] ?? null;
    },
    getItem(k: string): string | null {
      return _store.has(k) ? (_store.get(k) ?? null) : null;
    },
    setItem(k: string, v: string): void {
      _store.set(k, String(v));
    },
    removeItem(k: string): void {
      _store.delete(k);
    },
    clear(): void {
      _store.clear();
    },
  };
  Object.defineProperty(globalThis, "localStorage", {
    configurable: true,
    value: polyfill,
  });
}
