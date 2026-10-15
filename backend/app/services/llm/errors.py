"""User-safe model / gateway errors (no prompt or document text)."""

from __future__ import annotations


class ModelServiceError(Exception):
    """Raised when the model gateway cannot complete a request."""

    def __init__(
        self,
        *,
        code: str,
        user_message: str,
        status_code: int | None = None,
        retryable: bool = False,
    ) -> None:
        self.code = code
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
        )
