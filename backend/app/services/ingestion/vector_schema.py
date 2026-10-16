"""Detect a pgvector column size that does not match EMBEDDING_DIMENSIONS."""

from __future__ import annotations

import logging

from sqlalchemy import text
from sqlalchemy.engine import Engine

from app.core.config import Settings

logger = logging.getLogger("aqrem.providers")

VECTOR_COLUMNS = (("evidence_items", "embedding"), ("answer_library_entries", "question_embedding"))


class VectorDimensionMismatch(RuntimeError):
    pass


def vector_mismatch_message(table: str, column: str, db_dim: int, expected: int) -> str:
    return (
        f"Database column {table}.{column} is vector({db_dim}) but EMBEDDING_DIMENSIONS={expected}. "
        "Embeddings of the configured size cannot be stored. Fix: either set EMBEDDING_DIMENSIONS="
        f"{db_dim} to match the existing data, or migrate the column (see docs/azure-openai-setup.md, "
        "'Changing the embedding size'): "
        f"ALTER TABLE {table} ALTER COLUMN {column} TYPE vector({expected}) USING NULL; "
        "then restart and click 'Re-index all documents'."
    )


def read_vector_dimensions(conn, table: str, column: str) -> int | None:
    row = conn.execute(
        text(
            """
            SELECT a.atttypmod FROM pg_attribute a
            JOIN pg_class c ON c.oid = a.attrelid
            WHERE c.relname = :table AND a.attname = :column AND NOT a.attisdropped
            LIMIT 1
            """
        ),
        {"table": table, "column": column},
    ).first()
    if row is None or row[0] is None or int(row[0]) <= 0:
        return None
    return int(row[0])


def find_vector_mismatches(conn, expected: int) -> list[tuple[str, str, int]]:
    out: list[tuple[str, str, int]] = []
    for table, column in VECTOR_COLUMNS:
        dim = read_vector_dimensions(conn, table, column)
        if dim is not None and dim != expected:
            out.append((table, column, dim))
    return out


def check_vector_column_dimensions(engine: Engine, settings: Settings) -> list[str]:
    """Log (and in production, fail fast) when vector columns disagree with config."""
    expected = settings.embedding_dimensions
    try:
        with engine.connect() as conn:
            mismatches = find_vector_mismatches(conn, expected)
    except Exception:  # noqa: BLE001
        logger.exception("Could not inspect pgvector column sizes")
        return []
    messages = [vector_mismatch_message(t, c, d, expected) for t, c, d in mismatches]
    for msg in messages:
        logger.error("EMBEDDING DIMENSION MISMATCH: %s", msg)
    if messages and settings.app_env == "production":
        raise VectorDimensionMismatch(messages[0])
    if not messages:
        logger.info("pgvector columns match EMBEDDING_DIMENSIONS=%s", expected)
    return messages
