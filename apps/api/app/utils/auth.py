"""
Lightweight API authentication and role authorization for ReviveAI.
Provides ADMIN, OPERATIONS, and VIEWER roles.
"""

import os
from typing import Optional
from fastapi import Header, HTTPException, status, Security
from fastapi.security import APIKeyHeader

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

# API Keys mapped to user roles
API_KEYS = {
    os.getenv("ADMIN_API_KEY", "revive_admin_secret_key"): "ADMIN",
    os.getenv("OPERATIONS_API_KEY", "revive_ops_secret_key"): "OPERATIONS",
    os.getenv("VIEWER_API_KEY", "revive_viewer_secret_key"): "VIEWER",
}


def get_current_user_role(api_key: Optional[str] = Security(api_key_header)) -> str:
    """Validate API key and return role. Defaults to VIEWER for local demo mode if key omitted."""
    if not api_key:
        # Permissive local demo default: VIEWER role
        return "VIEWER"

    role = API_KEYS.get(api_key)
    if not role:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired API Key",
        )
    return role


def require_role(min_role: str):
    """Dependency that enforces role hierarchies: ADMIN > OPERATIONS > VIEWER."""
    role_weights = {"VIEWER": 1, "OPERATIONS": 2, "ADMIN": 3}

    def role_checker(current_role: str = Security(get_current_user_role)):
        if role_weights.get(current_role, 0) < role_weights.get(min_role, 0):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Operation requires '{min_role}' authorization; current role is '{current_role}'",
            )
        return current_role

    return role_checker
