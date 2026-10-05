from app.models.enums import EvidenceStrength


def classify_evidence_strength(file_path: str, content_type: str, source_type: str) -> str:
    lower = file_path.lower()
    if source_type == "github" and (lower.endswith(".tf") or "/terraform/" in lower):
        return EvidenceStrength.DIRECT.value
    if "policy" in lower or lower.endswith("policy.pdf") or "/policies/" in lower:
        return EvidenceStrength.STRONG.value
    if lower.endswith(".md") and ("architecture" in lower or "design" in lower):
        return EvidenceStrength.STRONG.value
    if lower.endswith("readme.md"):
        return EvidenceStrength.WEAK.value
    if content_type.startswith("text/"):
        return EvidenceStrength.MODERATE.value
    return EvidenceStrength.MODERATE.value
