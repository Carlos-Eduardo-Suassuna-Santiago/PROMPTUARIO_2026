from __future__ import annotations

import json
import os
import sys
import unicodedata
import traceback
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib import error, request
from urllib.parse import quote, quote_plus, urlsplit, urlunsplit
import re

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass


def safe_text(value: Any) -> str:
    text = str(value)
    normalized = unicodedata.normalize("NFKD", text)
    return normalized.encode("ascii", "ignore").decode("ascii")


def normalize_url(url: str) -> str:
    split = urlsplit(url)
    path = quote(split.path, safe="/%:@")

    query_parts: list[str] = []
    if split.query:
        for part in split.query.split("&"):
            if not part:
                continue
            if "=" in part:
                key, value = part.split("=", 1)
                query_parts.append(f"{quote_plus(key, safe='') }={quote_plus(value, safe='')}")
            else:
                query_parts.append(quote_plus(part, safe=""))

    return urlunsplit((split.scheme, split.netloc, path, "&".join(query_parts), split.fragment))


@dataclass
class Result:
    name: str
    ok: bool
    status: int | None = None
    details: str = ""


def print_collection_intro() -> None:
    print("  00 - Healthcheck de cada servico")
    print("  01 - Acesso ao /docs de cada servico")
    print("  02 - Validacao do /openapi.json e rota esperada")
    print("  03 - Verificacao de endpoint protegido sem token")
    print("  04 - Login via gateway e captura de access_token")
    print("  05 - Chamadas autenticadas para rotas proxy do gateway")
    print()


def print_step(title: str, description: str, method: str, url: str, expected: str) -> None:
    print(f"[STEP] {safe_text(title)}")
    print(f"  descricao: {safe_text(description)}")
    print(f"  request: {method.upper()} {safe_text(url)}")
    print(f"  esperado: {safe_text(expected)}")


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


def http_json(
    method: str,
    url: str,
    body: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
) -> tuple[int, dict[str, Any] | list[Any] | str]:
    url = normalize_url(url)
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
        return Result(
            name=name,
            ok=False,
            status=status_code,
            details=f"esperado {expected_values}, recebido {status_code} | body={body}",
        )
    return Result(name=name, ok=True, status=status_code)


def assert_openapi_path(name: str, status_code: int, body: Any, expected_path: str) -> Result:
    if status_code != 200:
        return Result(name=name, ok=False, status=status_code, details=f"openapi indisponivel: {body}")
    if not isinstance(body, dict):
        return Result(name=name, ok=False, status=status_code, details="openapi nao retornou JSON")

    paths = body.get("paths")
    if not isinstance(paths, dict):
        return Result(name=name, ok=False, status=status_code, details="campo paths ausente no openapi")

    if expected_path not in paths:
        return Result(
            name=name,
            ok=False,
            status=status_code,
            details=f"path esperado ausente no openapi: {expected_path}",
        )

    return Result(name=name, ok=True, status=status_code)


def print_result(result: Result) -> None:
    tag = "OK" if result.ok else "FAIL"
    suffix = "" if result.ok else f" | {result.details}"
    print(f"[{tag}] {safe_text(result.name)} -> {result.status}{safe_text(suffix)}")
    print()


def print_generated_tokens(access_token: str, refresh_token: str | None) -> None:
    print("[TOKENS] Tokens gerados no login:")
    print(f"  access_token: {safe_text(access_token)}")
    if refresh_token:
        print(f"  refresh_token: {safe_text(refresh_token)}")
    else:
        print("  refresh_token: <nao retornado>")
    print()


def print_entity_summary(title: str, fields: dict[str, Any]) -> None:
    if not fields:
        return
    print(f"[{safe_text(title)}]")
    for key, value in fields.items():
        print(f"  {safe_text(key)}: {safe_text(value)}")
    print()


def extract_first_dict(value: Any) -> dict[str, Any] | None:
    if isinstance(value, dict):
        return value
    if isinstance(value, list):
        for item in value:
            if isinstance(item, dict):
                return item
    return None


def build_user_summary(resp_body: Any, req_body: Any) -> dict[str, Any]:
    candidates: list[dict[str, Any]] = []

    def collect_dicts(value: Any) -> None:
        if isinstance(value, dict):
            candidates.append(value)
            for nested in value.values():
                collect_dicts(nested)
        elif isinstance(value, list):
            for item in value:
                collect_dicts(item)

    collect_dicts(resp_body)
    collect_dicts(req_body)

    for payload in candidates:
        summary: dict[str, Any] = {}
        for key in ("id", "user_id", "email", "full_name", "name", "role", "created_at", "updated_at"):
            if key in payload and payload[key] not in (None, ""):
                summary[key] = payload[key]

        if summary:
            return summary

    return {}


def build_appointment_summary(resp_body: Any, req_body: Any) -> dict[str, Any]:
    candidates: list[dict[str, Any]] = []

    def collect_dicts(value: Any) -> None:
        if isinstance(value, dict):
            candidates.append(value)
            for nested in value.values():
                collect_dicts(nested)
        elif isinstance(value, list):
            for item in value:
                collect_dicts(item)

    collect_dicts(resp_body)
    collect_dicts(req_body)

    for payload in candidates:
        summary: dict[str, Any] = {}
        for key in (
            "id",
            "appointment_id",
            "patient_id",
            "doctor_id",
            "scheduled_at",
            "appointment_type",
            "specialty",
            "status",
            "notes",
            "reason",
            "created_at",
            "updated_at",
        ):
            if key in payload and payload[key] not in (None, ""):
                summary[key] = payload[key]

        if "scheduled_at" in summary or "appointment_type" in summary or "patient_id" in summary or "doctor_id" in summary:
            return summary

    return {}


def main() -> int:
    project_root = Path(__file__).resolve().parents[1]
    load_env_file(project_root / ".env")

    gateway_base = os.getenv("GATEWAY_BASE_URL", "http://localhost:8000")

    services = {
        "gateway": {
            "base": os.getenv("GATEWAY_URL", gateway_base),
            "auth_probe": None,
            "openapi_path": "/healthz",
        },
        "iam": {
            "base": os.getenv("IAM_BASE_URL", "http://localhost:8001"),
            "auth_probe": "/api/v1/users",
            "openapi_path": "/api/v1/auth/login",
        },
        "patient": {
            "base": os.getenv("PATIENT_BASE_URL", "http://localhost:8002"),
            "auth_probe": "/api/v1/patients",
            "openapi_path": "/api/v1/patients",
        },
        "clinical": {
            "base": os.getenv("CLINICAL_BASE_URL", "http://localhost:8003"),
            "auth_probe": "/api/v1/appointments",
            "openapi_path": "/api/v1/appointments",
        },
        "ai": {
            "base": os.getenv("AI_BASE_URL", "http://localhost:8004"),
            "auth_probe": "/api/v1/ai/jobs/demo",
            "openapi_path": "/api/v1/ai/analyze",
        },
        "reporting": {
            "base": os.getenv("REPORTING_BASE_URL", "http://localhost:8005"),
            "auth_probe": "/api/v1/reports/summary",
            "openapi_path": "/api/v1/reports/export",
        },
    }

    credential_candidates: list[tuple[str, str]] = []
    if os.getenv("ADMIN_EMAIL") and os.getenv("ADMIN_PASSWORD"):
        credential_candidates.append((os.getenv("ADMIN_EMAIL", ""), os.getenv("ADMIN_PASSWORD", "")))
    if os.getenv("FIRST_ADMIN_EMAIL") and os.getenv("FIRST_ADMIN_PASSWORD"):
        credential_candidates.append((os.getenv("FIRST_ADMIN_EMAIL", ""), os.getenv("FIRST_ADMIN_PASSWORD", "")))
    credential_candidates.append(("admin@promptuario.health", "Admin@12345"))

    seen: set[tuple[str, str]] = set()
    unique_credentials: list[tuple[str, str]] = []
    for item in credential_candidates:
        if item not in seen:
            seen.add(item)
            unique_credentials.append(item)

    results: list[Result] = []

    print("== PROMPTUARIO FastAPI full smoke test ==")
    print_collection_intro()

    for service_name, cfg in services.items():
        base = str(cfg["base"]).rstrip("/")

        print_step(
            f"{service_name} :: 00-healthz",
            "Confirma se o servico esta ativo e respondendo no endpoint de saude.",
            "GET",
            f"{base}/healthz",
            "HTTP 200",
        )
        status, body = http_json("GET", f"{base}/healthz")
        result = assert_status(f"{service_name}:healthz", status, 200, body)
        results.append(result)
        print_result(result)

        print_step(
            f"{service_name} :: 01-docs",
            "Valida se a interface Swagger/Docs da FastAPI esta disponivel.",
            "GET",
            f"{base}/docs",
            "HTTP 200",
        )
        status, body = http_json("GET", f"{base}/docs")
        result = assert_status(f"{service_name}:docs", status, 200, body)
        results.append(result)
        print_result(result)

        print_step(
            f"{service_name} :: 02-openapi",
            "Garante que o OpenAPI expose a rota principal esperada para esse servico.",
            "GET",
            f"{base}/openapi.json",
            f"HTTP 200 + path {cfg['openapi_path']}",
        )
        status, body = http_json("GET", f"{base}/openapi.json")
        result = assert_openapi_path(
            f"{service_name}:openapi",
            status,
            body,
            str(cfg["openapi_path"]),
        )
        results.append(result)
        print_result(result)

        auth_probe = cfg.get("auth_probe")
        if auth_probe:
            print_step(
                f"{service_name} :: 03-auth-required",
                "Simula request sem Authorization para confirmar protecao por JWT.",
                "GET",
                f"{base}{auth_probe}",
                "HTTP 401 ou 403",
            )
            status, body = http_json("GET", f"{base}{auth_probe}")
            result = assert_status(f"{service_name}:auth_required", status, (401, 403), body)
            results.append(result)
            print_result(result)

    login_status = 0
    login_body: dict[str, Any] | list[Any] | str = ""
    login_ok = False
    used_email = ""

    print_step(
        "gateway :: 04-auth-login",
        "Replica o request de login do Insomnia e captura access_token para os proximos passos.",
        "POST",
        f"{gateway_base.rstrip('/')}/api/v1/auth/login",
        "HTTP 200 + access_token",
    )
    for email, password in unique_credentials:
        status_code, body = http_json(
            "POST",
            f"{gateway_base.rstrip('/')}/api/v1/auth/login",
            body={"email": email, "password": password},
        )
        login_status = status_code
        login_body = body
        if (
            login_status == 200
            and isinstance(login_body, dict)
            and "access_token" in login_body
        ):
            login_ok = True
            used_email = email
            break

    login_result = Result(
        name="gateway:auth_login",
        ok=login_ok,
        status=login_status,
        details=(f"email={used_email} {login_body}" if login_ok else str(login_body)),
    )
    results.append(login_result)
    print_result(login_result)

    access_token = ""
    if login_ok:
        access_token = normalize_token(str(login_body["access_token"]))
        refresh_token = None
        if isinstance(login_body, dict) and "refresh_token" in login_body:
            refresh_token = normalize_token(str(login_body["refresh_token"]))
        print_generated_tokens(access_token, refresh_token)

        gateway_authorized_checks = [
            ("gateway:users_authorized", "/api/v1/users"),
            ("gateway:patients_authorized", "/api/v1/patients"),
            ("gateway:appointments_authorized", "/api/v1/appointments"),
            ("gateway:ai_authorized", "/api/v1/ai/records/nonexistent/analyses"),
            ("gateway:reports_authorized", "/api/v1/reports/summary"),
        ]

        for name, path in gateway_authorized_checks:
            print_step(
                f"gateway :: 05-authorized :: {name}",
                "Valida proxy autenticado via gateway para servicos internos.",
                "GET",
                f"{gateway_base.rstrip('/')}{path}",
                "Nao retornar 401/403",
            )
            status, body = http_json(
                "GET",
                f"{gateway_base.rstrip('/')}{path}",
                headers={"Authorization": f"Bearer {access_token}"},
            )
            ok = status not in (401, 403)
            result = Result(name=name, ok=ok, status=status, details=str(body))
            results.append(result)
            print_result(result)

    print()
    ok_count = sum(1 for item in results if item.ok)
    fail_count = len(results) - ok_count
    print(f"Resumo: total={len(results)} ok={ok_count} fail={fail_count}")
    print()

    if all(item.ok for item in results):
        print("All FastAPI service checks passed.")
        return 0

    print("One or more checks failed:")
    for item in results:
        if not item.ok:
            print(f"- {item.name}: status={item.status} {item.details}")
    return 1


if __name__ == "__main__":
    # Run main checks
    exit_code = main()

    # Additional: try to load Insomnia collection and run its requests
    def load_insomnia_collection(path: Path) -> list[dict[str, Any]]:
        if not path.exists():
            return []
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return []

        resources = data.get("resources") if isinstance(data, dict) else None
        if not isinstance(resources, list):
            return []

        requests_list: list[dict[str, Any]] = []
        for item in resources:
            if not isinstance(item, dict):
                continue
            if item.get("_type") != "request":
                continue
            url = item.get("url") or item.get("uri") or ""
            method = (item.get("method") or "GET").upper()
            body = None
            body_def = item.get("body") or {}
            if isinstance(body_def, dict):
                # Insomnia stores body.text
                text = body_def.get("text")
                if isinstance(text, str) and text.strip():
                    try:
                        body = json.loads(text)
                    except Exception:
                        body = text

            # headers may be list of {name,value}
            headers = {}
            for h in item.get("headers") or []:
                if isinstance(h, dict) and h.get("name"):
                    headers[h.get("name")] = h.get("value", "")

            requests_list.append({
                "name": item.get("name", "unnamed"),
                "method": method,
                "url": url,
                "body": body,
                "headers": headers,
                "description": item.get("description", ""),
            })

        return requests_list

    def substitute_env_vars(text: str, gateway_base_value: str) -> str:
        # Replace {{ VAR }} with environment variable VAR when available
        fallback_values = {
            "base_url": gateway_base_value.rstrip("/") + "/api/v1",
            "gateway_base_url": gateway_base_value,
            "gateway_url": os.getenv("GATEWAY_URL", gateway_base_value),
            "admin_email": os.getenv("ADMIN_EMAIL", "admin@promptuario.health"),
            "admin_password": os.getenv("ADMIN_PASSWORD", "Admin@12345"),
            "refresh_token": os.getenv("refresh_token", ""),
            "access_token": os.getenv("access_token", ""),
        }

        def repl(m: re.Match) -> str:
            var = m.group(1)
            return os.environ.get(var, fallback_values.get(var, m.group(0)))

        return re.sub(r"{{\s*([^}\s]+)\s*}}", repl, text)

    def substitute_placeholders(value: Any, gateway_base_value: str) -> Any:
        if isinstance(value, str):
            return substitute_env_vars(value, gateway_base_value)
        if isinstance(value, dict):
            return {key: substitute_placeholders(val, gateway_base_value) for key, val in value.items()}
        if isinstance(value, list):
            return [substitute_placeholders(item, gateway_base_value) for item in value]
        return value

    def run_insomnia_tests(gateway_base_value: str):
        script_path = Path(__file__).resolve()
        coll_candidates = [
            script_path.parents[2] / "PROMPTUARIO_Insomnia_Collection.json",
            script_path.parents[1] / "PROMPTUARIO_Insomnia_Collection.json",
            script_path.parents[2] / "promptuario-backend" / "PROMPTUARIO_Insomnia_Collection.json",
        ]
        coll = next((candidate for candidate in coll_candidates if candidate.exists()), coll_candidates[0])
        tests = load_insomnia_collection(coll)
        if not tests:
            print(f"Nenhuma request da collection Insomnia encontrada em: {coll}")
            raise SystemExit(exit_code)

        print("== Executando requests da collection Insomnia ==")
        insomnia_results: list[Result] = []
        for req_item in tests:
            name = req_item["name"]
            method = req_item["method"]
            raw_url = str(req_item["url"])
            url = substitute_env_vars(raw_url, gateway_base_value)
            body = substitute_placeholders(req_item.get("body"), gateway_base_value)
            headers = substitute_placeholders(dict(req_item.get("headers") or {}), gateway_base_value)

            print_step(
                f"insomnia :: {name}",
                req_item.get("description", ""),
                method,
                url,
                "verificar resposta e status",
            )

            status, resp_body = http_json(method, url, body=body if isinstance(body, dict) else None, headers=headers)

            # extract meaningful info from response and request
            extracted: dict[str, str] = {}
            if isinstance(resp_body, dict):
                # tokens
                if "access_token" in resp_body:
                    tok = normalize_token(str(resp_body.get("access_token") or ""))
                    os.environ.setdefault("access_token", tok)
                    extracted["access_token"] = tok
                if "refresh_token" in resp_body:
                    rt = normalize_token(str(resp_body.get("refresh_token") or ""))
                    os.environ.setdefault("refresh_token", rt)
                    extracted["refresh_token"] = rt

                # generic id fields
                for candidate in ("id", "user_id", "patient_id", "appointment_id", "record_id", "prescription_id", "ai_job_id"):
                    if candidate in resp_body:
                        val = str(resp_body.get(candidate))
                        os.environ.setdefault(candidate, val)
                        extracted[candidate] = val

                # sometimes the API nests data under 'data' or returns the created resource
                if "data" in resp_body and isinstance(resp_body["data"], dict):
                    for k, v in resp_body["data"].items():
                        if k in ("id", "user_id", "patient_id", "appointment_id", "record_id"):
                            os.environ.setdefault(k, str(v))
                            extracted[k] = str(v)

            # infer from request body when possible
            if isinstance(body, dict):
                # user creation
                if method == "POST" and "/users" in url:
                    if "email" in body:
                        os.environ.setdefault("last_created_user_email", str(body["email"]))
                        extracted["created_user_email"] = str(body["email"])
                    if "role" in body:
                        role = str(body["role"]).lower()
                        # if we have an id in extracted, store role-specific var
                        uid = extracted.get("id") or extracted.get("user_id")
                        if uid:
                            env_key = f"user_id_{role}"
                            os.environ.setdefault(env_key, uid)
                            extracted[env_key] = uid

                # patient creation
                if method == "POST" and "/patients" in url:
                    if "user_id" in body:
                        os.environ.setdefault("patient_user_id", str(body["user_id"]))
                        extracted["patient_user_id"] = str(body["user_id"])

                # appointment scheduling
                if method == "POST" and "/appointments" in url:
                    if "patient_id" in body:
                        extracted["appointment_patient_id"] = str(body.get("patient_id"))
                    if "doctor_id" in body:
                        extracted["appointment_doctor_id"] = str(body.get("doctor_id"))
                    if "scheduled_at" in body:
                        extracted["scheduled_at"] = str(body.get("scheduled_at"))

            user_summary = build_user_summary(resp_body, body)
            if user_summary:
                print_entity_summary("USUARIO", user_summary)

            appointment_summary = build_appointment_summary(resp_body, body)
            if appointment_summary and ("appointment" in name.lower() or "/appointments" in url):
                print_entity_summary("AGENDAMENTO", appointment_summary)

            details = f"req_body={body} | resp_body={resp_body} | extracted={extracted}"
            result = Result(name=f"insomnia:{name}", ok=(200 <= (status or 0) < 400), status=status, details=details)
            insomnia_results.append(result)
            print_result(result)

        ok_count = sum(1 for item in insomnia_results if item.ok)
        fail_count = len(insomnia_results) - ok_count
        print(f"Insomnia resumo: total={len(insomnia_results)} ok={ok_count} fail={fail_count}")

    try:
        run_insomnia_tests(os.getenv("GATEWAY_BASE_URL", "http://localhost:8000"))
    except Exception as exc:  # keep script non-fatal if collection parsing fails
        print(f"Ignorando execucao Insomnia: {exc}")
        print(traceback.format_exc())

    raise SystemExit(exit_code)
