import { describe, expect, it } from "vitest";
import { formatNoEvidenceMessage } from "./noEvidenceMessage";
import { PRODUCT_V1, V1_EMPLOYEE_NOT_FOUND_MESSAGE } from "./productV1";

describe("formatNoEvidenceMessage", () => {
  it("does not collapse the no-documents case into a project search message", () => {
    const msg = formatNoEvidenceMessage("Demo Project", 2);
    if (PRODUCT_V1) {
      expect(msg).toBe(V1_EMPLOYEE_NOT_FOUND_MESSAGE);
      expect(msg).not.toContain("No documents available");
    } else {
      expect(msg).toContain("Demo Project");
      expect(msg).toContain("2 sources searched");
    }
    expect(msg.toLowerCase()).not.toContain("no documents available");
  });
});
