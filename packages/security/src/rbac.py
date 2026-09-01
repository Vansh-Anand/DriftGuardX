"""
DriftGuard-X v2 — Role Based Access Control
PRIVATE — All Rights Reserved.
"""
from typing import Any, Callable
from functools import wraps

from packages.contracts.src.recovery_models import RBACRole


class UnauthorizedError(Exception):
    pass


def require_role(required_role: RBACRole):
    """
    A decorator that checks if the current user/context possesses the required role.
    In a real web framework (like FastAPI), this would be implemented as a Dependency (Depends).
    Here we implement it as a decorator for services/functions.
    """
    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # In a real environment, the current user identity/role is extracted 
            # from the request context, JWT, or ThreadLocal storage.
            # For demonstration, we assume `current_user_role` is passed in kwargs
            # or we simulate an elevated context.
            
            user_role_str = kwargs.get("user_role", RBACRole.SYSTEM_ADMIN.value)
            
            try:
                user_role = RBACRole(user_role_str)
            except ValueError:
                raise UnauthorizedError(f"Invalid role: {user_role_str}")
                
            # Role Hierarchy
            # SYSTEM_ADMIN > APPROVER > OPERATOR > INVESTIGATOR > VIEWER
            hierarchy = {
                RBACRole.VIEWER: 0,
                RBACRole.INVESTIGATOR: 1,
                RBACRole.OPERATOR: 2,
                RBACRole.APPROVER: 3,
                RBACRole.SYSTEM_ADMIN: 4
            }
            
            if hierarchy[user_role] < hierarchy[required_role]:
                raise UnauthorizedError(
                    f"Action requires {required_role.value} privileges. "
                    f"User only has {user_role.value}."
                )
                
            return func(*args, **kwargs)
        return wrapper
    return decorator
