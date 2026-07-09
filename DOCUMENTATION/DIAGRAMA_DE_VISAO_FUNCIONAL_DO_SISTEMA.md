# Visao funcional do sistema

Este diagrama consolida a visao funcional do PROMPTUARIO Backend a partir dos atores de negocio, dos modulos de dominio e dos fluxos principais de uso.

```mermaid
flowchart LR
    subgraph ATORES["Atores"]
        PACIENTE["Paciente"]
        MEDICO["Medico"]
        ATENDENTE["Atendente"]
        ADMIN["Administrador"]
        OPERADOR["Operador"]
    end

    subgraph ACESSO["Camada de acesso"]
        PORTAL["Portal / Frontend"]
        GATEWAY["API Gateway"]
    end

    subgraph IDENTIDADE["Identidade e autorizacao"]
        IAM["IAM Service\nLogin, refresh, logout, usuarios e roles"]
    end

    subgraph ASSISTENCIA["Atencao ao paciente"]
        PATIENT["Patient Service\nCadastro, dados demograficos, historico e dados clinicos basicos"]
        CLINICAL["Clinical Service\nAgenda, consultas, prontuarios, prescricoes e exames"]
    end

    subgraph INTELIGENCIA["Automacao e analise"]
        AI["AI Service\nAnalises assicronas e processamento inteligente"]
        REPORTING["Reporting Service\nRelatorios, exportacoes e consultas gerenciais"]
    end

    subgraph SUPORTE["Suporte operacional"]
        OBS["Observabilidade\nLogs, metricas, traces e alertas"]
    end

    PACIENTE --> PORTAL
    MEDICO --> PORTAL
    ATENDENTE --> PORTAL
    ADMIN --> PORTAL
    OPERADOR --> PORTAL

    PORTAL --> GATEWAY

    GATEWAY --> IAM
    GATEWAY --> PATIENT
    GATEWAY --> CLINICAL
    GATEWAY --> AI
    GATEWAY --> REPORTING

    IAM -->|autenticacao e autorizacao| GATEWAY
    PATIENT -->|dados do paciente para atendimento| CLINICAL
    CLINICAL -->|solicitacoes de analise| AI
    CLINICAL -->|dados consolidados e eventos de negocio| REPORTING
    AI -->|resultados analiticos| REPORTING

    IAM -.-> OBS
    PATIENT -.-> OBS
    CLINICAL -.-> OBS
    AI -.-> OBS
    REPORTING -.-> OBS
    GATEWAY -.-> OBS
```

## Leitura da visao

- Os atores acessam o sistema pelo portal, que centraliza as interacoes com o Gateway.
- O Gateway distribui as requisicoes para os servicos funcionais adequados.
- O IAM controla identidade, autenticacao e autorizacao.
- O Patient Service organiza o cadastro e o contexto basico do paciente.
- O Clinical Service concentra o fluxo assistencial principal, incluindo agenda, prontuario, prescricao e exames.
- O AI Service executa analises assincronas quando ha processamento adicional.
- O Reporting Service consolida informacoes para relatorios e exportacoes.
- A observabilidade acompanha toda a operacao da plataforma.

## Relacao com a documentacao existente

Este diagrama complementa o documento de [casos de uso](DIAGRAMA_DE_CASOS_DE_USO.md) e a [arquitetura de software](ARQUITETURA_DE_SOFTWARE.md), mantendo a mesma divisao por dominios do sistema.