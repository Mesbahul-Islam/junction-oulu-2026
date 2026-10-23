from django.db.models import Q
from rest_framework.permissions import BasePermission


def has_role(user, role, *, language=None, community=None):
    """True if the user holds `role` (optionally scoped to a language/community)."""
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    qs = user.roles.filter(role=role)
    # A role with no language/community scope is global and always matches.
    if language is not None:
        qs = qs.filter(Q(language=language) | Q(language__isnull=True) | Q(language=""))
    if community is not None:
        qs = qs.filter(Q(community=community) | Q(community__isnull=True))
    return qs.exists()


class HasRole(BasePermission):
    """Use as `permission_classes = [HasRole.for_roles("editor", "news_editor")]`."""

    roles: tuple[str, ...] = ()

    @classmethod
    def for_roles(cls, *roles):
        return type(f"HasRole_{'_'.join(roles)}", (cls,), {"roles": roles})

    def has_permission(self, request, view):
        return any(has_role(request.user, r) for r in self.roles)
