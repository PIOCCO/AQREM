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
