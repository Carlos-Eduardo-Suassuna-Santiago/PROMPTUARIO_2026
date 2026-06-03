from __future__ import annotations

import json
import os
import sys
import time
from urllib import error, request


SERVICES = {
    "gateway": "http://localhost:8000",
    "iam-service": "http://localhost:8001",
    "patient-service": "http://localhost:8002",
    "clinical-service": "http://localhost:8003",
    "ai-service": "http://localhost:8004",
    "reporting-service": "http://localhost:8005",
}


def _get(url: str, headers: dict[str, str] | None = None) -> tuple[int, str, dict[str, str]]:
    req = request.Request(url, method="GET", headers=headers or {})
    try:
        with request.urlopen(req, timeout=10) as resp:
            body = resp.read().decode("utf-8")
            return resp.status, body, dict(resp.headers.items())
    except error.HTTPError as exc:
        body = exc.read().decode("utf-8")
        return exc.code, body, dict(exc.headers.items())


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _check_metrics(base_url: str, service: str) -> None:
    status, body, _ = _get(f"{base_url}/metrics")
    _assert(status == 200, f"{service} /metrics expected 200, got {status}")
    _assert("http_requests_total" in body, f"{service} missing http_requests_total")
    _assert("http_request_duration_seconds_bucket" in body, f"{service} missing duration histogram")


def _check_trace_exists(service_name: str) -> None:
    jaeger_url = os.getenv(
        "JAEGER_QUERY_URL",
        f"http://localhost:16686/api/traces?service={service_name}&limit=5&lookback=1h",
    )

    for _ in range(5):
        status, body, _ = _get(jaeger_url)
        if status != 200:
            time.sleep(1)
            continue
        parsed = json.loads(body)
        if parsed.get("data"):
            return
        time.sleep(1)

    raise AssertionError(f"No traces found in Jaeger for service={service_name}")


def main() -> int:
    request_id = f"smoke-{int(time.time())}"
    traceparent = "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01"

    status, _, headers = _get(
        f"{SERVICES['gateway']}/healthz/services",
        headers={"X-Request-Id": request_id, "traceparent": traceparent},
    )
    _assert(status == 200, f"gateway health expected 200, got {status}")
    _assert(headers.get("X-Request-Id") == request_id, "gateway did not propagate X-Request-Id")

    for name, base_url in SERVICES.items():
        _check_metrics(base_url, name)

    _check_trace_exists("gateway")

    print("[OK] observability smoke passed")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"[FAIL] {exc}")
        raise SystemExit(1)
