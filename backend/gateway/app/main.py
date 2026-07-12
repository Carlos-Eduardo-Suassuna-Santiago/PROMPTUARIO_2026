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

import asyncio
import hashlib
import json
import logging
import time
from dataclasses import dataclass
from typing import Any

import httpx
import redis.asyncio as aioredis
from fastapi import FastAPI, HTTPException, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.gzip import GZipMiddleware
from pydantic_settings import BaseSettings, SettingsConfigDict

from shared.observability import register_resilience_metrics, setup_observability
from shared.utils.security import decode_token


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
    RATE_LIMIT_API_KEY_PER_MINUTE: int = 120

    # Resilience defaults
    CACHE_TTL_SECONDS: int = 60
    CIRCUIT_BREAKER_FAILURE_THRESHOLD: int = 3
    CIRCUIT_BREAKER_RESET_TIMEOUT_SECONDS: int = 30


settings = Settings()

logger = logging.getLogger(__name__)


@dataclass
class CircuitBreakerState:
    state: str = "closed"
    failure_count: int = 0
    opened_at: float | None = None


class CircuitOpenError(RuntimeError):
    pass


# ─── Route table ─────────────────────────────────────────────────────────────
# Maps path prefix → (service_url, requires_auth)

ROUTE_TABLE: list[tuple[str, str, bool]] = [
    # Observability — public (gateway /metrics served locally via setup_observability)
    ("/metrics", settings.IAM_SERVICE_URL, False),
    # Auth routes — public
    ("/api/v1/auth/login",   settings.IAM_SERVICE_URL,       False),
    ("/api/v1/auth/refresh", settings.IAM_SERVICE_URL,       False),
    ("/api/v1/auth/forgot-password", settings.IAM_SERVICE_URL, False),
    ("/api/v1/auth/reset-password",  settings.IAM_SERVICE_URL, False),
    ("/api/v1/auth/register-patient", settings.IAM_SERVICE_URL, False),
    # OAuth routes — public (callbacks are handled by the provider redirect)
    ("/api/v1/auth/oauth", settings.IAM_SERVICE_URL, False),
    # All other routes — require JWT
    ("/api/v1/auth", settings.IAM_SERVICE_URL, True),
    ("/api/v1/users", settings.IAM_SERVICE_URL, True),
    ("/api/v1/patients", settings.PATIENT_SERVICE_URL, True),
    ("/api/v1/appointments", settings.CLINICAL_SERVICE_URL, True),
    ("/api/v1/schedules", settings.CLINICAL_SERVICE_URL, True),
    ("/api/v1/records", settings.CLINICAL_SERVICE_URL, True),
    ("/api/v1/ai", settings.AI_SERVICE_URL, True),
    ("/api/v1/reports", settings.REPORTING_SERVICE_URL, True),
    ("/api/v1/admin", settings.REPORTING_SERVICE_URL, True),
    ("/api/v1/audit", settings.REPORTING_SERVICE_URL, True),
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
app.add_middleware(GZipMiddleware, minimum_size=1000)

setup_observability(app, settings.SERVICE_NAME, settings.LOG_LEVEL)
app.state.resilience_metrics = register_resilience_metrics(app, settings.SERVICE_NAME)


@app.on_event("startup")
async def startup():
    app.state.redis = await aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    app.state.http_client = httpx.AsyncClient(timeout=30.0)
    app.state.circuit_breakers: dict[str, CircuitBreakerState] = {}
    app.state.circuit_breaker_lock = asyncio.Lock()
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

async def _check_rate_limit(request: Request, user_id: str | None, api_key: str | None = None) -> None:
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

    if api_key:
        key = f"rl:apikey:{hashlib.sha256(api_key.encode('utf-8')).hexdigest()}:{bucket}"
        count = await redis.incr(key)
        if count == 1:
            await redis.expire(key, window * 2)
        if count > settings.RATE_LIMIT_API_KEY_PER_MINUTE:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="API key excedeu a taxa permitida.",
                headers={"Retry-After": str(window - (now % window))},
            )


# ─── Token blacklist check ────────────────────────────────────────────────────

async def _is_blacklisted(request: Request, token: str) -> bool:
    redis: aioredis.Redis = request.app.state.redis
    return bool(await redis.exists(f"blacklist:{token}"))


# ─── Cache helpers ────────────────────────────────────────────────────────────


def _is_cacheable_path(full_path: str) -> bool:
    if full_path.startswith(("/healthz", "/metrics", "/docs", "/redoc", "/openapi.json")):
        return False
    if full_path.startswith(("/api/v1/auth", "/api/v1/users", "/api/v1/admin", "/api/v1/audit")):
        return False
    return full_path.startswith(("/api/v1/patients", "/api/v1/appointments", "/api/v1/schedules", "/api/v1/records", "/api/v1/reports"))


def _is_cacheable_content_type(content_type: str | None) -> bool:
    if not content_type:
        return True
    lowered = content_type.lower()
    return any(token in lowered for token in ("json", "text/", "xml", "javascript", "application/problem+json"))


async def _get_cached_response(request: Request, full_path: str, query_string: str, scope: str) -> Response | None:
    redis: aioredis.Redis = request.app.state.redis
    cache_key = f"cache:{scope}:{hashlib.sha256(f'{full_path}|{query_string}'.encode('utf-8')).hexdigest()}"
    raw = await redis.get(cache_key)
    if not raw:
        request.app.state.resilience_metrics["cache_misses_total"].labels(service=settings.SERVICE_NAME, route=full_path).inc()
        return None

    request.app.state.resilience_metrics["cache_hits_total"].labels(service=settings.SERVICE_NAME, route=full_path).inc()
    payload = json.loads(raw)
    return Response(
        content=payload["body"],
        status_code=payload["status_code"],
        headers=payload["headers"],
        media_type=payload["media_type"],
    )


async def _set_cached_response(request: Request, full_path: str, query_string: str, scope: str, response: Response) -> None:
    redis: aioredis.Redis = request.app.state.redis
    if response.status_code >= 400 or response.media_type is None:
        return
    if not _is_cacheable_content_type(response.media_type):
        return
    payload = {
        "body": response.body.decode("utf-8", errors="ignore"),
        "status_code": response.status_code,
        "headers": {k: v for k, v in response.headers.items() if k.lower() not in {"set-cookie", "authorization"}},
        "media_type": response.media_type,
    }
    cache_key = f"cache:{scope}:{hashlib.sha256(f'{full_path}|{query_string}'.encode('utf-8')).hexdigest()}"
    await redis.setex(cache_key, settings.CACHE_TTL_SECONDS, json.dumps(payload))


# ─── Circuit breaker helpers ─────────────────────────────────────────────────

async def _get_circuit_breaker(request: Request, service_name: str) -> CircuitBreakerState:
    breakers: dict[str, CircuitBreakerState] = request.app.state.circuit_breakers
    breaker = breakers.get(service_name)
    if breaker is None:
        breaker = CircuitBreakerState()
        breakers[service_name] = breaker
    return breaker


async def _forward_to_service(request: Request, target_url: str, forward_headers: dict[str, str], body: bytes, service_name: str) -> Response:
    client: httpx.AsyncClient = request.app.state.http_client
    breaker = await _get_circuit_breaker(request, service_name)
    metrics = request.app.state.resilience_metrics

    async with request.app.state.circuit_breaker_lock:
        if breaker.state == "open" and breaker.opened_at is not None:
            if time.time() - breaker.opened_at < settings.CIRCUIT_BREAKER_RESET_TIMEOUT_SECONDS:
                metrics["circuit_state"].labels(service=settings.SERVICE_NAME, target=service_name).set(1)
                raise CircuitOpenError("Circuito aberto para o serviço downstream")
            breaker.state = "half-open"
            breaker.failure_count = 0
            metrics["circuit_state"].labels(service=settings.SERVICE_NAME, target=service_name).set(0.5)

    try:
        resp = await client.request(method=request.method, url=target_url, headers=forward_headers, content=body)
    except httpx.RequestError as exc:
        async with request.app.state.circuit_breaker_lock:
            breaker.failure_count += 1
            if breaker.failure_count >= settings.CIRCUIT_BREAKER_FAILURE_THRESHOLD:
                breaker.state = "open"
                breaker.opened_at = time.time()
                metrics["circuit_state"].labels(service=settings.SERVICE_NAME, target=service_name).set(1)
                metrics["circuit_open_total"].labels(service=settings.SERVICE_NAME, target=service_name).inc()
                logger.warning("Circuit breaker abriu para %s após falhas: %s", service_name, exc)
            else:
                logger.warning("Falha transitória em %s: %s", service_name, exc)
        raise

    async with request.app.state.circuit_breaker_lock:
        breaker.state = "closed"
        breaker.failure_count = 0
        breaker.opened_at = None
        metrics["circuit_state"].labels(service=settings.SERVICE_NAME, target=service_name).set(0)

    return Response(
        content=resp.content,
        status_code=resp.status_code,
        headers={k: v for k, v in resp.headers.items() if k.lower() not in {"transfer-encoding", "connection", "keep-alive", "upgrade", "proxy-authenticate", "proxy-authorization"}},
        media_type=resp.headers.get("content-type"),
    )


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
    api_key = request.headers.get("X-Api-Key")
    await _check_rate_limit(request, user_id, api_key)

    # ── Cache lookup ───────────────────────────────────────────
    scope = f"user:{user_id}" if user_id else f"api:{hashlib.sha256(api_key.encode('utf-8')).hexdigest()}" if api_key else "anon"
    if request.method == "GET" and _is_cacheable_path(full_path):
        cached_response = await _get_cached_response(request, full_path, request.url.query, scope)
        if cached_response is not None:
            logger.info("cache hit %s %s", request.method, full_path)
            return cached_response

    # ── Forward request ─────────────────────────────────────────
    target_url = f"{target_base}{full_path}"
    if request.url.query:
        target_url = f"{target_url}?{request.url.query}"

    forward_headers = dict(request.headers)
    forward_headers.pop("host", None)

    if user_id:
        forward_headers["X-User-Id"] = user_id
        forward_headers["X-User-Role"] = user_role or ""
        forward_headers["X-User-Email"] = user_email or ""

    forward_headers["X-Forwarded-For"] = request.client.host if request.client else "unknown"
    forward_headers["X-Gateway"] = "promptuario-gateway/1.0"

    body = await request.body()

    try:
        response = await _forward_to_service(
            request=request,
            target_url=target_url,
            forward_headers=forward_headers,
            body=body,
            service_name=target_base,
        )
    except CircuitOpenError:
        logger.warning("Circuit breaker open for %s", target_url)
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"detail": "Serviço temporariamente indisponível"},
            headers={"X-Circuit-Breaker": "open"},
        )
    except httpx.RequestError as exc:
        logger.error("Service unreachable: %s (%s)", target_url, exc)
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"detail": "Serviço temporariamente indisponível"},
            headers={"X-Circuit-Breaker": "open"},
        )

    if request.method == "GET" and _is_cacheable_path(full_path):
        await _set_cached_response(request, full_path, request.url.query, scope, response)

    logger.info(
        "%s %s → %s [%d] user=%s",
        request.method,
        full_path,
        target_base,
        response.status_code,
        user_id or "anon",
    )

    return response
