"""
Cliente LLM com retry, circuit breaker e cache Redis.

Padrão circuit breaker:
  CLOSED → operação normal
  OPEN   → falhou N vezes consecutivas, rejeita chamadas por TIMEOUT segundos
  HALF_OPEN → após TIMEOUT, tenta uma chamada de teste
"""
from __future__ import annotations

import hashlib
import json
import logging
import time

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
    before_sleep_log,
)

logger = logging.getLogger(__name__)


class CircuitOpenError(RuntimeError):
    """Levantada quando o circuit breaker está OPEN."""
    pass


class LLMClient:
    """
    Cliente para OpenAI-compatible APIs com:
      - Retry automático (3 tentativas, backoff exponencial 2s→30s)
      - Circuit breaker (abre após 5 falhas, fecha após 60s)
      - Cache Redis (TTL 1h por prompt hash)
    """

    FAILURE_THRESHOLD = 5   # falhas para abrir o circuito
    RECOVERY_TIMEOUT  = 60  # segundos até tentar HALF_OPEN

    def __init__(self, api_key: str, model: str, max_tokens: int, redis_client=None):
        self._api_key     = api_key
        self._model       = model
        self._max_tokens  = max_tokens
        self._redis       = redis_client

        # Estado do circuit breaker
        self._state          = "CLOSED"   # CLOSED | OPEN | HALF_OPEN
        self._failure_count  = 0
        self._last_failure_t = 0.0

    # ── Circuit Breaker ──────────────────────────────────────────────────

    def _check_circuit(self) -> None:
        if self._state == "OPEN":
            elapsed = time.monotonic() - self._last_failure_t
            if elapsed >= self.RECOVERY_TIMEOUT:
                self._state = "HALF_OPEN"
                logger.info("Circuit breaker → HALF_OPEN (tentando recuperar)")
            else:
                remaining = self.RECOVERY_TIMEOUT - elapsed
                raise CircuitOpenError(
                    f"LLM indisponível (circuit OPEN). Tente novamente em {remaining:.0f}s."
                )

    def _on_success(self) -> None:
        if self._state in ("HALF_OPEN", "OPEN"):
            logger.info("Circuit breaker → CLOSED (recuperado)")
        self._failure_count = 0
        self._state = "CLOSED"

    def _on_failure(self, exc: Exception) -> None:
        self._failure_count += 1
        self._last_failure_t = time.monotonic()
        if self._failure_count >= self.FAILURE_THRESHOLD:
            if self._state != "OPEN":
                logger.error(
                    "Circuit breaker → OPEN após %d falhas consecutivas",
                    self._failure_count,
                )
            self._state = "OPEN"

    # ── Cache Redis ───────────────────────────────────────────────────────

    def _cache_key(self, prompt: str) -> str:
        return f"llm_cache:{hashlib.sha256(prompt.encode()).hexdigest()[:20]}"

    async def _get_cached(self, prompt: str) -> dict | None:
        if not self._redis:
            return None
        try:
            cached = await self._redis.get(self._cache_key(prompt))
            if cached:
                logger.debug("LLM cache hit")
                return json.loads(cached)
        except Exception as exc:
            logger.warning("Erro ao ler cache LLM: %s", exc)
        return None

    async def _set_cached(self, prompt: str, result: dict) -> None:
        if not self._redis:
            return
        try:
            await self._redis.setex(
                self._cache_key(prompt), 3600, json.dumps(result)   # TTL 1h
            )
        except Exception as exc:
            logger.warning("Erro ao salvar cache LLM: %s", exc)

    # ── Chamada à API com retry ───────────────────────────────────────────

    async def _call_api(self, prompt: str, system_prompt: str) -> dict:
        """Faz a chamada HTTP com retry automático via tenacity."""

        @retry(
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=1, min=2, max=30),
            retry=retry_if_exception_type(
                (httpx.HTTPStatusError, httpx.TimeoutException, json.JSONDecodeError)
            ),
            before_sleep=before_sleep_log(logger, logging.WARNING),
            reraise=True,
        )
        async def _inner() -> dict:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(connect=5.0, read=60.0, write=10.0, pool=5.0)
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
                        "response_format": {"type": "json_object"},
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": prompt},
                        ],
                    },
                )
                response.raise_for_status()
                content = response.json()["choices"][0]["message"]["content"]
                return json.loads(content)   # JSONDecodeError → retry

        return await _inner()

    # ── Interface pública ─────────────────────────────────────────────────

    async def call(self, prompt: str, system_prompt: str) -> dict | None:
        """
        Executa chamada LLM com circuit breaker, cache e retry.

        Retorna:
          dict com o resultado da análise
          None se não há API key configurada (modo mock)

        Levanta:
          CircuitOpenError se o circuit breaker estiver OPEN
          Exception em caso de falha persistente após retries
        """
        # Sem API key → modo mock (retorna None para sinalizar ao caller)
        if not self._api_key:
            return None

        # Verifica circuit breaker
        self._check_circuit()

        # Verifica cache
        cached = await self._get_cached(prompt)
        if cached is not None:
            return cached

        # Chama API
        try:
            result = await self._call_api(prompt, system_prompt)
            self._on_success()
            await self._set_cached(prompt, result)
            return result

        except CircuitOpenError:
            raise   # propaga sem contar como nova falha

        except Exception as exc:
            self._on_failure(exc)
            raise

    @property
    def state(self) -> str:
        return self._state

    @property
    def failure_count(self) -> int:
        return self._failure_count