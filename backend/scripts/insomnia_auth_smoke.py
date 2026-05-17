from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib import error, request


def load_env_file(path: Path) -> None:
    if not path.exists():
        return

    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]
        os.environ.setdefault(key, value)


def normalize_token(token: str) -> str:
    value = token.strip()
    if value.lower().startswith("bearer "):
        value = value[7:].strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        value = value[1:-1].strip()
    return value


@dataclass
class Result:
    name: str
    ok: bool
    status: int | None = None
    details: str = ""


def http_json(
    method: str,
    url: str,
    body: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
) -> tuple[int, dict[str, Any] | list[Any] | str]:
    payload = None
    request_headers = {"Accept": "application/json"}
    if headers:
        request_headers.update(headers)
    if body is not None:
        payload = json.dumps(body).encode("utf-8")
        request_headers.setdefault("Content-Type", "application/json")

    req = request.Request(url, data=payload, method=method.upper(), headers=request_headers)
    try:
        with request.urlopen(req, timeout=20) as resp:
            raw = resp.read().decode("utf-8")
            try:
                parsed: dict[str, Any] | list[Any] | str = json.loads(raw) if raw else ""
            except json.JSONDecodeError:
                parsed = raw
            return resp.status, parsed
    except error.HTTPError as exc:
        raw = exc.read().decode("utf-8")
        try:
            parsed = json.loads(raw) if raw else ""
        except json.JSONDecodeError:
            parsed = raw
        return exc.code, parsed


def assert_status(name: str, status_code: int, expected: int | tuple[int, ...], body: Any) -> Result:
    expected_values = expected if isinstance(expected, tuple) else (expected,)
    if status_code not in expected_values:
        return Result(name=name, ok=False, status=status_code, details=f"esperado {expected_values}, recebido {status_code} | body={body}")
    return Result(name=name, ok=True, status=status_code)


def main() -> int:
    project_root = Path(__file__).resolve().parents[1]
    load_env_file(project_root / ".env")

    base_url = os.getenv("GATEWAY_BASE_URL", "http://localhost:8000/api/v1")
    admin_email = os.getenv("ADMIN_EMAIL", "admin@promptuario.health")
    admin_password = os.getenv("ADMIN_PASSWORD", "Admin@12345")

    results: list[Result] = []

    print("== PROMPTUARIO auth smoke test ==")

    health_status, health_body = http_json("GET", f"{base_url.replace('/api/v1', '')}/healthz")
    results.append(assert_status("healthz", health_status, 200, health_body))
    print(f"[{'OK' if results[-1].ok else 'FAIL'}] healthz -> {health_status} {health_body}")

    login_status, login_body = http_json(
        "POST",
        f"{base_url}/auth/login",
        body={"email": admin_email, "password": admin_password},
    )
    login_ok = login_status == 200 and isinstance(login_body, dict) and "access_token" in login_body and "refresh_token" in login_body
    results.append(Result(name="login", ok=login_ok, status=login_status, details=str(login_body)))
    print(f"[{'OK' if login_ok else 'FAIL'}] login -> {login_status}")
    if not login_ok:
        print(login_body)
        return 1

    access_token = normalize_token(str(login_body["access_token"]))
    refresh_token = normalize_token(str(login_body["refresh_token"]))

    me_status, me_body = http_json(
        "GET",
        f"{base_url}/users/me",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    me_ok = me_status == 200 and isinstance(me_body, dict) and me_body.get("role") == "ADMIN"
    results.append(Result(name="users_me", ok=me_ok, status=me_status, details=str(me_body)))
    print(f"[{'OK' if me_ok else 'FAIL'}] users/me -> {me_status} {me_body}")

    refresh_status, refresh_body = http_json(
        "POST",
        f"{base_url}/auth/refresh",
        body={"refresh_token": refresh_token},
    )
    refresh_ok = refresh_status == 200 and isinstance(refresh_body, dict) and "access_token" in refresh_body
    results.append(Result(name="refresh", ok=refresh_ok, status=refresh_status, details=str(refresh_body)))
    print(f"[{'OK' if refresh_ok else 'FAIL'}] refresh -> {refresh_status} {refresh_body}")

    logout_status, logout_body = http_json(
        "POST",
        f"{base_url}/auth/logout",
        body={"refresh_token": refresh_token},
        headers={"Authorization": f"Bearer {access_token}"},
    )
    logout_ok = logout_status in (204, 200)
    results.append(Result(name="logout", ok=logout_ok, status=logout_status, details=str(logout_body)))
    print(f"[{'OK' if logout_ok else 'FAIL'}] logout -> {logout_status} {logout_body}")

    print()
    if all(item.ok for item in results):
        print("All smoke checks passed.")
        return 0

    print("One or more smoke checks failed:")
    for item in results:
        if not item.ok:
            print(f"- {item.name}: status={item.status} {item.details}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())