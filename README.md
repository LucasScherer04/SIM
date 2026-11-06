# SIM — Scherer Investments Money

Aplicação local para Windows de acompanhamento de carteira de investimentos (Brasil e EUA), análise de ativos, radar de mercado e analista de IA auditável.

## Principais Recursos

- **Gestão Completa de Carteira (BRL & USD):** ações B3, FIIs, ETFs, BDRs, Stocks/REITs/ETFs nos EUA, Criptoativos e Renda Fixa / Tesouro Direto, com separação explícita entre moeda original (`BRL` / `USD`) e câmbio referenciado.
- **Dashboard Auditável e Relatórios:** consolidação patrimonial, exposição cambial, concentração Top 5, evolução histórica, proventos por período e importação/exportação B3 (`.xlsx` e `.csv`).
- **Dados Reais de Mercado com Cache Resiliente:** cotações e histórico via Yahoo Finance (`yfinance`), câmbio e indicadores macro via AwesomeAPI / Banco Central do Brasil (SGS) e notícias reais via Google News RSS, com funcionamento offline sobre cache SQLite identificado.
- **Radar & Analista de IA Rastreável:** análises estruturadas de carteira, ativos e comparação de pares separando **fatos observados**, **cálculos do SIM** e **interpretação**, com histórico persistente e comparação de evolução entre análises.
- **Backup e Restauração Verificados:** criação e restauração de backups SQLite validados com `PRAGMA integrity_check` diretamente pela interface.

## Como Instalar e Iniciar no Windows

1. Certifique-se de ter o **Python 3.11+** instalado no Windows.
2. Execute **`Instalar_SIM_Windows.bat`** (cria backup preventivo, instala dependências e adiciona o atalho **SIM - Investimentos** na Área de Trabalho).
3. Abra o SIM pelo atalho na Área de Trabalho (**`Iniciar_SIM_Silencioso.vbs`**, sem janela de terminal) ou por **`Iniciar_SIM.bat`**.

## Documentação

- [**Manual Completo de Uso, Backup e Configuração de IA (`docs/manual-uso-sim.md`)**](docs/manual-uso-sim.md)
- [**Provedores de Dados de Mercado, Limites e Cache (`docs/provedores-mercado.md`)**](docs/provedores-mercado.md)
- [**Diagnóstico Técnico e Regras Financeiras (`docs/diagnostico-sim.md`)**](docs/diagnostico-sim.md)
- [**Plano de Execução (`SIM_PLANO_ENXUTO.md`)**](SIM_PLANO_ENXUTO.md)
