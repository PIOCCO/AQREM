from uuid import UUID

from pydantic import BaseModel, Field


class AccessGroupResponse(BaseModel):
    id: UUID
    name: str
    slug: str
    is_system: bool
    member_count: int


class AccessGroupCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=128)


class AccessGroupMembersRequest(BaseModel):
    user_ids: list[UUID] = Field(min_length=1)


class DocumentVisibilityRequest(BaseModel):
    visibility_mode: str = Field(min_length=1, max_length=32)
    visibility_group_ids: list[UUID] = Field(default_factory=list)
    visibility_user_ids: list[UUID] = Field(default_factory=list)


class BulkDocumentVisibilityRequest(DocumentVisibilityRequest):
    document_ids: list[UUID] = Field(min_length=1)


class PreviewAsRequest(BaseModel):
    user_id: UUID
    query: str = Field(min_length=1, max_length=2000)


class PreviewAsResponse(BaseModel):
    user_id: UUID
    query: str
    accessible_document_count: int
    answer_preview: str
    citation_file_names: list[str]
