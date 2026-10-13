import re

_DSN_PATTERN = re.compile(
    r"(postgresql(?:\+[\w]+)?://)([^@\s/]+)(/[^\s?]+)?(\?[^\s'\"]+)?",
    re.IGNORECASE,
)
_USERINFO = re.compile(
    r"(postgresql(?:\+[\w]+)?://)([^:]+):([^@/]+)@",
    re.IGNORECASE,
)


def mask_database_url(url: str | None) -> str:
    if not url:
        return ""
    return _USERINFO.sub(r"\1\2:***@", url)


def mask_message(text: str) -> str:
    if not text:
        return text
    return _DSN_PATTERN.sub("postgresql://***", text)
