# 🚀 Guia Definitivo de Implantação e Disaster Recovery (AWS EC2)

Este documento é o manual oficial de implantação da infraestrutura do backend. Ele contém todos os detalhes para reconstruir o ambiente de produção do zero, garantindo segurança máxima (Firewall) e roteamento HTTPS para todas as interfaces administrativas do sistema.

---

## 1. Topologia de Rede e Portas (AWS Security Group)

Uma das regras de ouro da segurança na nuvem é **jamais expor bancos de dados ou painéis administrativos brutos para a internet**. Todo o acesso deve ser filtrado pelo Proxy Reverso (Caddy).

Ao criar a nova instância EC2 na AWS, vá até a seção **Security Groups** (Inbound Rules) e libere **APENAS** as seguintes portas para o mundo (`0.0.0.0/0`):

| Porta | Protocolo | Origem | Descrição / Motivo |
| :---: | :---: | :---: | :--- |
| **22** | TCP | Seu IP (Recomendado) | Acesso SSH seguro para administração do servidor. |
| **80** | TCP | `0.0.0.0/0` | Tráfego HTTP. Fundamental para o Caddy validar o certificado SSL junto ao Let's Encrypt. |
| **443** | TCP | `0.0.0.0/0` | Tráfego HTTPS. Todo o acesso aos painéis e à API ocorrerá de forma criptografada por esta porta. |

> [!CAUTION]
> **Portas que NÃO devem ser abertas no Firewall da AWS:**
> - Bancos de Dados: `5432` a `5435` (Postgres), `27017` (MongoDB), `6379` (Redis).
> - Painéis e API: `3001` (Grafana), `8000` (Gateway), `15672` (RabbitMQ), `9090` (Prometheus), `9001` (MinIO), `16686` (Jaeger), `8025` (Mailpit).
> O Docker cuida de liberar essas portas *localmente* no servidor (host), e o Caddy fará a ponte do tráfego da porta `443` direto para as portas internas.

---

## 2. Preparação do DNS (DuckDNS)

Como o IP público do servidor mudará, acesse o painel do [DuckDNS](https://www.duckdns.org/) e atualize o IP do domínio base (`promptuario.duckdns.org`). O DuckDNS já faz o roteamento *wildcard* automático (qualquer subdomínio apontará para este IP).

### Lista Oficial de Interfaces Web (Subdomínios)
Você usará as URLs abaixo para acessar o sistema no navegador:

- `https://api.promptuario.duckdns.org` ➔ **API Gateway** (Ponto de entrada do Frontend/Mobile)
- `https://grafana.promptuario.duckdns.org` ➔ **Grafana** (Dashboards de Monitoramento e Logs)
- `https://prometheus.promptuario.duckdns.org` ➔ **Prometheus** (Métricas brutas e Alertas)
- `https://rabbitmq.promptuario.duckdns.org` ➔ **RabbitMQ Management** (Gestão de Filas e Mensagens)
- `https://minio.promptuario.duckdns.org` ➔ **MinIO Web Console** (Gestão do Storage S3, PDFs e Imagens)
- `https://s3.promptuario.duckdns.org` ➔ **MinIO API** (Endpoint usado pelas aplicações para upload via código)
- `https://jaeger.promptuario.duckdns.org` ➔ **Jaeger UI** (Rastreamento de requisições / Tracing distribuído)
- `https://mail.promptuario.duckdns.org` ➔ **Mailpit UI** (Caixa de entrada de E-mails interceptados nos testes)

---

## 3. Preparação do Servidor (Linux Ubuntu)

Acesse a máquina via SSH e prepare o ambiente instalando Docker, Git e Caddy:

```bash
# 1. Atualizar o sistema
sudo apt update && sudo apt upgrade -y

# 2. Instalar Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# 3. Dar permissão ao usuário para rodar Docker sem "sudo"
sudo usermod -aG docker ubuntu
# (Saia do SSH e entre novamente para aplicar esta permissão)

# 4. Instalar o Caddy (Proxy Reverso)
sudo apt install -y debian-keyring debian-archive-keyring apt-transport-https curl
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | sudo gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | sudo tee /etc/apt/sources.list.d/caddy-stable.list
sudo apt update
sudo apt install caddy
```

---

## 4. Configuração do Proxy Reverso (O Caddyfile Completo)

Agora configuraremos o Caddy para servir todos os subdomínios mapeados na seção 2 com HTTPS automático.

```bash
sudo nano /etc/caddy/Caddyfile
```

Cole o conteúdo abaixo, que engloba **todas** as interfaces administrativas do sistema:

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

jaeger.promptuario.duckdns.org {
    reverse_proxy localhost:16686
}

mail.promptuario.duckdns.org {
    reverse_proxy localhost:8025
}

minio.promptuario.duckdns.org {
    reverse_proxy localhost:9001
}

s3.promptuario.duckdns.org {
    reverse_proxy localhost:9000
}

promptuario.duckdns.org, api.promptuario.duckdns.org {
    reverse_proxy localhost:8000
}
```

Recarregue o Caddy para aplicar:
```bash
sudo systemctl reload caddy
```

---

## 5. Clonagem e Configuração do Repositório

```bash
# Caso o repositório seja privado, configure a chave SSH:
ssh-keygen -t rsa -b 4096 -C "seu-email@exemplo.com"
cat ~/.ssh/id_rsa.pub # Cole esta chave no painel do GitHub

# Clonar
git clone git@github.com:Carlos-Eduardo-Suassuna-Santiago/PROMPTUARIO_2026.git
cd PROMPTUARIO_2026/backend
```

### Configuração de Segredos (Secrets)
> [!IMPORTANT]
> Verifique a necessidade de criar um arquivo `.env` na pasta `backend/` caso as senhas dos bancos (`DB_IAM_PASSWORD`, `DB_PATIENT_PASSWORD`, etc.) não estejam chumbadas com fallback (`:-password`) no `docker-compose.yml`.

---

## 6. Inicialização do Ecossistema

Com tudo pronto, inicie a arquitetura completa em segundo plano:

```bash
docker compose up -d
```

Validando o estado:
```bash
docker compose ps
```
*Nenhum contêiner deve estar como `Restarting`. Se houver falha, analise com `docker compose logs [nome-do-serviço]`.*

---

## 7. Ajustes do CI/CD (GitHub Actions)

Toda a sua esteira de integração e entrega contínua (os pipelines de Deploy) depende de acessar o servidor para atualizar o código automaticamente. Como você criou uma AWS nova, você precisa reconfigurar as credenciais no GitHub.

1. No repositório, acesse **Settings** -> **Secrets and variables** -> **Actions**.
2. Atualize ou recrie as variáveis:
   - **`SERVER_HOST_BACKEND`**: O *Novo IP Público* da instância EC2.
   - **`SERVER_SSH_KEY_BACKEND`**: A nova chave `.pem` fornecida pela AWS ao criar a instância.
   - **`SERVER_USER_BACKEND`**: `ubuntu` (ou o usuário padrão da instância).

Feito isso, o sistema está **100% restaurado**, criptografado com SSL/TLS de ponta a ponta e preparado para atualizações automatizadas!
