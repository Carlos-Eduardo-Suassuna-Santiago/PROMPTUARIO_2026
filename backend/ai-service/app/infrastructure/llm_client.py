"""
Cliente LLM com retry, circuit breaker, cache Redis, validação de resposta e timeout.

Padrão circuit breaker:
  CLOSED   → operação normal
  OPEN     → falhou N vezes consecutivas, rejeita chamadas por TIMEOUT segundos
  HALF_OPEN → após TIMEOUT, tenta uma chamada de teste
"""
from __future__ import annotations

import hashlib
import json
import logging
import time
from datetime import datetime, timezone

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
    before_sleep_log,
)

from app.config import settings
from app.domain.schemas import validate_llm_response

logger = logging.getLogger(__name__)


class CircuitOpenError(RuntimeError):
    """Levantada quando o circuit breaker está OPEN."""
    pass


class LLMResponseValidationError(ValueError):
    """Levantada quando a resposta do LLM não passa na validação do schema."""
    pass


class LLMTimeoutError(TimeoutError):
    """Levantada quando a chamada LLM excede o timeout configurado."""
    pass


class LLMClient:
    """
    Cliente para OpenAI-compatible APIs com:
      - Retry automático (configurável, backoff exponencial)
      - Circuit breaker (configurável)
      - Cache Redis (TTL configurável)
      - Validação de resposta via Pydantic schemas
      - Timeout controlado
      - Rastreamento de versão do modelo
    """

    def __init__(
        self,
        api_key: str,
        model: str,
        max_tokens: int,
        temperature: float = 0.1,
        redis_client=None,
        failure_threshold: int | None = None,
        recovery_timeout: int | None = None,
        cache_ttl: int | None = None,
        request_timeout: int | None = None,
    ):
        self._api_key = api_key
        self._model = model
        self._max_tokens = max_tokens
        self._temperature = temperature
        self._redis = redis_client
        self._cache_ttl = cache_ttl or settings.LLM_CACHE_TTL_SECONDS

        # Circuit breaker state
        self._failure_threshold = failure_threshold or settings.CIRCUIT_BREAKER_FAILURE_THRESHOLD
        self._recovery_timeout = recovery_timeout or settings.CIRCUIT_BREAKER_RECOVERY_TIMEOUT
        self._state = "CLOSED"
        self._failure_count = 0
        self._last_failure_t = 0.0

        # Metrics
        self._total_calls = 0
        self._total_cache_hits = 0
        self._total_errors = 0
        self._last_call_duration = 0.0
        self._last_call_timestamp: str | None = None

    # ── Public properties ──────────────────────────────────────────────────

    @property
    def state(self) -> str:
        return self._state

    @property
    def failure_count(self) -> int:
        return self._failure_count

    @property
    def model_version(self) -> str:
        return self._model

    @property
    def metrics(self) -> dict:
        return {
            "model": self._model,
            "state": self._state,
            "failure_count": self._failure_count,
            "total_calls": self._total_calls,
            "total_cache_hits": self._total_cache_hits,
            "total_errors": self._total_errors,
            "last_call_duration_seconds": self._last_call_duration,
            "last_call_timestamp": self._last_call_timestamp,
        }

    # ── Circuit Breaker ────────────────────────────────────────────────────

    def _check_circuit(self) -> None:
        if self._state == "OPEN":
            elapsed = time.monotonic() - self._last_failure_t
            if elapsed >= self._recovery_timeout:
                self._state = "HALF_OPEN"
                logger.info("Circuit breaker → HALF_OPEN (tentando recuperar)")
            else:
                remaining = self._recovery_timeout - elapsed
                raise CircuitOpenError(
                    f"LLM indisponível (circuit OPEN após {self._failure_count} falhas). "
                    f"Tente novamente em {remaining:.0f}s."
                )

    def _on_success(self) -> None:
        if self._state in ("HALF_OPEN", "OPEN"):
            logger.info("Circuit breaker → CLOSED (recuperado)")
        self._failure_count = 0
        self._state = "CLOSED"

    def _on_failure(self, exc: Exception) -> None:
        self._failure_count += 1
        self._last_failure_t = time.monotonic()
        if self._failure_count >= self._failure_threshold:
            if self._state != "OPEN":
                logger.error(
                    "Circuit breaker → OPEN após %d falhas consecutivas",
                    self._failure_count,
                )
            self._state = "OPEN"

    # ── Cache Redis ────────────────────────────────────────────────────────

    def _cache_key(self, prompt: str, system_prompt: str) -> str:
        combined = f"{system_prompt}||{prompt}"
        return f"llm_cache:{hashlib.sha256(combined.encode()).hexdigest()[:32]}"

    async def _get_cached(self, prompt: str, system_prompt: str) -> dict | None:
        if not self._redis or not settings.CACHE_ENABLED:
            return None
        try:
            cached = await self._redis.get(self._cache_key(prompt, system_prompt))
            if cached:
                self._total_cache_hits += 1
                logger.debug("LLM cache hit")
                return json.loads(cached)
        except Exception as exc:
            logger.warning("Erro ao ler cache LLM: %s", exc)
        return None

    async def _set_cached(self, prompt: str, system_prompt: str, result: dict) -> None:
        if not self._redis or not settings.CACHE_ENABLED:
            return
        try:
            await self._redis.setex(
                self._cache_key(prompt, system_prompt),
                self._cache_ttl,
                json.dumps(result),
            )
        except Exception as exc:
            logger.warning("Erro ao salvar cache LLM: %s", exc)

    # ── Chamada à API com retry ────────────────────────────────────────────

    async def _call_api(self, prompt: str, system_prompt: str) -> dict:
        """Faz a chamada HTTP com retry automático via tenacity."""

        @retry(
            stop=stop_after_attempt(settings.LLM_RETRY_MAX_ATTEMPTS),
            wait=wait_exponential(
                multiplier=1,
                min=settings.LLM_RETRY_MIN_WAIT,
                max=settings.LLM_RETRY_MAX_WAIT,
            ),
            retry=retry_if_exception_type(
                (httpx.HTTPStatusError, httpx.TimeoutException, json.JSONDecodeError)
            ),
            before_sleep=before_sleep_log(logger, logging.WARNING),
            reraise=True,
        )
        async def _inner() -> dict:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(
                    connect=5.0,
                    read=float(settings.LLM_TIMEOUT_SECONDS),
                    write=10.0,
                    pool=5.0,
                )
            ) as client:
                response = await client.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self._api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": self._model,
                        "max_tokens": self._max_tokens,
                        "temperature": self._temperature,
                        "response_format": {"type": "json_object"},
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": prompt},
                        ],
                    },
                )
                response.raise_for_status()
                data = response.json()
                content = data["choices"][0]["message"]["content"]
                # Track token usage if available
                usage = data.get("usage", {})
                self._last_prompt_tokens = usage.get("prompt_tokens", 0)
                self._last_completion_tokens = usage.get("completion_tokens", 0)
                return json.loads(content)

        return await _inner()

    # ── Interface pública ──────────────────────────────────────────────────

    async def call(
        self,
        prompt: str,
        system_prompt: str,
        schema_name: str | None = None,
    ) -> dict | None:
        """
        Executa chamada LLM com circuit breaker, cache, retry e validação.

        Args:
            prompt: O prompt do usuário.
            system_prompt: O prompt de sistema.
            schema_name: Se fornecido, valida a resposta contra o schema.

        Returns:
            dict com o resultado validado.
            None se não há API key configurada (modo mock).

        Raises:
            CircuitOpenError: Se o circuit breaker estiver OPEN.
            LLMResponseValidationError: Se a resposta não passar na validação.
            Exception: Em caso de falha persistente após retries.
        """
        self._total_calls += 1
        self._last_call_timestamp = datetime.now(timezone.utc).isoformat()

        # Sem API key → modo mock
        if not self._api_key:
            return None

        # Verifica circuit breaker
        self._check_circuit()

        # Verifica cache
        cached = await self._get_cached(prompt, system_prompt)
        if cached is not None:
            return cached

        # Chama API
        start_time = time.monotonic()
        try:
            result = await self._call_api(prompt, system_prompt)
            self._last_call_duration = time.monotonic() - start_time

            # Valida resposta contra schema, se solicitado
            if schema_name:
                try:
                    result = validate_llm_response(result, schema_name)
                except ValueError as e:
                    self._total_errors += 1
                    raise LLMResponseValidationError(str(e)) from e

            self._on_success()
            await self._set_cached(prompt, system_prompt, result)
            return result

        except CircuitOpenError:
            raise

        except LLMResponseValidationError:
            raise

        except Exception as exc:
            self._total_errors += 1
            self._last_call_duration = time.monotonic() - start_time
            self._on_failure(exc)
            raise