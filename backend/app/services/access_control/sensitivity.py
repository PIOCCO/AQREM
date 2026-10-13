import re

_SENSITIVE_NAME = re.compile(
    r"(payroll|salary|compensation|disciplinary|termination|contract|iban|bank|ssn|national.?id|passport)",
    re.I,
)
_SENSITIVE_CONTENT = re.compile(
    r"(salary|iban|account.?number|social.?security|confidential.?hr|disciplinary)",
    re.I,
)


def detect_sensitive(*, file_name: str, content_sample: bytes | None = None) -> tuple[bool, str]:
    if _SENSITIVE_NAME.search(file_name or ""):
        return True, "This file name looks like HR, payroll, or legal content. We pre-selected Admins only."
    if content_sample:
        try:
            text = content_sample[:8000].decode("utf-8", errors="ignore")
        except Exception:
            text = ""
        if _SENSITIVE_CONTENT.search(text):
            return True, "The file content looks sensitive. We pre-selected Admins only."
    return False, ""
