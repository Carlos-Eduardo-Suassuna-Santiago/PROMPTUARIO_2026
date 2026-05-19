"""
PROMPTUARIO API Gateway
-----------------------
• JWT validation (RS256/HS256) on all routes except /auth/login and /auth/refresh
• Rate limiting via Redis (sliding window)
• Request routing to downstream microservices via httpx
• Injects X-User-Id and X-User-Role headers for downstream trust
• Health aggregation endpoint
"""
from __future__ import annotations

import logging
import sys
import time
from typing import Any

import httpx
import redis.asyncio as aioredis
from fastapi import FastAPI, HTTPException, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic_settings import BaseSettings, SettingsConfigDict

from shared.utils.security import decode_token

# ─── Settings ────────────────────────────────────────────────────────────────

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    SERVICE_NAME: str = "gateway"
    LOG_LEVEL: str = "INFO"

    IAM_SERVICE_URL: str = "http://localhost:8001"
    PATIENT_SERVICE_URL: str = "http://localhost:8002"
    CLINICAL_SERVICE_URL: str = "http://localhost:8003"
    AI_SERVICE_URL: str = "http://localhost:8004"
    REPORTING_SERVICE_URL: str = "http://localhost:8005"

    JWT_SECRET_KEY: str = "change-me-in-production"
    JWT_ALGORITHM: str = "HS256"

    REDIS_URL: str = "redis://localhost:6379/0"

    # Rate limiting
    RATE_LIMIT_ANON_PER_MINUTE: int = 30
    RATE_LIMIT_AUTH_PER_MINUTE: int = 300


settings = Settings()

logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)

# ─── Route table ─────────────────────────────────────────────────────────────
# Maps path prefix → (service_url, requires_auth)

ROUTE_TABLE: list[tuple[str, str, bool]] = [
    # Auth routes — public
    ("/api/v1/auth/login",   settings.IAM_SERVICE_URL,       False),
    ("/api/v1/auth/refresh", settings.IAM_SERVICE_URL,       False),
    # All other routes — require JWT
    ("/api/v1/auth",         settings.IAM_SERVICE_URL,       True),
    ("/api/v1/users",        settings.IAM_SERVICE_URL,       True),
    ("/api/v1/patients",     settings.PATIENT_SERVICE_URL,   True),
    ("/api/v1/appointments", settings.CLINICAL_SERVICE_URL,  True),
    ("/api/v1/schedules",    settings.CLINICAL_SERVICE_URL,  True),
    ("/api/v1/records",      settings.CLINICAL_SERVICE_URL,  True),
    ("/api/v1/ai",           settings.AI_SERVICE_URL,        True),
    ("/api/v1/reports",      settings.REPORTING_SERVICE_URL, True),
]

# ─── App ─────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="PROMPTUARIO — API Gateway",
    description="Single entry point: JWT auth, rate limiting, service routing",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup():
    app.state.redis = await aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    app.state.http_client = httpx.AsyncClient(timeout=30.0)
    logger.info("API Gateway started ✅")


@app.on_event("shutdown")
async def shutdown():
    await app.state.redis.aclose()
    await app.state.http_client.aclose()


# ─── Health ───────────────────────────────────────────────────────────────────

@app.get("/healthz", tags=["Health"])
async def gateway_health():
    return {"status": "ok", "service": "gateway"}


@app.get("/healthz/services", tags=["Health"])
async def services_health(request: Request):
    """Aggregate health check across all downstream services."""
    services = {
        "iam": settings.IAM_SERVICE_URL,
        "patient": settings.PATIENT_SERVICE_URL,
        "clinical": settings.CLINICAL_SERVICE_URL,
        "ai": settings.AI_SERVICE_URL,
        "reporting": settings.REPORTING_SERVICE_URL,
    }
    results = {}
    client: httpx.AsyncClient = request.app.state.http_client
    for name, url in services.items():
        try:
            resp = await client.get(f"{url}/healthz", timeout=3.0)
            results[name] = "ok" if resp.status_code == 200 else "degraded"
        except Exception:
            results[name] = "unreachable"

    overall = "ok" if all(v == "ok" for v in results.values()) else "degraded"
    return {"status": overall, "services": results}


# ─── Middleware: rate limiting ─────────────────────────────────────────────────

async def _check_rate_limit(request: Request, user_id: str | None) -> None:
    redis: aioredis.Redis = request.app.state.redis
    window = 60  # seconds
    now = int(time.time())
    bucket = now // window

    if user_id:
        key = f"rl:auth:{user_id}:{bucket}"
        limit = settings.RATE_LIMIT_AUTH_PER_MINUTE
    else:
        ip = request.client.host if request.client else "unknown"
        key = f"rl:anon:{ip}:{bucket}"
        limit = settings.RATE_LIMIT_ANON_PER_MINUTE

    count = await redis.incr(key)
    if count == 1:
        await redis.expire(key, window * 2)

    if count > limit:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Taxa de requisições excedida. Tente novamente em breve.",
            headers={"Retry-After": str(window - (now % window))},
        )


# ─── Token blacklist check ────────────────────────────────────────────────────

async def _is_blacklisted(request: Request, token: str) -> bool:
    redis: aioredis.Redis = request.app.state.redis
    return bool(await redis.exists(f"blacklist:{token}"))


# ─── Main proxy handler ───────────────────────────────────────────────────────

@app.api_route(
    "/{path:path}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    include_in_schema=False,
)
async def proxy(request: Request, path: str):
    full_path = f"/{path}"

    # Match route
    target_base: str | None = None
    requires_auth: bool = True

    for prefix, service_url, auth in ROUTE_TABLE:
        if full_path.startswith(prefix):
            target_base = service_url
            requires_auth = auth
            break

    if target_base is None:
        raise HTTPException(status_code=404, detail="Rota não encontrada")

    # ── JWT validation ──────────────────────────────────────────
    user_id: str | None = None
    user_role: str | None = None
    user_email: str | None = None

    auth_header = request.headers.get("Authorization", "")
    raw_token: str | None = None

    if auth_header.startswith("Bearer "):
        raw_token = auth_header[7:]
        # Blacklist check
        if await _is_blacklisted(request, raw_token):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token revogado",
            )
        try:
            payload = decode_token(raw_token, settings.JWT_SECRET_KEY, settings.JWT_ALGORITHM)
            user_id = payload.sub
            user_role = payload.role
            user_email = payload.email
        except ValueError:
            if requires_auth:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Token inválido ou expirado",
                    headers={"WWW-Authenticate": "Bearer"},
                )

    if requires_auth and not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Autenticação necessária",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # ── Rate limiting ───────────────────────────────────────────
    await _check_rate_limit(request, user_id)

    # ── Forward request ─────────────────────────────────────────
    target_url = f"{target_base}{full_path}"
    if request.url.query:
        target_url = f"{target_url}?{request.url.query}"

    # Build forwarded headers
    forward_headers = dict(request.headers)
    forward_headers.pop("host", None)  # remove original host

    if user_id:
        forward_headers["X-User-Id"] = user_id
        forward_headers["X-User-Role"] = user_role or ""
        forward_headers["X-User-Email"] = user_email or ""

    forward_headers["X-Forwarded-For"] = request.client.host if request.client else "unknown"
    forward_headers["X-Gateway"] = "promptuario-gateway/1.0"

    body = await request.body()

    client: httpx.AsyncClient = request.app.state.http_client

    try:
        resp = await client.request(
            method=request.method,
            url=target_url,
            headers=forward_headers,
            content=body,
        )
    except httpx.ConnectError:
        logger.error("Service unreachable: %s", target_url)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Serviço temporariamente indisponível",
        )
    except httpx.TimeoutException:
        logger.error("Service timeout: %s", target_url)
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Timeout ao processar requisição",
        )

    # Strip hop-by-hop headers
    excluded = {
        "transfer-encoding", "connection", "keep-alive",
        "upgrade", "proxy-authenticate", "proxy-authorization",
    }
    response_headers = {
        k: v for k, v in resp.headers.items() if k.lower() not in excluded
    }

    logger.info(
        "%s %s → %s [%d] user=%s",
        request.method, full_path, target_base, resp.status_code, user_id or "anon",
    )

    return Response(
        content=resp.content,
        status_code=resp.status_code,
        headers=response_headers,
        media_type=resp.headers.get("content-type"),
    )
