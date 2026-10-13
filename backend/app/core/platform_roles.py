from enum import StrEnum


class PlatformRole(StrEnum):
    SUPER_ADMIN = "SUPER_ADMIN"
    PLATFORM_SUPPORT = "PLATFORM_SUPPORT"
    PLATFORM_BILLING = "PLATFORM_BILLING"


PLATFORM_ROLE_LABELS: dict[PlatformRole, str] = {
    PlatformRole.SUPER_ADMIN: "Super admin",
    PlatformRole.PLATFORM_SUPPORT: "Support",
    PlatformRole.PLATFORM_BILLING: "Billing",
}
