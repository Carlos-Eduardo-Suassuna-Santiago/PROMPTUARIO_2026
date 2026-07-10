from __future__ import annotations
from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import RedirectResponse
from app.config import settings
from app.domain.services.oauth_service import OAuthService
from shared.middleware.auth import make_auth_dependency

get_current_user, require_roles = make_auth_dependency(
    settings.JWT_SECRET_KEY, settings.JWT_ALGORITHM
)

oauth_router = APIRouter(prefix="/auth/oauth", tags=["OAuth"])


def _get_services(request: Request):
    return request.app.state.session_factory, request.app.state.publisher, request.app.state.redis


@oauth_router.get("/google", summary="Iniciar login com Google")
async def google_login(request: Request):
    sf, pub, redis = _get_services(request)
    async with sf() as session:
        svc = OAuthService(session, pub, redis)
        url = await svc.get_google_auth_url()
    return RedirectResponse(url=url, status_code=302)


@oauth_router.get("/google/callback", summary="Callback Google OAuth")
async def google_callback(
    request: Request,
    code: str = Query(...),
    state: str = Query(...),
):
    sf, pub, redis = _get_services(request)
    async with sf() as session:
        svc = OAuthService(session, pub, redis)
        tokens = await svc.handle_google_callback(code, state)

    frontend_url = settings.FRONTEND_CALLBACK_URL
    redirect = (
        f"{frontend_url}"
        f"?access_token={tokens['access_token']}"
        f"&refresh_token={tokens['refresh_token']}"
    )
    return RedirectResponse(url=redirect, status_code=302)


@oauth_router.get("/accounts", summary="Listar contas OAuth vinculadas")
async def list_oauth_accounts(request: Request, user=Depends(get_current_user)):
    sf, pub, redis = _get_services(request)
    async with sf() as session:
        svc = OAuthService(session, pub, redis)
        return {"accounts": await svc.list_accounts(user.sub)}