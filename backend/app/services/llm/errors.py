"""User-safe model / gateway errors (no prompt or document text)."""

from __future__ import annotations


ASSISTANT_UNAVAILABLE_MESSAGE = "The assistant is temporarily unavailable, please try again."


class ModelServiceError(Exception):
    """Raised when the model gateway cannot complete a request."""

    def __init__(
        self,
        *,
        code: str,
        user_message: str,
        status_code: int | None = None,
        retryable: bool = False,
        admin_message: str | None = None,
    ) -> None:
        self.code = code
        self.admin_message = admin_message or user_message
        self.user_message = user_message
        self.status_code = status_code
        self.retryable = retryable
        super().__init__(user_message)


class EmbeddingDimensionMismatchError(ModelServiceError):
    def __init__(self, *, expected: int, actual: int) -> None:
        super().__init__(
            code="embedding_dimension_mismatch",
            user_message=(
                "Document indexing is paused: embedding size does not match this environment "
                f"({actual} vs expected {expected}). Contact your administrator to re-index "
                "after aligning the embedding model."
            ),
            status_code=500,
            retryable=False,
            admin_message=(
                f"Embedding size mismatch: the embedding deployment returned {actual} dimensions but "
                f"EMBEDDING_DIMENSIONS={expected}. Set EMBEDDING_DIMENSIONS to the model's size "
                "(text-embedding-3-small = 1536), run the vector migration, then Re-index all documents."
            ),
        )
        self.expected = expected
        self.actual = actual
