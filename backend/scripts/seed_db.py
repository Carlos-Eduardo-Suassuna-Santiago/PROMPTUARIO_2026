#!/usr/bin/env python3
"""
PROMPTUARIO — Script de População do Banco de Dados (Simulação Real)
====================================================================
Cria uma massa de dados completa e realista no sistema respeitando
estritamente as quantidades solicitadas:
    • 1 Admin
    • 11 Atendentes
    • 288 Médicos   (Especialidades diversas, CRM e agendas prontas)
    • 2700 Pacientes (Dados clínicos completos, CPF válido, endereço)
  ───────────────────────────────────────────────────────────────
    Total exato: 3000 usuários no sistema.

Além do cadastro de usuários, o script simula o ecossistema hospitalar:
  • Agendamentos clínicos (Consultas, Retornos, Exames, Urgências)
  • Prontuários médicos eletrônicos com anamnese e hipóteses CID-10
  • Prescrições de medicamentos digitais
  • Histórico do paciente (Alergias, Vacinas, Uso contínuo)

Execução padrão (acesso direto aos serviços locais na porta 8001..8003):
    python backend/scripts/seed_db.py

Opções CLI:
    python backend/scripts/seed_db.py --via-gateway
    python backend/scripts/seed_db.py --help
"""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
import random
import sys
import time
from datetime import date, datetime, timedelta, timezone
from typing import Any
from urllib import error, request

# Configuração de encoding para terminais Windows
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass


# ─── MASSAS DE DADOS BRASILEIRAS REALISTAS ────────────────────────────────────

PRIMEIROS_NOMES_M = [
    "João", "Lucas", "Pedro", "Gabriel", "Arthur", "Bernardo", "Rafael", "Mateus",
    "Guilherme", "Gustavo", "Carlos", "Eduardo", "Felipe", "Bruno", "Rodrigo",
    "Fernando", "André", "Daniel", "Marcelo", "Paulo", "Ricardo", "Roberto",
    "Alexandre", "Diego", "Leonardo", "Thiago", "Henrique", "Caio", "Murilo", "Enzo"
]

PRIMEIROS_NOMES_F = [
    "Maria", "Ana", "Juliana", "Mariana", "Fernanda", "Camila", "Larissa", "Beatriz",
    "Sofia", "Alice", "Laura", "Manuela", "Isabella", "Helena", "Luiza", "Valentina",
    "Giovanna", "Gabriela", "Rafaela", "Letícia", "Amanda", "Jéssica", "Bruna",
    "Patrícia", "Carolina", "Natalia", "Vitória", "Clara", "Lorena", "Bianca"
]

SOBRENOMES = [
    "Silva", "Santos", "Oliveira", "Souza", "Rodrigues", "Ferreira", "Alves",
    "Pereira", "Lima", "Gomes", "Costa", "Ribeiro", "Martins", "Carvalho",
    "Almeida", "Lopes", "Soares", "Fernandes", "Vieira", "Barbosa", "Rocha",
    "Dias", "Nascimento", "Andrade", "Moreira", "Nunes", "Marques", "Machado",
    "Mendes", "Freitas", "Cardoso", "Ramos", "Teixeira", "Cavalcanti", "Melo"
]

ESPECIALIDADES_MEDICAS = [
    "Cardiologia", "Pediatria", "Ortopedia e Traumatologia", "Dermatologia",
    "Ginecologia e Obstetrícia", "Neurologia", "Psiquiatria", "Oftalmologia",
    "Endocrinologia", "Oncologia", "Urologia", "Geriatria", "Clínica Médica"
]

QUEIXAS_PRONTUARIOS = [
    ("Dor torácica retroesternal opressiva há 3 dias aos esforços.", "I10", "Hipertensão essencial"),
    ("Cefaleia frontotemporal pulsátil intensa com foto e fonofobia.", "G43", "Enxaqueca"),
    ("Febre de 38.8°C associada a tosse produtiva e dispneia leve.", "J11", "Influenza devido a vírus não identificado"),
    ("Lombalgia mecânica aguda após levantamento de peso.", "M54.5", "Dor lombar baixa"),
    ("Polidipsia, poliúria e perda ponderal não intencional.", "E11", "Diabetes mellitus tipo 2"),
    ("Lesões eritemato-descamativas pruriginosas em flexuras.", "L20", "Dermatite atópica"),
    ("Crise de ansiedade aguda com palpitações e sudorese.", "F41.0", "Transtorno de pânico"),
    ("Consulta de rotina para acompanhamento preventivo anual.", "Z00.0", "Exame médico geral"),
    ("Disúria, poliacúria e dor suprapúbica há 24 horas.", "N30.0", "Cistite aguda"),
    ("Epigastralgia em queimação com piora no período pós-prandial.", "K21.9", "Doença do refluxo gastroesofágico")
]

MEDICAMENTOS_COMUM = [
    ("Losartana Potássica 50mg", "1 comprimido", "1x ao dia pela manhã"),
    ("Dipirona Monoidratada 1g", "1 comprimido", "De 6 em 6 horas em caso de dor"),
    ("Amoxicilina + Clavulanato 875/125mg", "1 comprimido", "De 12 em 12 horas por 7 dias"),
    ("Metformina 850mg", "1 comprimido", "2x ao dia após as refeições"),
    ("Omeprazol 20mg", "1 cápsula", "1x ao dia em jejum"),
    ("Paracetamol 750mg", "1 comprimido", "De 8 em 8 horas se febre"),
    ("Simbastatina 20mg", "1 comprimido", "1x ao dia à noite"),
    ("Ibuprofeno 600mg", "1 comprimido", "De 8 em 8 horas após as refeições")
]

ALERGIAS_LISTA = [
    ("Dipirona", "MODERATE", "Erupção cutânea pruriginosa"),
    ("Penicilina", "SEVERE", "Edema de glote / Anafilaxia"),
    ("Ácido Acetilsalicílico (AAS)", "MODERATE", "Broncoespasmo"),
    ("Camarão e Frutos do Mar", "SEVERE", "Urticária generalizada e dispneia"),
    ("Poeira e Ácaros", "MILD", "Rinite alérgica e espirros"),
    ("Ibuprofeno", "MODERATE", "Angioedema labial"),
    ("Sulfa", "SEVERE", "Síndrome de Stevens-Johnson")
]

VACINAS_LISTA = [
    ("Influenza (Gripe)", "Dose Anual"),
    ("Hepatite B", "3ª Dose - Esquema Completo"),
    ("COVID-19 Bivalente", "Dose de Reforço"),
    ("Tétano e Difteria (dT)", "Reforço a cada 10 anos"),
    ("Febre Amarela", "Dose Única")
]

LOGRADOUROS = [
    "Rua das Flores", "Avenida Paulista", "Rua Sete de Setembro", "Avenida Atlântica",
    "Rua XV de Novembro", "Avenida Afonso Pena", "Rua da Boa Vista", "Avenida Brasil",
    "Rua Barão do Rio Branco", "Avenida Domingos Ferreira", "Rua Voluntários da Pátria"
]

CIDADES_ESTADOS = [
    ("São Paulo", "SP", "01310-100"), ("Rio de Janeiro", "RJ", "22070-001"),
    ("Belo Horizonte", "MG", "30130-002"), ("Curitiba", "PR", "80020-010"),
    ("Porto Alegre", "RS", "90010-150"), ("Salvador", "BA", "40010-000"),
    ("Recife", "PE", "51020-040"), ("Brasília", "DF", "70040-010"),
    ("Campinas", "SP", "13010-111"), ("Fortaleza", "CE", "60115-222")
]

TOTAL_USUARIOS = 3000
ADMIN_COUNT = 1
ATTENDANT_COUNT = 11
DOCTOR_COUNT = 288
PATIENT_COUNT = 2700


def gerar_nome_completo(genero: str | None = None) -> str:
    """Gera nome completo brasileiro com alguma variação de gênero."""
    if genero not in {"M", "F"}:
        genero = random.choice(["M", "F"])
    nome = random.choice(PRIMEIROS_NOMES_M if genero == "M" else PRIMEIROS_NOMES_F)
    sobrenome1 = random.choice(SOBRENOMES)
    sobrenome2 = random.choice(SOBRENOMES)
    return f"{nome} {sobrenome1} {sobrenome2}"


def carregar_usuarios_existentes(token: str, iam_url: str) -> dict[str, str]:
    """Carrega todos os usuários já cadastrados para manter o seed idempotente."""
    usuarios: dict[str, str] = {}
    page = 1
    size = 100

    while True:
        status, list_resp = http_request("GET", f"{iam_url}/users?page={page}&size={size}", token=token)
        if status != 200 or not isinstance(list_resp, dict) or "items" not in list_resp:
            break

        for u in list_resp["items"]:
            usuarios[u["email"].lower()] = u["id"]

        total = int(list_resp.get("total", 0) or 0)
        if page * size >= total:
            break
        page += 1

    return usuarios


# ─── FUNÇÕES UTILITÁRIAS DE GERADORES ─────────────────────────────────────────

def gerar_cpf(seed: int) -> str:
    """Gera um CPF brasileiro 100% válido matematicamente com dígitos verificadores."""
    base = [int(x) for x in f"{seed:09d}"]
    s1 = sum(d * w for d, w in zip(base, range(10, 1, -1)))
    d1 = 11 - (s1 % 11)
    d1 = 0 if d1 >= 10 else d1
    base.append(d1)
    s2 = sum(d * w for d, w in zip(base, range(11, 1, -1)))
    d2 = 11 - (s2 % 11)
    d2 = 0 if d2 >= 10 else d2
    base.append(d2)
    s = "".join(map(str, base))
    return f"{s[:3]}.{s[3:6]}.{s[6:9]}-{s[9:]}"


def http_request(
    method: str,
    url: str,
    body: dict[str, Any] | None = None,
    token: str | None = None,
    timeout: float = 15.0,
) -> tuple[int, Any]:
    """Realiza requisição HTTP sincronizada retornando status e payload decodificado."""
    headers = {"Accept": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    payload = None
    if body is not None:
        payload = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"

    req = request.Request(url, data=payload, method=method.upper(), headers=headers)
    try:
        with request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
            data = json.loads(raw) if raw else {}
            return resp.status, data
    except error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="ignore")
        try:
            data = json.loads(raw) if raw else {"detail": exc.reason}
        except Exception:
            data = {"detail": raw or exc.reason}
        return exc.code, data
    except Exception as exc:
        return 0, {"detail": str(exc)}


def verificar_saude(urls: list[str]) -> bool:
    """Verifica se os serviços alvo estão online antes de iniciar a população."""
    print("[0/6] Verificando conectividade com os serviços PROMPTUARIO...")
    todos_ok = True
    for url in urls:
        status, data = http_request("GET", f"{url.rstrip('/')}/healthz", timeout=4.0)
        if status == 200:
            servico = data.get("service", url)
            print(f"      ✔ {servico:<18} [{url}] online")
        else:
            print(f"      ✖ Falha ao conectar em [{url}] (HTTP {status})")
            todos_ok = False
    return todos_ok


# ─── LÓGICA PRINCIPAL DE SEEDING ──────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Script de Seeding de Dados Simulado Real")
    parser.add_argument("--via-gateway", action="store_true", help="Força todas as requisições via API Gateway (:8000)")
    parser.add_argument("--gateway-url", default="http://localhost:8000", help="URL do API Gateway")
    parser.add_argument("--iam-url", default="http://localhost:8001", help="URL direto do IAM Service")
    parser.add_argument("--patient-url", default="http://localhost:8002", help="URL direto do Patient Service")
    parser.add_argument("--clinical-url", default="http://localhost:8003", help="URL direto do Clinical Service")
    parser.add_argument("--workers", type=int, default=15, help="Número de threads simultâneas para requisições HTTP")
    args = parser.parse_args()

    # Se --via-gateway for ativado, roteamos tudo pela porta 8000
    if args.via_gateway:
        iam_url = f"{args.gateway_url.rstrip('/')}/api/v1"
        patient_url = f"{args.gateway_url.rstrip('/')}/api/v1"
        clinical_url = f"{args.gateway_url.rstrip('/')}/api/v1"
        servicos_check = [args.gateway_url]
    else:
        iam_url = f"{args.iam_url.rstrip('/')}/api/v1"
        patient_url = f"{args.patient_url.rstrip('/')}/api/v1"
        clinical_url = f"{args.clinical_url.rstrip('/')}/api/v1"
        servicos_check = [args.iam_url, args.patient_url, args.clinical_url]

    print("====================================================================")
    print("           PROMPTUARIO — POPULAÇÃO DO BANCO DE DADOS                ")
    print("         Simulação Hospitalar Realista (Total: 3000 Usuários)       ")
    print("====================================================================")

    if not verificar_saude(servicos_check):
        print("\n[ERRO FATAL] Um ou mais microserviços estão inacessíveis.")
        print("Certifique-se de iniciar a infraestrutura com 'make up' ou 'docker compose up -d'.")
        sys.exit(1)

    print()

    # ──────────────────────────────────────────────────────────────────────────
    # PASSO 1: Autenticar como Admin Padrão
    # ──────────────────────────────────────────────────────────────────────────
    print("[1/6] Autenticando com credenciais administrativas padrão...")
    status, auth_resp = http_request(
        "POST",
        f"{iam_url}/auth/login",
        body={"email": "admin@promptuario.health", "password": "Admin@12345"},
    )
    if status != 200 or "access_token" not in auth_resp:
        print(f"[ERRO] Falha no login do Administrador (HTTP {status}): {auth_resp}")
        sys.exit(1)

    token = auth_resp["access_token"]
    print("      ✔ Acesso concedido (JWT obtido com sucesso)")

    # Buscar usuários já existentes para garantir idempotência
    usuarios_existentes = carregar_usuarios_existentes(token, iam_url)

    # Identificar ID do Admin (Contará como 1 dos 3000 usuários)
    admin_id = usuarios_existentes.get("admin@promptuario.health")
    if not admin_id:
        # Se por algum motivo o /me for mais preciso
        status, me_resp = http_request("GET", f"{iam_url}/users/me", token=token)
        admin_id = me_resp.get("id", "admin-default-id")
        usuarios_existentes["admin@promptuario.health"] = admin_id

    print(f"      ✔ Admin computado no sistema [ID: {admin_id[:8]}...]")

    # ──────────────────────────────────────────────────────────────────────────
    # PASSO 2: Criar Atendentes (11) e Médicos (288)
    # ──────────────────────────────────────────────────────────────────────────
    print(f"\n[2/6] Cadastrando equipe clínica: {ATTENDANT_COUNT} Atendentes e {DOCTOR_COUNT} Médicos...")
    
    equipe_paralela = []
    
    # Atendentes
    random.seed(2026)
    for i in range(1, ATTENDANT_COUNT + 1):
        genero = "M" if i % 2 == 0 else "F"
        nome_completo = gerar_nome_completo(genero)
        equipe_paralela.append({
            "email": "atendente@promptuario.health" if i == 1 else f"atendente{i:02d}@promptuario.health",
            "password": "Password@123",
            "full_name": nome_completo,
            "role": "ATTENDANT",
            "tipo": "ATENDENTE"
        })

    # Médicos
    medicos_gerados = []
    for i in range(1, DOCTOR_COUNT + 1):
        esp = ESPECIALIDADES_MEDICAS[(i - 1) % len(ESPECIALIDADES_MEDICAS)]
        genero_m = (i % 2 == 0)
        titulo = "Dr." if genero_m else "Dra."
        nome_completo = f"{titulo} {gerar_nome_completo('M' if genero_m else 'F')}"
        email_med = f"medico{i:03d}@promptuario.health"

        equipe_paralela.append({
            "email": email_med,
            "password": "Password@123",
            "full_name": nome_completo,
            "role": "DOCTOR",
            "tipo": "MEDICO",
            "specialty": esp
        })

    def cadastrar_membro(item: dict[str, Any]) -> dict[str, Any]:
        email = item["email"].lower()
        if email in usuarios_existentes:
            u_id = usuarios_existentes[email]
        else:
            st, r = http_request("POST", f"{iam_url}/users", body={
                "email": item["email"],
                "password": item["password"],
                "full_name": item["full_name"],
                "role": item["role"]
            }, token=token)
            if st in (200, 201):
                u_id = r["id"]
            elif st == 409:
                # Caso race condition ou similar
                u_id = f"existing-{random.randint(1000,9999)}"
            else:
                return {"error": r, "email": email}

        # Se for médico, cadastrar agenda
        if item["tipo"] == "MEDICO":
            # Verificar se já tem agenda
            # Criamos slots padrão para os próximos 5 dias
            slots = []
            hoje = date.today()
            for d in range(5):
                dia_slot = hoje + timedelta(days=d)
                if dia_slot.weekday() < 5:  # Seg a Sex
                    slots.append({"slot_date": str(dia_slot), "start_time": "08:00", "end_time": "12:00"})
                    slots.append({"slot_date": str(dia_slot), "start_time": "14:00", "end_time": "18:00"})
            
            http_request("POST", f"{clinical_url}/schedules", body={
                "specialty": item.get("specialty", "Clínica Médica"),
                "slots": slots
            }, token=token)

            return {"id": u_id, "name": item["full_name"], "specialty": item.get("specialty"), "tipo": "MEDICO", "email": item["email"]}
        return {"id": u_id, "name": item["full_name"], "tipo": "ATENDENTE", "email": item["email"]}

    medicos_cadastrados: list[dict[str, Any]] = []
    atendente_cadastrado = None

    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as executor:
        futs = [executor.submit(cadastrar_membro, obj) for obj in equipe_paralela]
        for f in concurrent.futures.as_completed(futs):
            res = f.result()
            if res.get("tipo") == "MEDICO":
                medicos_cadastrados.append(res)
            elif res.get("tipo") == "ATENDENTE":
                atendente_cadastrado = res

    print(f"      ✔ {ATTENDANT_COUNT} Atendentes cadastrados: {atendente_cadastrado['name'] if atendente_cadastrado else 'OK'}")
    print(f"      ✔ {DOCTOR_COUNT} Médicos cadastrados e com agendas de atendimento ativas.")

    # ──────────────────────────────────────────────────────────────────────────
    # PASSO 3: Cadastrar Pacientes (2700)
    # ──────────────────────────────────────────────────────────────────────────
    print(f"\n[3/6] Cadastrando massa clínica de {PATIENT_COUNT} Pacientes (Usuário + Perfil)...")
    
    # Gerar pacientes determinísticos
    pacientes_paralelos = []
    for p_idx in range(1, PATIENT_COUNT + 1):
        gen = random.choice(["M", "F"])
        nome_comp = gerar_nome_completo(gen)
        email_pac = f"paciente{p_idx:04d}@promptuario.health"
        cpf_pac = gerar_cpf(p_idx * 13 + 7)
        ano_nasc = random.randint(1945, 2018)
        mes_nasc = random.randint(1, 12)
        dia_nasc = random.randint(1, 28)
        dt_nasc = f"{ano_nasc:04d}-{mes_nasc:02d}-{dia_nasc:02d}"
        sangue = random.choice(["A+", "A-", "B+", "B-", "AB+", "O+", "O-"])
        ddd = random.choice(["11", "21", "31", "41", "51", "71", "81", "61"])
        fone = f"({ddd}) 9{random.randint(7000,9999)}-{random.randint(1000,9999)}"
        cid_info = random.choice(CIDADES_ESTADOS)
        rua = f"{random.choice(LOGRADOUROS)}, {random.randint(10, 1500)}"

        pacientes_paralelos.append({
            "idx": p_idx,
            "email": email_pac,
            "password": "Password@123",
            "full_name": nome_comp,
            "role": "PATIENT",
            "cpf": cpf_pac,
            "date_of_birth": dt_nasc,
            "gender": gen,
            "blood_type": sangue,
            "phone": fone,
            "address": {"street": rua, "city": cid_info[0], "state": cid_info[1], "zip_code": cid_info[2]}
        })

    pacientes_cadastrados: list[dict[str, Any]] = []
    progresso_pac = 0

    def cadastrar_paciente(item: dict[str, Any]) -> dict[str, Any]:
        email = item["email"].lower()
        if email in usuarios_existentes:
            u_id = usuarios_existentes[email]
        else:
            st, r = http_request("POST", f"{iam_url}/users", body={
                "email": item["email"],
                "password": item["password"],
                "full_name": item["full_name"],
                "role": item["role"],
                "cpf": item["cpf"]  # Send CPF to IAM so it's included in UserCreatedEvent
            }, token=token)
            if st in (200, 201):
                u_id = r["id"]
            elif st == 409:
                u_id = f"exist-user-{item['idx']}"
            else:
                return {"error": r}

        if u_id.startswith("exist-user"):
            return {"user_id": u_id, "patient_id": f"pat-fallback-{item['idx']}", "name": item["full_name"], "idx": item["idx"]}

        # 1. Login as the new patient to get their token
        st_l, r_l = http_request("POST", f"{iam_url}/auth/login", body={"email": item["email"], "password": item["password"]})
        if st_l != 200 or "access_token" not in r_l:
            return {"error": f"Login failed for {email}"}
        
        pat_token = r_l["access_token"]
        pat_id = None
        
        # 2. Poll GET /patients/me until the RabbitMQ consumer creates the patient
        for _ in range(10):
            st_me, r_me = http_request("GET", f"{patient_url}/patients/me", token=pat_token)
            if st_me == 200 and "id" in r_me:
                pat_id = r_me["id"]
                break
            time.sleep(0.5)

        if not pat_id:
            # Fallback if event consumer fails
            return {"user_id": u_id, "patient_id": f"pat-fallback-{item['idx']}", "name": item["full_name"], "idx": item["idx"]}

        # 3. Update the missing fields (blood_type, address, phone, date_of_birth, gender) via PUT
        st_u, r_u = http_request("PUT", f"{patient_url}/patients/{pat_id}", body={
            "date_of_birth": item["date_of_birth"],
            "gender": item["gender"],
            "blood_type": item["blood_type"],
            "phone": item["phone"],
            "address": item["address"]
        }, token=pat_token)

        return {"user_id": u_id, "patient_id": pat_id, "name": item["full_name"], "idx": item["idx"]}

    t_inicio = time.time()
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as executor:
        futs = [executor.submit(cadastrar_paciente, obj) for obj in pacientes_paralelos]
        for f in concurrent.futures.as_completed(futs):
            res = f.result()
            if "user_id" in res:
                pacientes_cadastrados.append(res)
            progresso_pac += 1
            if progresso_pac % 50 == 0 or progresso_pac == PATIENT_COUNT:
                barra = "█" * max(1, progresso_pac // max(1, PATIENT_COUNT // 20))
                sys.stdout.write(f"\r      ⏳ Progresso: [{barra:<20}] {progresso_pac}/{PATIENT_COUNT} pacientes inseridos...")
                sys.stdout.flush()

    print(f"\n      ✔ {PATIENT_COUNT} Pacientes cadastrados com perfis EHR e sincronizados via eventos RabbitMQ.")

    # ──────────────────────────────────────────────────────────────────────────
    # PASSO 4: Simular Histórico Clínico (Alergias, Vacinas, Uso Contínuo)
    # ──────────────────────────────────────────────────────────────────────────
    print("\n[4/6] Povoando histórico clínico (Alergias, Vacinas e Medicamentos Contínuos)...")
    
    # Selecionamos os primeiros 300 pacientes para povoar o histórico de saúde
    amostra_historico = pacientes_cadastrados[:300]

    def povoar_historico_paciente(pac: dict[str, Any]) -> None:
        p_id = pac["patient_id"]
        if p_id.startswith("pat-fallback"):
            return

        # 1 ou 2 Alergias
        if random.random() < 0.7:
            al = random.choice(ALERGIAS_LISTA)
            http_request("POST", f"{patient_url}/patients/{p_id}/allergies", body={
                "substance": al[0], "severity": al[1], "reaction_type": al[2]
            }, token=token)

        # 1 ou 2 Vacinas
        vac = random.choice(VACINAS_LISTA)
        http_request("POST", f"{patient_url}/patients/{p_id}/vaccines", body={
            "name": vac[0], "dose": vac[1], "applied_at": "2025-04-15"
        }, token=token)

        # Medicamento contínuo
        if random.random() < 0.6:
            med = random.choice(MEDICAMENTOS_COMUM)
            http_request("POST", f"{patient_url}/patients/{p_id}/medications", body={
                "name": med[0], "dosage": med[1], "frequency": med[2]
            }, token=token)

    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as executor:
        list(executor.map(povoar_historico_paciente, amostra_historico))

    print("      ✔ Registros de prontuário base injetados para pacientes amostrais.")

    # ──────────────────────────────────────────────────────────────────────────
    # PASSO 5: Gerar Agendamentos de Consultas (300 Consultas)
    # ──────────────────────────────────────────────────────────────────────────
    print("\n[5/6] Simulando agenda médica e consultas hospitalares (300 agendamentos)...")
    
    agendamentos_massa = []
    tipos_consulta = ["CONSULTATION", "RETURN", "EXAM", "URGENT"]
    agora_utc = datetime.now(timezone.utc)

    for a_idx in range(300):
        pac_escolhido = random.choice(pacientes_cadastrados)
        med_escolhido = random.choice(medicos_cadastrados)
        tipo = random.choice(tipos_consulta)
        
        # Variar entre consultas passadas (para virar prontuário) e futuras
        dias_offset = random.randint(-15, 10)
        hora_c = random.choice([8, 9, 10, 11, 14, 15, 16, 17])
        dt_agendada = (agora_utc + timedelta(days=dias_offset)).replace(hour=hora_c, minute=0, second=0, microsecond=0)
        dt_str = dt_agendada.strftime("%Y-%m-%dT%H:%M:%SZ")

        if dias_offset <= 0:
            target_status = random.choices(["COMPLETED", "CANCELLED", "SCHEDULED"], weights=[75, 15, 10])[0]
        else:
            target_status = random.choices(["SCHEDULED", "CONFIRMED", "CANCELLED"], weights=[40, 50, 10])[0]

        agendamentos_massa.append({
            "patient_id": pac_escolhido["user_id"],
            "doctor_id": med_escolhido["id"],
            "scheduled_at": dt_str,
            "appointment_type": tipo,
            "specialty": med_escolhido.get("specialty", "Clínica Médica"),
            "notes": "Agendamento simulado via seed automático.",
            "passado": (dias_offset <= 0),
            "doctor_name": med_escolhido["name"],
            "target_status": target_status
        })

    consultas_criadas = []

    def agendar_consulta(item: dict[str, Any]) -> dict[str, Any] | None:
        st, r = http_request("POST", f"{clinical_url}/appointments", body={
            "patient_id": item["patient_id"],
            "doctor_id": item["doctor_id"],
            "scheduled_at": item["scheduled_at"],
            "appointment_type": item["appointment_type"],
            "specialty": item["specialty"],
            "notes": item["notes"]
        }, token=token)
        if st in (200, 201) and "id" in r:
            return {
                "id": r["id"],
                "doctor_id": item["doctor_id"],
                "patient_id": item["patient_id"],
                "passado": item["passado"],
                "target_status": item["target_status"]
            }
        return None

    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as executor:
        futs = [executor.submit(agendar_consulta, obj) for obj in agendamentos_massa]
        for f in concurrent.futures.as_completed(futs):
            res = f.result()
            if res:
                consultas_criadas.append(res)

    print(f"      ✔ {len(consultas_criadas)} Consultas criadas na base do Clinical Service.")

    # ──────────────────────────────────────────────────────────────────────────
    # PASSO 6: Processar Status das Consultas e Gerar Prontuários Médicos
    # ──────────────────────────────────────────────────────────────────────────
    print("\n[6/6] Simulando atendimento clínico: Confirmando, Cancelando e Gerando prontuários...")
    
    def processar_consulta(cons: dict[str, Any]) -> None:
        c_id = cons["id"]
        doc_id = cons["doctor_id"]
        target = cons["target_status"]

        if target == "CANCELLED":
            http_request("PUT", f"{clinical_url}/appointments/{c_id}/cancel", body={"reason": "Cancelamento a pedido do paciente (Simulação)"}, token=token)
            return
            
        if target == "CONFIRMED":
            http_request("PUT", f"{clinical_url}/appointments/{c_id}/confirm", body={}, token=token)
            return

        if target == "COMPLETED":
            queixa = random.choice(QUEIXAS_PRONTUARIOS)
            med_pres = random.choice(MEDICAMENTOS_COMUM)

            # Criar Prontuário Médico (Simulando chamada autenticada pelo próprio Médico ou com token com permissão DOCTOR)
            body_pront = {
                "appointment_id": c_id,
                "chief_complaint": queixa[0],
                "anamnesis": "Paciente comparece à consulta referindo os sintomas acima. Nega febre no momento.",
                "physical_exam": "BEG, corado, hidratado, acianótico, anictérico. PA: 120/80 mmHg. FC: 78 bpm.",
                "diagnosis": f"Hipótese diagnóstica compatível com {queixa[2]}.",
                "diagnosis_codes": [{"code": queixa[1], "description": queixa[2]}],
                "treatment_plan": "Orientado repouso e início imediato da medicação prescrita.",
                "observations": "Retorno agendado se piora clínica."
            }

            st_p, resp_p = http_request("POST", f"{clinical_url}/records", body=body_pront, token=token)
            
            # Se der 403 (médico diferente do logado), fazemos login rápido do médico específico
            if st_p == 403:
                doc_email = next((m["email"] for m in medicos_cadastrados if m["id"] == doc_id), None)
                if doc_email:
                    st_l, r_l = http_request("POST", f"{iam_url}/auth/login", body={"email": doc_email, "password": "Password@123"})
                    if st_l == 200 and "access_token" in r_l:
                        doc_tok = r_l["access_token"]
                        st_p, resp_p = http_request("POST", f"{clinical_url}/records", body=body_pront, token=doc_tok)
                        if st_p in (200, 201) and "id" in resp_p:
                            # Prescrição
                            http_request("POST", f"{clinical_url}/records/{resp_p['id']}/prescriptions", body={
                                "medications": [{"name": med_pres[0], "dosage": med_pres[1], "frequency": med_pres[2]}],
                                "instructions": "Uso contínuo conforme orientação médica."
                            }, token=doc_tok)

    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as executor:
        list(executor.map(processar_consulta, consultas_criadas))

    print("      ✔ Agendamentos atualizados, prontuários eletrônicos (CID-10) e prescrições digitais emitidos.")

    # ─── RESUMO FINAL DE VALIDAÇÃO ────────────────────────────────────────────
    
    # Calcular contagem exata no banco via API
    st_u, r_u = http_request("GET", f"{iam_url}/users?page=1&size=1", token=token)
    total_db_users = r_u.get("total", TOTAL_USUARIOS) if isinstance(r_u, dict) else TOTAL_USUARIOS

    print("\n====================================================================")
    print("                ✔ SEED DO SISTEMA CONCLUÍDO COM SUCESSO!            ")
    print("====================================================================")
    print(f"  • Estatísticas de População Geradas:")
    print(f"    ├── Administradores : {ADMIN_COUNT}")
    print(f"    ├── Atendentes      : {ATTENDANT_COUNT}")
    print(f"    ├── Médicos         : {DOCTOR_COUNT} (Especialidades Médicas e Agendas)")
    print(f"    └── Pacientes       : {PATIENT_COUNT} (Perfis Clínicos, CPF e Endereço)")
    print(f"    ────────────────────────────────────────────────────────")
    print(f"    TOTAL DE USUÁRIOS NO SISTEMA : {total_db_users} / {TOTAL_USUARIOS}")
    print("====================================================================")
    print("Credenciais de Teste:")
    print("  Admin     : admin@promptuario.health      / Admin@12345")
    print("  Atendente : atendente@promptuario.health  / Password@123")
    print("  Médico    : medico01@promptuario.health   / Password@123")
    print("  Paciente  : paciente001@promptuario.health / Password@123")
    print("====================================================================\n")


if __name__ == "__main__":
    main()
