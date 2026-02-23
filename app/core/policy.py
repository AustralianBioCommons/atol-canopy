from __future__ import annotations

from functools import wraps
from typing import Any, Callable, Dict, List, Optional
from inspect import iscoroutinefunction

from fastapi import status

from app.core.errors import AppError
from app.models.user import User

# Centralized authorization policy
POLICY: Dict[str, List[str]] = {
    # Organisms
    "organisms:read_sensitive": ["admin", "curator", "broker", "genome_launcher"],
    "organisms:create": ["curator", "admin"],
    "organisms:update": ["curator", "admin"],
    "organisms:delete": ["admin", "superuser"],
    "organisms:bulk_import": ["curator", "admin"],
    # Samples
    "samples:create": ["curator", "admin"],
    "samples:update": ["curator", "admin"],
    "samples:delete": ["admin", "superuser"],
    "samples:bulk_import": ["curator", "admin"],
    "samples:read_sensitive": ["admin", "curator", "broker", "genome_launcher"],
    # Sample submissions
    "sample_submissions:read": ["admin", "curator", "broker", "genome_launcher"],
    "sample_submissions:write": ["curator", "admin"],
    # Experiments
    "experiments:create": ["curator", "admin"],
    "experiments:update": ["curator", "admin"],
    "experiments:bulk_import": ["curator", "admin"],
    "experiments:delete": ["admin", "superuser"],
    # Experiment submissions
    "experiment_submissions:read": ["admin", "curator", "broker", "genome_launcher"],
    "experiment_submissions:write": ["curator", "admin"],
    # Reads
    "reads:create": ["curator", "admin"],
    "reads:update": ["curator", "admin"],
    "reads:delete": ["admin", "superuser"],
    # Read submissions
    "read_submissions:read": ["admin", "curator", "broker", "genome_launcher"],
    "read_submissions:write": ["curator", "admin"],
    # Projects
    "projects:create": ["curator", "admin"],
    "projects:update": ["curator", "admin"],
    "projects:delete": ["admin", "superuser"],
    # Assemblies
    "assemblies:write": ["curator", "admin"],
    "assemblies:delete": ["admin", "superuser"],
    # Genome notes
    "genome_notes:write": ["curator", "admin"],
    # BPA initiatives
    "bpa_initiatives:write": ["curator", "admin"],
    "users:read": ["admin", "superuser"],
    "users:create": ["admin", "superuser"],
}


def check_policy(user: User, action: str) -> None:
    roles = POLICY.get(action)
    if roles is None:
        raise AppError(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            code="policy_missing",
            message=f"Policy not defined for action '{action}'",
        )
    if user.is_superuser:
        return
    if any(role in user.roles for role in roles):
        return
    raise AppError(
        status_code=status.HTTP_403_FORBIDDEN,
        code="forbidden",
        message="Not enough permissions",
    )


def _check_policy_from_kwargs(action: str, kwargs: Dict[str, Any]) -> None:
    current_user: Optional[User] = kwargs.get("current_user")
    if current_user is None:
        raise AppError(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            code="policy_user_missing",
            message="current_user is required for policy checks",
        )
    check_policy(current_user, action)


def policy(action: str) -> Callable:
    def decorator(func: Callable) -> Callable:
        if iscoroutinefunction(func):
            @wraps(func)
            async def async_wrapper(*args, **kwargs):
                _check_policy_from_kwargs(action, kwargs)
                return await func(*args, **kwargs)

            return async_wrapper

        @wraps(func)
        def wrapper(*args, **kwargs):
            _check_policy_from_kwargs(action, kwargs)
            return func(*args, **kwargs)

        return wrapper

    return decorator
