/** Client-side preview before upload (does not replace server validation). */
export async function previewQuestionnaireFile(file: File): Promise<{ rowEstimate: number; note: string }> {
  const name = file.name.toLowerCase();
  if (name.endsWith(".csv")) {
    const text = await file.text();
    const lines = text.split(/\r?\n/).filter((l) => l.trim().length > 0);
    const dataRows = Math.max(0, lines.length - 1);
    return {
      rowEstimate: dataRows,
      note: `CSV preview: ~${dataRows} data row(s). Upload will replace existing questions on this questionnaire.`,
    };
  }
  if (name.endsWith(".xlsx") || name.endsWith(".xls")) {
    return {
      rowEstimate: 0,
      note: "Spreadsheet selected. Row count will be determined during server import.",
    };
  }
  return { rowEstimate: 0, note: "Unsupported preview for this file type." };
}
