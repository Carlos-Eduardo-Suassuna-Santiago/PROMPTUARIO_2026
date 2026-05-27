# CASOS DE USO

## PROMPTUARIO Backend

Este documento apresenta a visao funcional do sistema em formato de casos de uso, cobrindo os principais atores, interacoes e responsabilidades dos servicos distribuidos.

---

## 1. Atores

- **Paciente**: acessa o portal, consulta dados e acompanha seu atendimento.
- **Medico**: realiza consultas, registra prontuarios, gera prescricoes e solicita analises.
- **Atendente**: apoia o cadastro, o agendamento e a gestao operacional.
- **Administrador**: administra usuarios, acessos, parametros e auditoria.
- **Operador**: acompanha saude, logs, metricas e disponibilidade da plataforma.

---

## 2. Escopo Funcional

O limite do sistema engloba:
- Gateway de entrada e validacao de autenticacao.
- Servico IAM para login, refresh, logout e gestao de usuarios.
- Servico de Pacientes para cadastro e manutencao de dados clinicos e cadastrais.
- Servico Clinico para agenda, consultas, prontuarios, prescricoes e exames.
- Servico de IA para analises assicronas.
- Servico de Relatorios para exportacoes e consultas gerenciais.
- Camada de observabilidade para logs, metricas, traces e alertas.

---

## 3. Regras de Negocio Representadas

1. Todo acesso autenticado passa pelo Gateway antes de chegar aos servicos.
2. O Administrador possui permissao para gestao global de usuarios e saude operacional.
3. O Medico pode executar as atividades clinicas centrais do sistema.
4. O Atendente atua como apoio operacional em cadastro e agendamento.
5. O Paciente acessa apenas dados e operacoes permitidas sobre o proprio contexto.
6. As analises de IA e os relatorios sao processados de forma assincrona quando aplicavel.

---

## 4. Mapeamento Para os Principais Modulos

- **IAM**: autenticar usuario, renovar token, encerrar sessao, gerenciar usuarios.
- **Patient**: gerenciar pacientes, alergias, vacinas e medicacoes continuas.
- **Clinical**: agendar consultas, cancelar consultas, criar prontuarios, historico, prescricoes e exames.
- **AI**: solicitar analises e consultar status/resultados.
- **Reporting**: gerar e baixar relatorios.
- **Gateway e Observabilidade**: validacao de acesso, saude, metricas e logs.

---

## 5. Conclusao

O diagrama consolida a visao de negocio do PROMPTUARIO Backend e mostra como os perfis de usuario interagem com os modulos principais do sistema distribuido.
