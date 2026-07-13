import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shared.audit import build_audit_event, sanitize_payload, AuditLog
from shared.observability import clear_request_context, get_request_context, set_request_context


def test_sanitize_payload_redacts_sensitive_fields_recursively():
    payload = {
        "name": "Ana",
        "credentials": {
            "password": "secret123",
            "token": "abc.def",
            "nested": [{"access_token": "x"}, {"note": "ok"}],
        },
    }

    sanitized = sanitize_payload(payload)

    assert sanitized["name"] == "Ana"
    assert sanitized["credentials"]["password"] == "[REDACTED]"
    assert sanitized["credentials"]["token"] == "[REDACTED]"
    assert sanitized["credentials"]["nested"][0]["access_token"] == "[REDACTED]"
    assert sanitized["credentials"]["nested"][1]["note"] == "ok"


def test_sanitize_payload_redacts_jwt_and_bearer():
    payload = {
        "jwt": "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PlFUP0THsR8",
        "bearer": "some-token",
        "credit_card": "4111-1111-1111-1111",
        "medical_history_raw": "patient has HIV",
    }
    sanitized = sanitize_payload(payload)
    assert sanitized["jwt"] == "[REDACTED]"
    assert sanitized["bearer"] == "[REDACTED]"
    assert sanitized["credit_card"] == "[REDACTED]"
    assert sanitized["medical_history_raw"] == "[REDACTED]"


def test_build_audit_event_uses_standard_fields_and_masks_values():
    event = build_audit_event(
        service="iam-service",
        operation="AUTH_LOGIN",
        target="user:123",
        user="user-1",
        request_id="req-42",
        correlation_id="corr-99",
        old_values={"password": "old"},
        new_values={"token": "abc"},
    )

    assert event["service"] == "iam-service"
    assert event["operation"] == "AUTH_LOGIN"
    assert event["target"] == "user:123"
    assert event["user"] == "user-1"
    assert event["request_id"] == "req-42"
    assert event["correlation_id"] == "corr-99"
    assert event["timestamp"].endswith("Z")
    assert event["old_values"]["password"] == "[REDACTED]"
    assert event["new_values"]["token"] == "[REDACTED]"


def test_build_audit_event_falls_back_to_context():
    clear_request_context()
    set_request_context(request_id="ctx-req", correlation_id="ctx-corr", user_id="ctx-user")
    event = build_audit_event(
        service="patient-service",
        operation="INSERT",
        target="patients/123",
    )
    assert event["request_id"] == "ctx-req"
    assert event["correlation_id"] == "ctx-corr"
    assert event["user"] == "ctx-user"
    clear_request_context()


def test_request_context_round_trip():
    clear_request_context()
    set_request_context(request_id="req-100", correlation_id="corr-100", ip_address="192.168.1.1")
    ctx = get_request_context()
    assert ctx["request_id"] == "req-100"
    assert ctx["correlation_id"] == "corr-100"
    assert ctx["ip_address"] == "192.168.1.1"
    clear_request_context()
    assert get_request_context() == {}


def test_audit_log_model_has_correlation_id():
    """Verify that the AuditLog model includes the correlation_id field."""
    columns = {c.name: c for c in AuditLog.__table__.columns}
    assert "correlation_id" in columns
    assert "request_id" in columns
    assert "service_name" in columns
    assert "operation" in columns
    assert "ip_address" in columns


def test_sanitize_payload_handles_nested_lists():
    payload = {
        "medications": [
            {"name": "Paracetamol", "dosage": "500mg"},
            {"name": "Ibuprofeno", "dosage": "600mg", "token": "abc123"},
        ]
    }
    sanitized = sanitize_payload(payload)
    assert sanitized["medications"][0]["name"] == "Paracetamol"
    assert sanitized["medications"][1]["token"] == "[REDACTED]"
    assert sanitized["medications"][1]["name"] == "Ibuprofeno"


def test_sanitize_payload_handles_non_dict():
    assert sanitize_payload("hello") == "hello"
    assert sanitize_payload("my_token_here") == "[REDACTED]"
    assert sanitize_payload(123) == 123
    assert sanitize_payload(None) is None