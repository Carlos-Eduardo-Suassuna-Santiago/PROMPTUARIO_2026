# 🗺️ Mapeamento de Rotas do Sistema

Este documento descreve toda a topologia de rede do sistema, relacionando os subdomínios, as portas e os serviços do Docker.

> [!NOTE]
> O roteamento externo e a criptografia SSL/TLS (HTTPS) são gerenciados pelo **Caddy** nativo rodando na porta 80 e 443 do servidor Ubuntu.

## 1. Serviços de Infraestrutura e Observabilidade

| Serviço | URL Externa (HTTPS) | Porta Interna (Host) | Descrição |
| :--- | :--- | :--- | :--- |
| **Grafana** | `https://grafana.promptuario.duckdns.org` | `3001` | Painel de visualização de métricas (Dashboards). |
| **Prometheus** | `https://prometheus.promptuario.duckdns.org` | `9090` | Motor de coleta de métricas e alertas (Scraping). |
| **RabbitMQ** | `https://rabbitmq.promptuario.duckdns.org` | `15672` | Painel de gerenciamento (Management UI) das filas de eventos assíncronos. |
| **Jaeger** | *(Não exposto externamente)* | `16686` | Rastreamento distribuído de requisições (Tracing). |
| **Mailpit** | *(Não exposto externamente)* | `8025` | Interface Web para capturar e visualizar e-mails enviados em ambiente de testes. |

## 2. API Gateway e Microsserviços

> [!TIP]
> Todo o tráfego externo voltado para o backend da aplicação deve passar obrigatoriamente pelo **API Gateway**. Os microsserviços não são expostos diretamente para a internet.

| Serviço | URL Externa (HTTPS) | Porta Interna (Host) | Descrição |
| :--- | :--- | :--- | :--- |
| **API Gateway** | `https://api.promptuario.duckdns.org` <br> `https://promptuario.duckdns.org` | `8000` | Ponto de entrada central. Orquestra autenticação (IAM) e roteia requisições para os microsserviços. |
| **IAM Service** | *(Rede Interna Docker)* | `8001` | Gerenciamento de Identidade, Autenticação, Tokens JWT e Login com Google. |
| **Patient Service** | *(Rede Interna Docker)* | `8002` | Gerenciamento do ciclo de vida e prontuário dos pacientes. |
| **Clinical Service** | *(Rede Interna Docker)* | `8003` | Consultas, Receituários e interações clínicas diretas. |
| **AI Service** | *(Rede Interna Docker)* | `8004` | Processamento de LLMs (Inteligência Artificial) e sumarização. |
| **Reporting Service**| *(Rede Interna Docker)* | `8005` | Geração de relatórios, webhooks e PDFs assíncronos. |

## 3. Bancos de Dados e Armazenamento

> [!IMPORTANT]
> Por segurança, os bancos de dados **NUNCA** devem ser expostos em subdomínios ou para a rede externa. O acesso a eles deve ocorrer estritamente pela rede interna `backend` do Docker ou por tunelamento SSH.

- **PostgreSQL (IAM):** Porta `5432` no host.
- **PostgreSQL (Patient):** Porta `5433` no host.
- **PostgreSQL (Clinical):** Porta `5434` no host.
- **PostgreSQL (Reporting):** Porta `5435` no host.
- **MongoDB (AI):** Porta `27017` no host.
- **Redis (Cache & Celery):** Porta `6379` no host.
- **MinIO (Object Storage S3):** Porta `9000` (API) e `9001` (Painel Web) no host.

---

### Exemplo de Configuração Padrão do Caddyfile
*(Localizado em `/etc/caddy/Caddyfile` no servidor)*

```caddyfile
grafana.promptuario.duckdns.org {
    reverse_proxy localhost:3001
}

rabbitmq.promptuario.duckdns.org {
    reverse_proxy localhost:15672
}

prometheus.promptuario.duckdns.org {
    reverse_proxy localhost:9090
}

promptuario.duckdns.org, api.promptuario.duckdns.org {
    reverse_proxy localhost:8000
}
```
