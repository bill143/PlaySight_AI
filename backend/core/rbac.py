"""Role-based access control (RBAC) helpers.

Roles are simple strings stored on the `User` model. Permissions are derived
from a static role -> permission-set mapping which keeps authorization
decisions fast and easy to reason about for an MVP.
"""

from __future__ import annotations

from enum import StrEnum


class Role(StrEnum):
    ADMIN = "admin"
    COACH = "coach"
    ANALYST = "analyst"
    VIEWER = "viewer"


class Permission(StrEnum):
    MATCH_CREATE = "match:create"
    MATCH_READ = "match:read"
    MATCH_DELETE = "match:delete"
    PLAYER_READ = "player:read"
    REPORT_READ = "report:read"
    HIGHLIGHT_READ = "highlight:read"
    PUBLISH_YOUTUBE = "publish:youtube"
    ARTIFACT_DOWNLOAD = "artifact:download"
    USER_MANAGE = "user:manage"


ROLE_PERMISSIONS: dict[Role, set[Permission]] = {
    Role.ADMIN: set(Permission),
    Role.COACH: {
        Permission.MATCH_CREATE,
        Permission.MATCH_READ,
        Permission.PLAYER_READ,
        Permission.REPORT_READ,
        Permission.HIGHLIGHT_READ,
        Permission.PUBLISH_YOUTUBE,
        Permission.ARTIFACT_DOWNLOAD,
    },
    Role.ANALYST: {
        Permission.MATCH_READ,
        Permission.PLAYER_READ,
        Permission.REPORT_READ,
        Permission.HIGHLIGHT_READ,
        Permission.ARTIFACT_DOWNLOAD,
    },
    Role.VIEWER: {
        Permission.MATCH_READ,
        Permission.PLAYER_READ,
        Permission.REPORT_READ,
        Permission.HIGHLIGHT_READ,
    },
}


def role_has_permission(role: str, permission: Permission) -> bool:
    """Check whether a given role string grants the requested permission."""
    try:
        role_enum = Role(role)
    except ValueError:
        return False
    return permission in ROLE_PERMISSIONS.get(role_enum, set())


class PermissionDenied(Exception):
    """Raised when a user's role does not grant a required permission."""


def require_permission(role: str, permission: Permission) -> None:
    """Raise `PermissionDenied` if `role` does not grant `permission`."""
    if not role_has_permission(role, permission):
        raise PermissionDenied(f"Role '{role}' lacks permission '{permission.value}'")
