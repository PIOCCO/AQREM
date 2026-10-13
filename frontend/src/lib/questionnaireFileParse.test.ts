import { describe, expect, it } from "vitest";
import { parseQuestionnaireFile, QUESTIONNAIRE_MAX_BYTES } from "./questionnaireFileParse";

describe("parseQuestionnaireFile", () => {
  it("rejects wrong file types", async () => {
    const file = new File(["hello"], "notes.txt", { type: "text/plain" });
    const result = await parseQuestionnaireFile(file);
    expect(result.ok).toBe(false);
    expect(result.errorCode).toBe("wrong_type");
  });

  it("parses csv and detects question column", async () => {
    const csv = "question,section\nWhat is MFA?,Security\nWho is DPO?,Privacy\n";
    const file = new File([csv], "q.csv", { type: "text/csv" });
    const result = await parseQuestionnaireFile(file);
    expect(result.ok).toBe(true);
    expect(result.rowCount).toBe(2);
    expect(result.questionColumn.toLowerCase()).toContain("question");
  });

  it("rejects oversize files", async () => {
    const big = new Uint8Array(QUESTIONNAIRE_MAX_BYTES + 1);
    const file = new File([big], "big.csv", { type: "text/csv" });
    const result = await parseQuestionnaireFile(file);
    expect(result.ok).toBe(false);
    expect(result.errorCode).toBe("too_large");
  });
});
