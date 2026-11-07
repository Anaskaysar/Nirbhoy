from rest_framework.permissions import BasePermission

REVIEWER_GROUP = "reviewers"


def is_reviewer(user) -> bool:
    return bool(
        user
        and user.is_authenticated
        and (user.is_staff or user.groups.filter(name=REVIEWER_GROUP).exists())
    )


class IsReviewer(BasePermission):
    message = "Only verified reviewers can access this."

    def has_permission(self, request, view):
        return is_reviewer(request.user)
