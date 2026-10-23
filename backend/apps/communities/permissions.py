from rest_framework.permissions import SAFE_METHODS, BasePermission, IsAdminUser

from apps.common.permissions import HasRole

from .models import Post
from .services import is_member

# FR-3.14: sources/glossary/context are configured by admins (role "admin", staff or superuser).
IsCommunityAdmin = HasRole.for_roles("admin") | IsAdminUser


class IsCommunityMember(BasePermission):
    """FR-1.2: posts are visible/writable only for members of the community in the URL."""

    message = "Join this community to see and write posts."

    def has_permission(self, request, view):
        community = getattr(view, "community", None)
        return community is not None and is_member(request.user, community)


class IsAuthorOrReadOnly(BasePermission):
    def has_object_permission(self, request, view, obj: Post):
        return request.method in SAFE_METHODS or obj.author_id == request.user.id
