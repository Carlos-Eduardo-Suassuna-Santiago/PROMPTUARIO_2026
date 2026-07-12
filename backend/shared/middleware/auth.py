"""
FastAPI dependency for JWT authentication.
All services use this to protect endpoints.
"""
from __future__ import annotations

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from shared.utils.security import TokenPayload, decode_token

bearer = HTTPBearer()


def make_auth_dependency(secret: str, algorithm: str):
    """
    Factory that returns a FastAPI dependency pre-configured
    with the service's JWT settings.
    """

    async def get_current_user(
        credentials: HTTPAuthorizationCredentials = Depends(bearer),
    ) -> TokenPayload:
        token = credentials.credentials
        try:
            payload = decode_token(token, secret, algorithm)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token inválido ou expirado",
                headers={"WWW-Authenticate": "Bearer"},
            )
        if payload.type != "access":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Tipo de token incorreto",
            )
        # Ensure access tokens have role and email
        if not payload.role or not payload.email:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token inválido: faltam campos obrigatórios",
            )
        try:
            from shared.audit import audit_context_var
            curr = dict(audit_context_var.get())
            curr["user_id"] = payload.sub
            curr["user_role"] = payload.role
            curr["user_email"] = payload.email
            audit_context_var.set(curr)
        except Exception:
            pass
        return payload

    def require_roles(*roles: str):
        async def _check(user: TokenPayload = Depends(get_current_user)) -> TokenPayload:
            if user.role not in roles:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Acesso negado. Requer: {', '.join(roles)}",
                )
            return user
        return _check

    return get_current_user, require_roles


ROLES = {
    "ADMIN": "ADMIN",
    "DOCTOR": "DOCTOR",
    "ATTENDANT": "ATTENDANT",
    "PATIENT": "PATIENT",
}
