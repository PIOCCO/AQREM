import { describe, expect, it } from "vitest";

/** Mirrors ChatComposer send-enable rules for regression tests. */
function composerCanSend(value: string, hasPendingAttachment: boolean, disabled: boolean, loading: boolean) {
  return (
    !disabled &&
    !loading &&
    (value.trim().length > 0 || hasPendingAttachment)
  );
}

describe("ChatComposer send state", () => {
  it("disables send when empty", () => {
    expect(composerCanSend("", false, false, false)).toBe(false);
  });

  it("enables send when text present", () => {
    expect(composerCanSend("Hello", false, false, false)).toBe(true);
  });

  it("disables send while loading", () => {
    expect(composerCanSend("Hello", false, false, true)).toBe(false);
  });
});
