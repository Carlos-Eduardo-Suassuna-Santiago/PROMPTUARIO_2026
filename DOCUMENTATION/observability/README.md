# Observabilidade - PROMPTUARIO

## Componentes

- Logs estruturados JSON com campos padronizados:
  - `timestamp`, `level`, `service`, `module`, `request_id`, `user_id`, `duration_ms`, `http.method`, `http.path`, `status_code`, `message`
- Tracing distribuido com OpenTelemetry + OTLP + Jaeger
- Metricas Prometheus expostas em `/metrics`
- Dashboard Grafana provisionado automaticamente
- Alert rules:
  - `service_down`
  - `error_rate > 5%` por 5m
  - `rabbitmq_queue_backlog > threshold`

## Subir ambiente

A partir da pasta `backend`:

```bash
docker compose up --build
```

## Endpoints uteis

- Grafana: `http://localhost:3000` (admin/admin)
- Prometheus: `http://localhost:9090`
- Jaeger: `http://localhost:16686`
- Gateway health: `http://localhost:8000/healthz/services`

## Smoke test

```bash
python scripts/observability_smoke.py
```

O smoke valida:

- propagacao de `X-Request-Id`
- exposicao das metricas principais em todos os servicos
- presenca de traces basicos no Jaeger
