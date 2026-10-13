import * as XLSX from "xlsx";

export const QUESTIONNAIRE_MAX_BYTES = 10 * 1024 * 1024;
export const QUESTIONNAIRE_MAX_ROWS = 1000;
export const QUESTIONNAIRE_ACCEPT = ".csv,.xlsx,.xls";

const QUESTION_HEADER_HINTS = ["question", "questions", "prompt", "text", "requirement", "control", "query"];

export type ParsedSheet = { name: string; rowCount: number };

export type ParsedQuestionnaire = {
  ok: boolean;
  error?: string;
  errorCode?:
    | "wrong_type"
    | "too_large"
    | "empty"
    | "no_column"
    | "unreadable"
    | "too_many_rows"
    | "password_protected";
  sheets: ParsedSheet[];
  selectedSheet: string;
  columns: string[];
  questionColumn: string;
  previewRows: string[][];
  questionTexts: string[];
  duplicateQuestions: string[];
  rowCount: number;
};

function normalizeHeader(h: string): string {
  return h.trim().toLowerCase().replace(/\s+/g, " ");
}

function detectQuestionColumn(headers: string[]): string {
  const normalized = headers.map(normalizeHeader);
  for (const hint of QUESTION_HEADER_HINTS) {
    const idx = normalized.findIndex((h) => h === hint || h.includes(hint));
    if (idx >= 0) return headers[idx] ?? headers[0];
  }
  return headers[0] ?? "Column 1";
}

function parseCsv(text: string): { headers: string[]; rows: string[][] } {
  const lines = text.split(/\r?\n/).filter((l) => l.trim().length > 0);
  if (lines.length === 0) return { headers: [], rows: [] };
  const headers = lines[0].split(",").map((c) => c.trim().replace(/^"|"$/g, ""));
  const rows = lines.slice(1).map((line) => line.split(",").map((c) => c.trim().replace(/^"|"$/g, "")));
  return { headers, rows };
}

function sheetToTable(workbook: XLSX.WorkBook, sheetName: string): { headers: string[]; rows: string[][] } {
  const sheet = workbook.Sheets[sheetName];
  if (!sheet) return { headers: [], rows: [] };
  const raw = XLSX.utils.sheet_to_json<(string | number)[]>(sheet, { header: 1, defval: "" });
  if (raw.length === 0) return { headers: [], rows: [] };
  const headers = (raw[0] ?? []).map((c) => String(c ?? "").trim());
  const rows = raw.slice(1).map((r) => headers.map((_, i) => String(r[i] ?? "").trim()));
  return { headers, rows };
}

function buildFromTable(
  headers: string[],
  rows: string[][],
  questionColumn: string,
): Omit<ParsedQuestionnaire, "ok" | "error" | "errorCode" | "sheets" | "selectedSheet"> {
  const colIdx = Math.max(0, headers.indexOf(questionColumn));
  const questionTexts = rows.map((r) => (r[colIdx] ?? "").trim()).filter(Boolean);
  const seen = new Map<string, number>();
  const duplicateQuestions: string[] = [];
  for (const q of questionTexts) {
    const key = q.toLowerCase();
    seen.set(key, (seen.get(key) ?? 0) + 1);
    if (seen.get(key)! > 1 && !duplicateQuestions.includes(q)) duplicateQuestions.push(q);
  }
  const previewRows = rows.slice(0, 5).map((r) => r.slice(0, Math.min(4, r.length)));
  return {
    columns: headers.length ? headers : ["Column 1"],
    questionColumn: headers[colIdx] ?? questionColumn,
    previewRows,
    questionTexts,
    duplicateQuestions,
    rowCount: questionTexts.length,
  };
}

export async function parseQuestionnaireFile(
  file: File,
  opts?: { sheetName?: string; questionColumn?: string; stripDuplicates?: boolean },
): Promise<ParsedQuestionnaire> {
  const name = file.name.toLowerCase();
  if (!name.endsWith(".csv") && !name.endsWith(".xlsx") && !name.endsWith(".xls")) {
    return {
      ok: false,
      error: "Use a CSV or XLSX file.",
      errorCode: "wrong_type",
      sheets: [],
      selectedSheet: "",
      columns: [],
      questionColumn: "",
      previewRows: [],
      questionTexts: [],
      duplicateQuestions: [],
      rowCount: 0,
    };
  }
  if (file.size > QUESTIONNAIRE_MAX_BYTES) {
    return {
      ok: false,
      error: `File is too large (max ${QUESTIONNAIRE_MAX_BYTES / (1024 * 1024)} MB).`,
      errorCode: "too_large",
      sheets: [],
      selectedSheet: "",
      columns: [],
      questionColumn: "",
      previewRows: [],
      questionTexts: [],
      duplicateQuestions: [],
      rowCount: 0,
    };
  }

  try {
    if (name.endsWith(".csv")) {
      const text = await file.text();
      if (!text.trim()) {
        return fail("empty", "This file has no rows.");
      }
      const { headers, rows } = parseCsv(text);
      if (rows.length === 0) return fail("empty", "This file has no data rows.");
      const qCol = opts?.questionColumn ?? detectQuestionColumn(headers.length ? headers : ["Column 1"]);
      const built = buildFromTable(headers.length ? headers : ["Column 1"], rows, qCol);
      if (built.rowCount === 0) return fail("no_column", "No question text found in the selected column.");
      if (built.rowCount > QUESTIONNAIRE_MAX_ROWS) {
        return fail("too_many_rows", `Too many questions (max ${QUESTIONNAIRE_MAX_ROWS}).`);
      }
      return {
        ok: true,
        sheets: [{ name: "CSV", rowCount: built.rowCount }],
        selectedSheet: "CSV",
        ...built,
        questionTexts: opts?.stripDuplicates ? [...new Set(built.questionTexts.map((q) => q))] : built.questionTexts,
      };
    }

    const buf = await file.arrayBuffer();
    let workbook: XLSX.WorkBook;
    try {
      workbook = XLSX.read(buf, { type: "array" });
    } catch {
      return fail("unreadable", "Could not read this spreadsheet (encoding or password protection).");
    }
    const sheets = workbook.SheetNames.map((n) => {
      const { rows } = sheetToTable(workbook, n);
      return { name: n, rowCount: rows.length };
    });
    const selectedSheet = opts?.sheetName && sheets.some((s) => s.name === opts.sheetName) ? opts.sheetName : sheets[0]?.name ?? "";
    const { headers, rows } = sheetToTable(workbook, selectedSheet);
    if (rows.length === 0) return fail("empty", "The selected sheet has no data rows.");
    const qCol = opts?.questionColumn ?? detectQuestionColumn(headers.length ? headers : ["Column 1"]);
    const built = buildFromTable(headers.length ? headers : ["Column 1"], rows, qCol);
    if (built.rowCount === 0) return fail("no_column", "No question text found. Pick a different column.");
    if (built.rowCount > QUESTIONNAIRE_MAX_ROWS) {
      return fail("too_many_rows", `Too many questions (max ${QUESTIONNAIRE_MAX_ROWS}).`);
    }
    return {
      ok: true,
      sheets,
      selectedSheet,
      ...built,
      questionTexts: opts?.stripDuplicates ? [...new Set(built.questionTexts.map((q) => q))] : built.questionTexts,
    };
  } catch {
    return fail("unreadable", "Could not read this file.");
  }
}

function fail(code: ParsedQuestionnaire["errorCode"], message: string): ParsedQuestionnaire {
  return {
    ok: false,
    error: message,
    errorCode: code,
    sheets: [],
    selectedSheet: "",
    columns: [],
    questionColumn: "",
    previewRows: [],
    questionTexts: [],
    duplicateQuestions: [],
    rowCount: 0,
  };
}

export function downloadQuestionnaireTemplateCsv() {
  const csv = "question,section,expected_answer\nSample security question?,General,\n";
  const blob = new Blob([csv], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = "questionnaire-template.csv";
  a.click();
  URL.revokeObjectURL(url);
}
