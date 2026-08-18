from rest_framework.permissions import BasePermission
from .models import Runner


class IsRunner(BasePermission):
    def has_permission(self, request, view):
        return isinstance(request.user, Runner)

