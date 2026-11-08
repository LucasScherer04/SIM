# SIM — Scherer Investments Money

> **Sobre a Iniciativa:** O **SIM** é uma iniciativa pessoal idealizada para **explorar os limites da Inteligência Artificial aplicada à engenharia de software e geração de código**. Todo o sistema — da especificação arquitetural, regras contábeis multimercado e integrações de dados financeiros até a bateria de testes automatizados — foi desenvolvido como um laboratório prático de até onde agentes de IA conseguem construir, auditar e evoluir um software financeiro complexo e real.

---

## O que é o SIM?

O **SIM (Scherer Investments Money)** é uma plataforma local (*local-first*) para Windows voltada à **gestão patrimonial, consolidação de carteira de investimentos (Brasil e Estados Unidos), monitoramento de mercado ao vivo e análise de ativos assistida por IA**.

Diferente de planilhas estáticas ou plataformas em nuvem fechadas, o SIM mantém 100% dos seus dados financeiros no seu próprio computador (banco SQLite local), combinando precisão contábil com coleta automática de cotações, indicadores macroeconômicos, documentos oficiais da B3/CVM e análises estruturadas por IA.

> **Escopo do Projeto:** O SIM é uma ferramenta analítica e de apoio à decisão. Ele **não** é uma corretora, não executa ordens automáticas de compra/venda e não promete retornos financeiros.

---

## Pilares e Ideia Central do Projeto

1. **Privacidade e Autonomia (*Local-First*):**
   Todos os lançamentos, posições, proventos e análises ficam armazenados localmente em SQLite (`sim_database.db`), com sistema integrado de backup e restauração verificado por `PRAGMA integrity_check` e funcionamento offline sobre cache identificado.
2. **Consolidação Multimoeda e Multiclasse Auditável (`BRL` & `USD`):**
   Acompanhamento unificado de Ações B3 (`ACAO_BR`), Fundos Imobiliários (`FII`), ETFs/BDRs (`ETF_BR`), Renda Fixa e Tesouro Direto (`RENDA_FIXA`, `TESOURO`), Stocks e REITs americanos (`STOCK_US`, `ETF_US`), Criptoativos (`CRIPTO`) e Caixa (`CAIXA`), preservando sempre a moeda original do ativo, o custo histórico de aquisição e a taxa de câmbio de referência.
3. **Motor Contábil Real:**
   Cálculo exato de Preço Médio ponderado (incluindo taxas nas compras e preservando o PM nas vendas para apuração de lucro/prejuízo realizado), curva diária de Renda Fixa indexada ao CDI/Selic/IPCA oficiais do Banco Central e consolidação de proventos (*Dividend Yield* e *Yield on Cost*).
4. **Inteligência de Mercado & Leitura de Relatórios Oficiais:**
   Busca automatizada de cotações e séries históricas (`1D`, `5D`, `1M`, `6M`, `1A`, `5A`), notícias em tempo real via RSS e integração direta com o **Fundos.NET (B3) / CVM** para localizar e extrair PDFs de Relatórios Gerenciais de FIIs e Fatos Relevantes (`PyMuPDF`).
5. **Analista de IA Rastreável e Sem "Caixa-Preta":**
   Integração com LLMs (Google Gemini / OpenAI configuráveis via API) desenhada para separar rigorosamente três camadas em cada análise:
   - **Fatos Observados:** dados brutos de mercado, cotações, datas e fontes.
   - **Cálculos do SIM:** métricas determinísticas calculadas pelo código (ex.: peso na carteira, desconto sobre média móvel, concentração Top 5, DY 12m).
   - **Interpretação da IA:** leitura crítica de pontos fortes, riscos, hipóteses de investigação no Radar de Oportunidades e comparação entre análises históricas.

---

## Principais Módulos do Sistema

| Módulo | O que faz |
| :--- | :--- |
| **1. Dashboard Consolidado** | Exibe KPIs patrimoniais em `R$` e `US$`, exposição cambial, alocação por classe, concentração Top 5 ativos, evolução histórica (aportes vs. patrimônio) e comparação com benchmarks (CDI, IPCA, Ibovespa, S&P 500). |
| **2. Gestão de Carteira & B3** | Cadastro de compras, vendas e proventos, cálculo automático de Preço Médio e lucro realizado, conciliação/importação de planilhas da B3 (`.xlsx`/`.csv`) e curva diária de Renda Fixa. |
| **3. Explorador & Raio-X do Ativo** | Painel por classes de ativos com rankings dinâmicos (*Em Alta*, *Em Baixa*, *Maior Dividendo*, *Mais Descontados*) e página exclusiva por ticker com gráfico interativo, linha do seu Preço Médio, histórico de dividendos por cota e documentos B3/CVM. |
| **4. Radar de Oportunidades & Notícias** | Monitoramento de sinais objetivos para investigação (variações atípicas, proximidade de mínimas/máximas de 52 semanas, concentração elevada e notícias relevantes do Brasil e EUA), com gestão de status (*Relevante*, *Em Acompanhamento*, *Ignorado*). |
| **5. Analista de IA & Comparador** | Geração de dossiês de carteira, análise individual de ativos, leitura de PDFs gerenciais de FIIs, comparador lado a lado de ativos do mesmo segmento e histórico evolutivo (*"O que mudou desde a última análise?"*). |
| **6. Segurança, Backup & Resiliência** | Criptografia local para chaves de API, cache SQLite resiliente para operação offline com aviso explícito de idade dos dados e backups locais validados com 1 clique. |

---

## Arquitetura e Stack Tecnológica

- **Backend:** Python 3.11+ com **FastAPI** e **Uvicorn** (`app/main.py`)
- **Banco de Dados:** **SQLite 3** local (`app/database.py`) com cache persistente de mercado e histórico de análises
- **Frontend:** Interface Web *Dark Mode FinTech* responsiva em HTML5/CSS3/JS (`static/`) com **TradingView Lightweight Charts** e **Chart.js**
- **Integrações de Dados (`app/market_adapters.py`):**
  - *Cotações, Histórico e Fundamentos:* Yahoo Finance (`yfinance`) & Brapi
  - *Câmbio e Indicadores Macro (Selic, CDI, IPCA):* AwesomeAPI & API SGS do Banco Central do Brasil
  - *Criptomoedas:* Binance Public API
  - *Documentos Oficiais e Notícias:* B3 Fundos.NET, RAD CVM (`PyMuPDF`) & Google News Finance RSS (`feedparser`)
- **Qualidade e Testes:** Suíte automatizada com `pytest` (`tests/`) cobrindo cálculos contábeis, conciliação B3, adaptadores de mercado, fluxos do analista de IA, backups e testes de ponta a ponta (E2E).

```text
SIM/
├── app/
│   ├── main.py                  # Rotas FastAPI e orquestração da aplicação
│   ├── database.py              # Esquema SQLite, migrações e persistência
│   ├── dashboard_service.py     # Consolidação patrimonial, evolução e concentração
│   ├── market_adapters.py       # Adaptadores (Yahoo Finance, BCB, AwesomeAPI, RSS)
│   ├── market_service.py        # Cotações, séries históricas e cache offline
│   ├── ai_radar_service.py      # Radar de oportunidades, comparador e Analista de IA
│   ├── intelligence_service.py  # Extração de PDFs (Fundos.NET/CVM) e notícias
│   ├── b3_sync_service.py       # Importação, exportação e conciliação B3 (.xlsx/.csv)
│   └── backup_service.py        # Backup e restauração SQLite com integrity_check
├── static/                      # Interface visual (SPA Dark Mode, gráficos e painéis)
├── tests/                       # Testes automatizados de unidade, integração e E2E
├── docs/                        # Manuais técnicos, diagnóstico e guia do usuário
├── Instalar_SIM_Windows.bat     # Instalador automático e criador de atalho no Windows
└── Iniciar_SIM.bat              # Script de inicialização rápida local
```

---

## Como Instalar e Executar no Windows

1. Certifique-se de ter o **Python 3.11+** instalado no Windows.
2. Dê um duplo clique em **`Instalar_SIM_Windows.bat`**:
   - Cria um backup preventivo caso já exista banco local;
   - Instala todas as dependências do `requirements.txt`;
   - Cria o atalho **SIM - Investimentos** na sua Área de Trabalho.
3. Inicie o sistema pelo atalho na Área de Trabalho (**`Iniciar_SIM_Silencioso.vbs`**, que abre direto no navegador sem janela de terminal) ou executando **`Iniciar_SIM.bat`**.
4. Para rodar a suíte de testes automatizados via terminal:
   ```powershell
   pytest -q
   ```

---

## Documentação Complementar

- [**Manual Completo de Uso, Backup e Configuração de IA (`docs/manual-uso-sim.md`)**](docs/manual-uso-sim.md)
- [**Provedores de Dados de Mercado, Limites e Cache (`docs/provedores-mercado.md`)**](docs/provedores-mercado.md)
- [**Diagnóstico Técnico e Regras Financeiras (`docs/diagnostico-sim.md`)**](docs/diagnostico-sim.md)
- [**Especificação Funcional Completa (`specification.md`)**](specification.md)
- [**Plano de Execução e Arquitetura Enxuta (`SIM_PLANO_ENXUTO.md`)**](SIM_PLANO_ENXUTO.md)
