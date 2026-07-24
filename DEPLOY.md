# 🚀 Guia Definitivo de Implantação Fullstack (AWS + Vercel)

Esta é a estratégia definitiva para colocar a sua aplicação completa no ar com custo zero ou baixíssimo, dividindo a carga estrategicamente:

- O **Backend** (bancos de dados, filas e microsserviços) ficará na **AWS (Amazon)**, em uma máquina Linux.  
- O **Frontend** (interface React/Vite) ficará na **Vercel**, hospedagem serverless focada em performance.

> [!WARNING]
> **ALERTA DE MEMÓRIA NA AWS**: O arquivo `docker-compose.yml` atual sobe muitos serviços pesados. Se você usar uma `t2.micro` (nível gratuito, 1GB RAM), o uso do **Swap de 4GB** (ensinado abaixo) é obrigatório, mas saiba que a máquina ficará com a CPU em 100% durante o *build*.

---

## PASSO 1: Criando a Máquina na AWS (EC2 & Security Group)

1. Crie uma conta no [AWS Free Tier](https://aws.amazon.com/pt/free/) e busque por **EC2** (Elastic Compute Cloud).
2. Clique em **Executar Instância** (Launch Instance).
3. **Nome:** `promptuario-backend`
4. **Imagem (AMI):** Escolha **Ubuntu Server 22.04 LTS** (ou superior).
5. **Tipo de Instância:** `t2.micro` (ou superior).
6. **Par de chaves (Login):** Crie um novo par de chaves (`.pem`) e faça o download seguro para a sua máquina.

### 🛑 Configurações de Rede (Security Group)
Uma das regras de ouro da segurança na nuvem é **jamais expor bancos de dados para a internet**. Adicione **APENAS** as regras abaixo no Inbound Rules:
- **Porta 22 (SSH):** Permitir tráfego (Recomendado: Apenas do seu IP).
- **Porta 80 (HTTP):** Para o Caddy gerar o certificado SSL (Permitir de qualquer lugar).
- **Porta 443 (HTTPS):** Para acesso seguro aos painéis e à API (Permitir de qualquer lugar).

> [!CAUTION]
> **Portas que NÃO devem ser abertas:** `5432` a `5435` (Postgres), `27017` (MongoDB), `6379` (Redis), `3001` (Grafana), `8000` (Gateway), `15672` (RabbitMQ), etc. O Docker e o Proxy Reverso cuidarão de rotear isso.

7. Conclua clicando em **Executar Instância** e copie o seu **Endereço IPv4 Público**.

---

## PASSO 2: Preparação do DNS (DuckDNS)

Como o frontend na Vercel usa obrigatoriamente HTTPS, o backend também precisa de HTTPS (senão ocorrerá erro de *Mixed Content*).
1. Acesse o painel do [DuckDNS](https://www.duckdns.org/).
2. Atualize o IP associado ao domínio `promptuario.duckdns.org` com o novo IP Público da sua EC2. O DuckDNS já faz o roteamento *wildcard* (qualquer subdomínio apontará para este IP).

### Lista de Subdomínios Mapeados:
- `https://api.promptuario.duckdns.org` ➔ **API Gateway**
- `https://grafana.promptuario.duckdns.org` ➔ **Grafana**
- `https://prometheus.promptuario.duckdns.org` ➔ **Prometheus**
- `https://rabbitmq.promptuario.duckdns.org` ➔ **RabbitMQ Management**
- `https://minio.promptuario.duckdns.org` ➔ **MinIO Web Console**
- `https://s3.promptuario.duckdns.org` ➔ **MinIO API**
- `https://jaeger.promptuario.duckdns.org` ➔ **Jaeger UI**
- `https://mail.promptuario.duckdns.org` ➔ **Mailpit UI**

---

## PASSO 3: Preparando o Linux (Swap, Docker, Caddy)

Acesse sua máquina AWS via terminal (substituindo pelo seu IP e caminho da chave):
```bash
ssh -i aws-key-backend.pem ubuntu@IP_DA_MAQUINA_AWS
```

Execute os comandos abaixo passo a passo:

**1. Criar Swap Memory (4GB)** *(Crucial para máquinas pequenas)*
```bash
sudo fallocate -l 4G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
```

**2. Atualizar Sistema e Instalar Docker**
```bash
sudo apt update && sudo apt upgrade -y
curl -fsSL https://get.docker.com -o get-docker.sh && sudo sh get-docker.sh
sudo usermod -aG docker $USER
# (Dica: Faça logoff e login no SSH para a permissão do docker funcionar sem sudo)
```

**3. Instalar o Proxy Reverso (Caddy)**
```bash
sudo apt install -y debian-keyring debian-archive-keyring apt-transport-https curl
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | sudo gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | sudo tee /etc/apt/sources.list.d/caddy-stable.list
sudo apt update && sudo apt install caddy
```

---

## PASSO 4: Configuração do Proxy (HTTPS Automático)

Abra o arquivo Caddyfile:
```bash
sudo nano /etc/caddy/Caddyfile
```

Cole o conteúdo abaixo (que engloba todas as interfaces seguras):
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
Salve e recarregue o serviço:
```bash
sudo systemctl reload caddy
```

---

## PASSO 5: Código-Fonte e Inicialização

**1. Baixe o Código do Projeto:**
*(Caso privado, registre sua chave SSH primeiro no GitHub com `ssh-keygen`)*
```bash
git clone git@github.com:Carlos-Eduardo-Suassuna-Santiago/PROMPTUARIO_2026.git
cd PROMPTUARIO_2026/backend
```

**2. Segredos locais (`.env`):**
Verifique se você precisa recriar os arquivos `.env` para suprir variáveis não mapeadas no Git.

**3. Inicie o Ecossistema Docker:**
```bash
docker compose up -d
```
Verifique o estado com `docker compose ps`. Se o Grafana carregar via URL (`https://grafana...`), tudo está funcionando perfeitamente!

---

## PASSO 6: Ajustes do CI/CD Automático (GitHub Actions)

Como você recriou o servidor, o GitHub precisa saber o novo IP e a nova chave SSH para fazer os deploys automáticos das atualizações.

1. No repositório, acesse **Settings** -> **Secrets and variables** -> **Actions**.
2. Atualize os Segredos:
   - `SERVER_HOST_BACKEND`: Novo IP Público da EC2.
   - `SERVER_SSH_KEY_BACKEND`: Conteúdo do `.pem` gerado no Passo 1.
   - `SERVER_USER_BACKEND`: `ubuntu`

---

## PASSO 7: Hospedando o Frontend na Vercel

Com a API rodando segura e de forma automatizada no backend, o último passo é plugar a interface.

1. Acesse [Vercel.com](https://vercel.com) e conecte seu GitHub.
2. Clique em **Add New Project** e importe o `PROMPTUARIO_2026`.
3. Em **Framework Preset**, deixe `Vite`.
4. Em **Root Directory**, selecione a pasta `frontend`.
5. Em **Environment Variables**, crie a conexão segura com a sua API AWS:
   - Name: `VITE_API_BASE_URL`
   - Value: `https://api.promptuario.duckdns.org/v1` *(Adapte se sua base URL da API for diferente)*
6. Clique em **Deploy**.

**Pronto! Sua aplicação completa está em nuvem, criptografada, balanceada entre dois provedores top de linha, de forma totalmente gratuita!**

<!-- Last updated by agent -->
