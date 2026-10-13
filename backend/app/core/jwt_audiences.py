"""JWT audience constants — one per application surface."""

AUD_PLATFORM = "aqrem-master"
AUD_ORG_ADMIN = "aqrem-org-admin"
AUD_EMPLOYEE = "aqrem-employee"

TENANT_AUDIENCES = (AUD_ORG_ADMIN, AUD_EMPLOYEE)
ALL_AUDIENCES = (AUD_PLATFORM, AUD_ORG_ADMIN, AUD_EMPLOYEE)
