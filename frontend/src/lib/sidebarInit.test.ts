import { describe, expect, it, vi } from "vitest";
import { SIDEBAR_COLLAPSED_KEY, readSidebarCollapsedFromStorage } from "./sidebarInit";

describe("sidebarInit", () => {
  it("reads collapsed flag from storage", () => {
    const store = new Map<string, string>();
    vi.stubGlobal("localStorage", {
      getItem: (k: string) => store.get(k) ?? null,
      setItem: (k: string, v: string) => store.set(k, v),
    });
    vi.stubGlobal("window", {});
    expect(readSidebarCollapsedFromStorage()).toBe(false);
    store.set(SIDEBAR_COLLAPSED_KEY, "1");
    expect(readSidebarCollapsedFromStorage()).toBe(true);
  });
});
