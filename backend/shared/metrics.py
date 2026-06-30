"""
PROMPTUARIO — Shared Business Metrics
--------------------------------------
Defines Prometheus counters, histograms, and gauges for business-domain observability.
Each service imports the metrics relevant to its domain.
"""
from prometheus_client import Counter, Histogram, Gauge
from prometheus_client.registry import REGISTRY

# ─── IAM Service Metrics ───────────────────────────────────────────────────────
login_attempts_total = Counter(
    "login_attempts_total",
    "Total de tentativas de login",
    ["service", "status"],  # success | failure
)
active_users = Gauge(
    "active_users",
    "Usuários ativos no momento",
    ["service"],
)
users_registered_total = Counter(
    "users_registered_total",
    "Total de usuários cadastrados",
    ["service", "role"],
)

# ─── Patient Service Metrics ───────────────────────────────────────────────────
patients_registered_total = Counter(
    "patients_registered_total",
    "Total de pacientes cadastrados",
    ["service"],
)
patients_active_total = Gauge(
    "patients_active_total",
    "Pacientes ativos no momento",
    ["service"],
)
allergies_registered_total = Counter(
    "allergies_registered_total",
    "Total de alergias registradas",
    ["service"],
)
vaccines_registered_total = Counter(
    "vaccines_registered_total",
    "Total de vacinas registradas",
    ["service"],
)

# ─── Clinical Service Metrics ──────────────────────────────────────────────────
consultations_total = Counter(
    "consultations_total",
    "Total de consultas realizadas",
    ["service", "status"],  # scheduled | completed | cancelled
)
prescriptions_total = Counter(
    "prescriptions_total",
    "Total de receitas emitidas",
    ["service"],
)
medical_records_total = Counter(
    "medical_records_total",
    "Total de prontuários criados",
    ["service"],
)
exam_requests_total = Counter(
    "exam_requests_total",
    "Total de solicitações de exame",
    ["service", "status"],  # requested | completed
)

# ─── AI Service Metrics ────────────────────────────────────────────────────────
ai_requests_total = Counter(
    "ai_requests_total",
    "Total de requisições à IA",
    ["service", "model", "analysis_type"],
)
ai_tokens_prompt_total = Counter(
    "ai_tokens_prompt_total",
    "Total de tokens de entrada (prompt)",
    ["service", "model"],
)
ai_tokens_completion_total = Counter(
    "ai_tokens_completion_total",
    "Total de tokens de saída (completion)",
    ["service", "model"],
)
ai_request_duration_seconds = Histogram(
    "ai_request_duration_seconds",
    "Latência das requisições à IA (segundos)",
    ["service", "model", "analysis_type"],
    buckets=[0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0],
)
ai_cache_hits_total = Counter(
    "ai_cache_hits_total",
    "Cache hits de respostas da IA",
    ["service"],
)
ai_errors_total = Counter(
    "ai_errors_total",
    "Erros nas requisições à IA",
    ["service", "error_type"],
)

# ─── Reporting Service Metrics ─────────────────────────────────────────────────
reports_generated_total = Counter(
    "reports_generated_total",
    "Total de relatórios gerados",
    ["service", "report_type", "output_format"],
)
reports_errors_total = Counter(
    "reports_errors_total",
    "Total de erros na geração de relatórios",
    ["service", "report_type"],
)

# ─── Event Bus Metrics ─────────────────────────────────────────────────────────
events_published_total = Counter(
    "events_published_total",
    "Total de eventos publicados",
    ["service", "exchange", "routing_key"],
)
events_consumed_total = Counter(
    "events_consumed_total",
    "Total de eventos consumidos",
    ["service", "exchange", "routing_key"],
)
events_processing_duration_seconds = Histogram(
    "events_processing_duration_seconds",
    "Tempo de processamento de eventos",
    ["service", "exchange"],
    buckets=[0.01, 0.05, 0.1, 0.5, 1.0, 5.0],
)