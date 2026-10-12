from enum import StrEnum


class SourceType(StrEnum):
    FILE_UPLOAD = "file_upload"
    GITHUB = "github"
    FOLDER_ARCHIVE = "folder_archive"


class EvidenceScope(StrEnum):
    ORGANIZATION = "organization"
    PROJECT = "project"
    SOURCE = "source"


class SourceStatus(StrEnum):
    PENDING = "pending"
    INDEXING = "indexing"
    READY = "ready"
    ERROR = "error"


class SyncJobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class EvidenceStrength(StrEnum):
    DIRECT = "direct"
    STRONG = "strong"
    MODERATE = "moderate"
    WEAK = "weak"
    INSUFFICIENT = "insufficient"


class QuestionnaireStatus(StrEnum):
    DRAFT = "draft"
    IN_PROGRESS = "in_progress"
    IN_REVIEW = "in_review"
    COMPLETED = "completed"


class AnswerStatus(StrEnum):
    DRAFT = "draft"
    NEEDS_REVIEW = "needs_review"
    APPROVED = "approved"
    REJECTED = "rejected"


class LibraryEntryStatus(StrEnum):
    APPROVED = "approved"
    NEEDS_REVIEW = "needs_review"


class AnswerGenerationSource(StrEnum):
    RETRIEVAL_LLM = "retrieval_llm"
    LIBRARY_REUSE = "library_reuse"
    LIBRARY_ADAPTED = "library_adapted"
    STALE_REGENERATION = "stale_regeneration"


class StalenessEventStatus(StrEnum):
    OPEN = "open"
    RESOLVED = "resolved"


class AnswerOutcome(StrEnum):
    """Structured employee-facing result for chat and RAG answers."""

    ANSWERED = "answered"
    PARTIALLY_ANSWERED = "partially_answered"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    CONFLICTING_EVIDENCE = "conflicting_evidence"
    CLARIFICATION_REQUIRED = "clarification_required"
    ACCESS_DENIED = "access_denied"
    SOURCE_UNAVAILABLE = "source_unavailable"
    ACTION_NOT_SUPPORTED = "action_not_supported"
