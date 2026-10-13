from pydantic import BaseModel, Field


class TenantStorageResponse(BaseModel):
    storage_mode: str
    connection_method: str
    status: str
    host: str | None = None
    port: int | None = None
    database_name: str | None = None
    schema_name: str
    ssl_mode: str
    username: str | None = None
    has_credentials: bool = False
    schema_version: int
    last_health_status: str | None = None
    last_health_summary: str | None = None
    last_latency_ms: int | None = None
    last_health_check_at: str | None = None
    paused: bool = False


class TenantStorageConfigureRequest(BaseModel):
    storage_mode: str = Field(description="managed_colocated or customer_postgres")
    connection_method: str = "public_tls"
    host: str | None = None
    port: int | None = 5432
    database_name: str | None = None
    schema_name: str = "public"
    ssl_mode: str = "verify-full"
    username: str | None = None
    password: str | None = Field(default=None, description="Stored in secret store only; never returned")


class PreflightCheckResponse(BaseModel):
    id: str
    title: str
    status: str
    detail: str


class PreflightReportResponse(BaseModel):
    ok: bool
    latency_ms: int | None = None
    checks: list[PreflightCheckResponse]
