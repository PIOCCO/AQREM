"""Structured logging with secret/content redaction.

LOG_FORMAT=json -> one JSON object per line (ts, level, logger, msg, + safe extras).
A RedactionFilter is attached to every handler in both formats:
  * secrets in messages: URL credentials, AccountKey/SharedAccessSignature/sig=, Bearer tokens, JWTs,
    api-key/password/secret/token=value pairs, PEM blocks;
  * content fields in `extra`: content, document_text, text, question, answer, prompt, messages, chunk(s)
    are replaced by "[redacted len=N]".
Also keeps a small in-memory ring buffer of recent WARNING+ records (already redacted) for the
diagnostics bundle.
"""

from __future__ import annotations

import collections
import json
import logging
import re
import threading
import time

CONTENT_KEYS = frozenset({
    "content", "document_text", "text", "question", "answer", "prompt", "messages", "chunk", "chunks",
    "query", "body", "html", "file_content", "embedding", "embeddings",
})
SECRET_KEYS = frozenset({"password", "secret", "token", "api_key", "apikey", "authorization", "connection_string",
                         "database_url", "secret_key", "access_token", "refresh_token", "setup_token", "license_key"})

_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----", re.S), "[redacted-private-key]"),
    (re.compile(r"(?P<scheme>[a-z][a-z0-9+.-]*://)(?P<user>[^:/@\s]+):(?P<pw>[^@\s/]+)@", re.I), r"\g<scheme>\g<user>:***@"),
    (re.compile(r"(AccountKey|SharedAccessKey|SharedAccessSignature)=[^;\s\"']+", re.I), r"\1=***"),
    (re.compile(r"([?&](?:sig|se|sp|sv|skoid|sktid)=)[^&\s\"']+", re.I), r"\1***"),
    (re.compile(r"(Bearer\s+)[A-Za-z0-9._~+/=-]{8,}", re.I), r"\1***"),
    (re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b"), "[redacted-jwt]"),
    (re.compile(r"((?:api[-_]?key|password|passwd|pwd|secret|token|client_secret)[\"']?\s*[:=]\s*[\"']?)[^\s\"',;&]+", re.I), r"\1***"),
    (re.compile(r"\bsk-[A-Za-z0-9_-]{16,}\b"), "[redacted-key]"),
    (re.compile(r"(setup[-_]?token[\"']?\s*[:=]\s*[\"']?)[^\s\"',;&]+", re.I), r"\1***"),
]


_LITERAL_SECRETS: set[str] = set()
_literal_lock = threading.Lock()


def register_secret(value: str | None) -> None:
    """Redact this exact value wherever it appears in a log line (e.g. the live setup token)."""
    v = (value or "").strip()
    if len(v) >= 8:
        with _literal_lock:
            _LITERAL_SECRETS.add(v)


def redact_text(value: str) -> str:
    for pat, repl in _PATTERNS:
        value = pat.sub(repl, value)
    if _LITERAL_SECRETS:
        for secret in tuple(_LITERAL_SECRETS):
            if secret in value:
                value = value.replace(secret, "***")
    return value


def _redact_value(key: str, value):
    k = key.lower()
    if k in SECRET_KEYS:
        return "***"
    if k in CONTENT_KEYS:
        try:
            n = len(value)  # type: ignore[arg-type]
        except Exception:
            n = -1
        return f"[redacted len={n}]"
    if isinstance(value, str):
        return redact_text(value)
    if isinstance(value, dict):
        return {kk: _redact_value(str(kk), vv) for kk, vv in value.items()}
    if isinstance(value, (list, tuple)):
        return [_redact_value(key, v) for v in value]
    return value


_STD_ATTRS = frozenset(vars(logging.makeLogRecord({})).keys()) | {"message", "asctime"}


class RedactionFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        try:
            msg = record.getMessage()
        except Exception:
            msg = str(record.msg)
        record.msg = redact_text(msg)
        record.args = None
        for key in list(vars(record)):
            if key not in _STD_ATTRS:
                setattr(record, key, _redact_value(key, getattr(record, key)))
        if record.exc_text:
            record.exc_text = redact_text(record.exc_text)
        return True


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        out = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(record.created)) + f".{int(record.msecs):03d}Z",
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        for key, val in vars(record).items():
            if key not in _STD_ATTRS and not key.startswith("_"):
                out[key] = val
        if record.exc_info:
            out["exc_type"] = record.exc_info[0].__name__ if record.exc_info[0] else None
            out["exc"] = redact_text(self.formatException(record.exc_info))
        return json.dumps(out, default=str)


class RecentErrors(logging.Handler):
    def __init__(self, capacity: int = 200) -> None:
        super().__init__(level=logging.WARNING)
        self.buf: collections.deque[dict] = collections.deque(maxlen=capacity)
        self.lock2 = threading.Lock()
        self.addFilter(RedactionFilter())

    def emit(self, record: logging.LogRecord) -> None:
        with self.lock2:
            self.buf.append({
                "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(record.created)),
                "level": record.levelname, "logger": record.name,
                "msg": record.getMessage()[:500],
                "exc_type": record.exc_info[0].__name__ if record.exc_info and record.exc_info[0] else None,
            })

    def snapshot(self) -> list[dict]:
        with self.lock2:
            return list(self.buf)


recent_errors = RecentErrors()
_configured = False


def configure_logging(log_format: str = "text") -> None:
    """Idempotent. Installs redaction on root and aqrem loggers' handlers."""
    global _configured
    root = logging.getLogger()
    if not _configured:
        if (log_format or "").lower() == "json":
            handler = logging.StreamHandler()
            handler.setFormatter(JsonFormatter())
            handler.addFilter(RedactionFilter())
            for h in list(root.handlers):
                root.removeHandler(h)
            root.addHandler(handler)
            for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
                lg = logging.getLogger(name)
                for h in list(lg.handlers):
                    lg.removeHandler(h)
                lg.propagate = True
        if root.level > logging.INFO or root.level == logging.NOTSET:
            root.setLevel(logging.INFO)
        root.addHandler(recent_errors)
        _configured = True
    for name in ("", "aqrem", "aqrem.providers", "aqrem.rag", "uvicorn", "uvicorn.error", "uvicorn.access", "celery"):
        for h in logging.getLogger(name).handlers:
            if not any(isinstance(f, RedactionFilter) for f in h.filters):
                h.addFilter(RedactionFilter())
