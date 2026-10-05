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
