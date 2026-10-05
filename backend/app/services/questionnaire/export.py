import csv
import io
from dataclasses import dataclass
from uuid import UUID

from openpyxl import Workbook
from sqlalchemy.orm import Session, joinedload

from app.models.enums import AnswerStatus
from app.models.questionnaire import Answer, AnswerEvidenceLink, Question, Questionnaire
from app.models.evidence import EvidenceItem


EXPORT_COLUMNS = [
    "Question ID",
    "Section",
    "Question",
    "Answer",
    "Status",
    "Confidence",
    "Evidence Strength",
    "Evidence",
    "Expected Answer",
    "Existing Answer",
]


@dataclass
class ExportRow:
    question_id: str
    section: str
    question: str
    answer: str
    status: str
    confidence: str
    evidence_strength: str
    evidence: str
    expected_answer: str
    existing_answer: str

    def as_list(self) -> list[str]:
        return [
            self.question_id,
            self.section,
            self.question,
            self.answer,
            self.status,
            self.confidence,
            self.evidence_strength,
            self.evidence,
            self.expected_answer,
            self.existing_answer,
        ]


def _display_status(answer: Answer | None) -> str:
    if answer is None:
        return "No answer"
    mapping = {
        AnswerStatus.DRAFT.value: "Draft",
        AnswerStatus.NEEDS_REVIEW.value: "Review",
        AnswerStatus.APPROVED.value: "Approved",
        AnswerStatus.REJECTED.value: "Rejected",
    }
    base = mapping.get(answer.status, answer.status)
    if answer.potentially_stale:
        return f"{base} (Potentially stale)"
    if answer.evidence_sufficiency == "insufficient":
        return f"{base} (Insufficient evidence)"
    return base


def _final_answer_text(answer: Answer | None) -> str:
    if answer is None:
        return ""
    if answer.status == AnswerStatus.APPROVED.value and answer.approved_text:
        return answer.approved_text
    return answer.draft_text or ""


def _evidence_summary(db: Session, answer: Answer | None) -> tuple[str, str]:
    if answer is None:
        return "", ""
    links = db.query(AnswerEvidenceLink).filter(AnswerEvidenceLink.answer_id == answer.id).all()
    if not links:
        return "", ""
    parts: list[str] = []
    strengths: list[str] = []
    for link in links:
        item = db.get(EvidenceItem, link.evidence_item_id)
        if item is None:
            continue
        strength = link.evidence_strength or item.evidence_strength or ""
        if strength:
            strengths.append(strength)
        loc = item.file_path
        if item.line_start is not None:
            loc += f" (lines {item.line_start}"
            if item.line_end is not None and item.line_end != item.line_start:
                loc += f"–{item.line_end}"
            loc += ")"
        if item.repository:
            loc = f"{item.repository}: {loc}"
        if item.commit_hash:
            loc += f" @{item.commit_hash[:8]}"
        parts.append(loc)
    strength_label = max(strengths, key=lambda s: strengths.count(s)) if strengths else ""
    return strength_label, "; ".join(parts)


def build_export_rows(
    db: Session,
    *,
    organization_id: UUID,
    questionnaire_id: UUID,
    approved_only: bool = False,
    needs_review_only: bool = False,
) -> list[ExportRow]:
    questionnaire = (
        db.query(Questionnaire)
        .filter(Questionnaire.id == questionnaire_id, Questionnaire.organization_id == organization_id)
        .first()
    )
    if questionnaire is None:
        raise ValueError("Questionnaire not found")

    questions = (
        db.query(Question)
        .options(joinedload(Question.answer))
        .filter(Question.questionnaire_id == questionnaire_id)
        .order_by(Question.sort_order.asc(), Question.external_id.asc())
        .all()
    )

    rows: list[ExportRow] = []
    for question in questions:
        answer = question.answer
        if approved_only and (answer is None or answer.status != AnswerStatus.APPROVED.value):
            continue
        if needs_review_only and (answer is None or answer.status != AnswerStatus.NEEDS_REVIEW.value):
            continue
        strength, evidence = _evidence_summary(db, answer)
        rows.append(
            ExportRow(
                question_id=question.external_id,
                section=question.section or "",
                question=question.text,
                answer=_final_answer_text(answer),
                status=_display_status(answer),
                confidence=answer.confidence if answer else "",
                evidence_strength=strength,
                evidence=evidence,
                expected_answer=question.expected_answer or "",
                existing_answer=question.existing_answer or "",
            )
        )
    return rows


def render_csv_bytes(rows: list[ExportRow]) -> bytes:
    buffer = io.StringIO()
    writer = csv.writer(buffer, quoting=csv.QUOTE_MINIMAL, lineterminator="\n")
    writer.writerow(EXPORT_COLUMNS)
    for row in rows:
        writer.writerow(row.as_list())
    return buffer.getvalue().encode("utf-8-sig")


def render_xlsx_bytes(rows: list[ExportRow]) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = "Questionnaire"
    ws.append(EXPORT_COLUMNS)
    for row in rows:
        ws.append(row.as_list())
    for column_cells in ws.columns:
        max_len = 0
        column = column_cells[0].column_letter
        for cell in column_cells:
            if cell.value:
                max_len = max(max_len, len(str(cell.value)))
        ws.column_dimensions[column].width = min(max_len + 2, 80)
    out = io.BytesIO()
    wb.save(out)
    return out.getvalue()
