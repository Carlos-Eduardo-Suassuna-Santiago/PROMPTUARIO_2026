"""
Tests for LLM client with circuit breaker, cache, retry, and response validation.
"""
from __future__ import annotations

import json
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.infrastructure.llm_client import (
    LLMClient,
    CircuitOpenError,
    LLMResponseValidationError,
)


@pytest.fixture
def llm_client():
    return LLMClient(
        api_key="test-key",
        model="gpt-4o-mini",
        max_tokens=1000,
        temperature=0.1,
        redis_client=None,
        failure_threshold=3,
        recovery_timeout=2,
        cache_ttl=3600,
        request_timeout=30,
    )


@pytest.fixture
def llm_client_no_key():
    return LLMClient(
        api_key="",
        model="gpt-4o-mini",
        max_tokens=1000,
        redis_client=None,
    )


class TestCircuitBreaker:
    async def test_initial_state_closed(self, llm_client):
        """Should start in CLOSED state."""
        assert llm_client.state == "CLOSED"
        assert llm_client.failure_count == 0

    async def test_opens_after_threshold_failures(self, llm_client):
        """Should transition to OPEN after threshold failures."""
        for i in range(llm_client._failure_threshold):
            llm_client._on_failure(Exception(f"Error {i}"))

        assert llm_client.state == "OPEN"
        assert llm_client.failure_count == llm_client._failure_threshold

    async def test_rejects_when_open(self, llm_client):
        """Should raise CircuitOpenError when circuit is OPEN."""
        llm_client._state = "OPEN"
        llm_client._last_failure_t = time.monotonic()
        llm_client._failure_count = 5

        with pytest.raises(CircuitOpenError) as exc:
            await llm_client.call("prompt", "system")
        assert "indisponível" in str(exc.value).lower()

    async def test_half_open_after_recovery_timeout(self, llm_client):
        """Should transition to HALF_OPEN after recovery timeout."""
        llm_client._state = "OPEN"
        llm_client._last_failure_t = time.monotonic() - llm_client._recovery_timeout - 1
        llm_client._failure_count = 5

        # _check_circuit should transition to HALF_OPEN
        llm_client._check_circuit()
        assert llm_client.state == "HALF_OPEN"

    async def test_closes_on_success(self, llm_client):
        """Should transition to CLOSED on successful call."""
        llm_client._state = "HALF_OPEN"
        llm_client._failure_count = 3

        llm_client._on_success()
        assert llm_client.state == "CLOSED"
        assert llm_client.failure_count == 0


class TestCache:
    async def test_cache_hit(self):
        """Should return cached result when available."""
        mock_redis = AsyncMock()
        cached_result = {"risk_level": "LOW", "interactions_found": []}
        mock_redis.get.return_value = json.dumps(cached_result)

        client = LLMClient(
            api_key="test-key",
            model="gpt-4o-mini",
            max_tokens=1000,
            redis_client=mock_redis,
        )

        result = await client.call("test prompt", "system prompt")
        assert result == cached_result
        assert client._total_cache_hits == 1

    async def test_cache_miss_calls_api(self, llm_client):
        """Should call API when cache misses."""
        with patch.object(llm_client, "_call_api") as mock_call:
            mock_call.return_value = {"risk_level": "LOW"}
            result = await llm_client.call("prompt", "system")
            assert result == {"risk_level": "LOW"}
            mock_call.assert_called_once()

    async def test_cache_skipped_when_disabled(self):
        """Should skip cache when CACHE_ENABLED is False."""
        with patch("app.config.settings.CACHE_ENABLED", False):
            mock_redis = AsyncMock()
            client = LLMClient(
                api_key="test-key",
                model="gpt-4o-mini",
                max_tokens=1000,
                redis_client=mock_redis,
            )

            with patch.object(client, "_call_api") as mock_call:
                mock_call.return_value = {"risk_level": "LOW"}
                result = await client.call("prompt", "system")
                mock_redis.get.assert_not_called()


class TestResponseValidation:
    async def test_validates_response_when_schema_provided(self):
        """Should validate response against schema when schema_name is provided."""
        mock_redis = AsyncMock()
        mock_redis.get.return_value = None  # cache miss

        client = LLMClient(
            api_key="test-key",
            model="gpt-4o-mini",
            max_tokens=1000,
            redis_client=mock_redis,
        )

        valid_response = {
            "risk_level": "HIGH",
            "interactions_found": [
                {"drugs": ["A", "B"], "severity": "HIGH", "description": "Test interaction"}
            ],
            "allergy_conflicts": [],
            "recommendations": ["Test"],
            "disclaimer": "Test",
        }

        with patch.object(client, "_call_api") as mock_call:
            mock_call.return_value = valid_response
            result = await client.call("prompt", "system", schema_name="drug_interaction")
            assert result["risk_level"] == "HIGH"
            assert len(result["interactions_found"]) == 1

    async def test_rejects_invalid_response(self):
        """Should raise LLMResponseValidationError for invalid response."""
        mock_redis = AsyncMock()
        mock_redis.get.return_value = None

        client = LLMClient(
            api_key="test-key",
            model="gpt-4o-mini",
            max_tokens=1000,
            redis_client=mock_redis,
        )

        invalid_response = {"risk_level": "INVALID"}

        with patch.object(client, "_call_api") as mock_call:
            mock_call.return_value = invalid_response
            with pytest.raises(LLMResponseValidationError) as exc:
                await client.call("prompt", "system", schema_name="drug_interaction")
            assert "validation failed" in str(exc.value).lower()


class TestNoApiKey:
    async def test_returns_none_without_key(self, llm_client_no_key):
        """Should return None when no API key is configured."""
        result = await llm_client_no_key.call("prompt", "system")
        assert result is None

    async def test_metrics_tracked(self, llm_client):
        """Should track call metrics."""
        with patch.object(llm_client, "_call_api") as mock_call:
            mock_call.return_value = {"risk_level": "LOW"}
            await llm_client.call("prompt", "system")
            metrics = llm_client.metrics
            assert metrics["total_calls"] == 1
            assert metrics["model"] == "gpt-4o-mini"

    async def test_no_cache_hits_without_redis(self, llm_client):
        """Should not cache when no redis client is available."""
        with patch.object(llm_client, "_call_api") as mock_call:
            mock_call.return_value = {"risk_level": "LOW"}
            result = await llm_client.call("prompt", "system")
            assert llm_client._total_cache_hits == 0