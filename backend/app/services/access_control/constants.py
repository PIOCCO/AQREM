"""Document visibility modes (who can SEE content)."""

VISIBILITY_ALL_STAFF = "all_staff"
VISIBILITY_GROUPS = "groups"
VISIBILITY_USERS = "users"
VISIBILITY_ADMINS_ONLY = "admins_only"
VISIBILITY_UNSET = "unset"

DEFAULT_GROUP_SPECS: tuple[tuple[str, str], ...] = (
    ("All staff", "all-staff"),
    ("Management", "management"),
    ("HR", "hr"),
    ("Finance", "finance"),
    ("IT", "it"),
    ("Sales", "sales"),
)
