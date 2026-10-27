# SIM — Scherer Investments Money
## Especificação Técnica e Funcional Completa (v1.0 - Draft Inicial)

> **Propósito do Documento:** Definir de ponta a ponta todos os módulos, regras de negócio, cálculos financeiros, integrações de dados ao vivo, telas e estrutura de dados do **SIM (Scherer Investments Money)** antes do início da implementação.

---

## 1. Visão Geral do Produto

O **SIM (Scherer Investments Money)** é uma plataforma pessoal de gestão patrimonial, consolidação de carteira de investimentos e acompanhamento em tempo real do mercado financeiro brasileiro e global.

### Princípios do Sistema
1. **Privacidade Total (Local-First):** Todos os dados de patrimônio, transações e proventos ficam armazenados localmente no computador do usuário (SQLite + backups automáticos exportáveis em JSON/CSV/Excel).
2. **Dados de Mercado Ao Vivo:** Integração direta com APIs públicas e gratuitas para atualização automática de preços de ativos e indicadores macroeconômicos.
3. **Precisão Contábil e Fiscal:** Cálculo exato de Preço Médio ajustado, rentabilidade ponderada pelo tempo (TWR / cota da carteira), Dividend Yield (*DY* atual e *Yield on Cost*) e regras de apuração de Imposto de Renda (isenções de R$ 20 mil/mês em ações, alíquotas regressivas de Renda Fixa, etc.).
4. **Multimoeda Nativo:** Consolidação automática do patrimônio em **BRL (`R$`)** e **USD (`US$`)** usando a cotação PTAX/Comercial do dólar em tempo real.

---

## 2. Classes de Ativos Suportadas

| Código | Classe de Ativo | Exemplos | Moeda Base | Fonte de Cotação Ao Vivo |
| :--- | :--- | :--- | :---: | :--- |
| **`ACAO_BR`** | Ações Brasileiras (B3) | `PETR4`, `VALE3`, `WEGE3`, `ITUB4` | `BRL` | Yahoo Finance (`*.SA`) / Brapi |
| **`FII`** | Fundos Imobiliários e Fiagros (B3) | `HGLG11`, `MXRF11`, `XPML11`, `KNCR11` | `BRL` | Yahoo Finance (`*.SA`) / Brapi |
| **`ETF_BR`** | ETFs e BDRs listados na B3 | `BOVA11`, `IVVB11`, `AAPL34`, `NVDC34` | `BRL` | Yahoo Finance (`*.SA`) / Brapi |
| **`RENDA_FIXA`** | CDB, LCI, LCA, Debêntures, Caixinhas, Poupança | CDB 110% CDI, LCI 95% CDI, Pós/Pré/IPCA+ | `BRL` | API Séries Temporais do Banco Central (BCB) |
| **`TESOURO`** | Títulos Públicos (Tesouro Direto) | Tesouro Selic, Tesouro IPCA+, Tesouro Prefixado | `BRL` | API Banco Central (BCB) / Tesouro Transparente |
| **`STOCK_US`** | Ações Americanas (NYSE / NASDAQ) | `NVDA`, `AAPL`, `MSFT`, `AMZN`, `GOOGL` | `USD` | Yahoo Finance |
| **`ETF_US`** | ETFs e REITs Americanos | `VOO`, `QQQ`, `VNQ`, `SCHD`, `TLT` | `USD` | Yahoo Finance |
| **`CRIPTO`** | Criptomoedas e Stablecoins | `BTC`, `ETH`, `SOL`, `USDT`, `USDC` | `USD` / `BRL` | Binance API / WebSocket (tempo real) & CoinGecko |
| **`FUNDO_INV`** | Fundos de Investimento (Multimercado/Ações/RF) | Fundos com CNPJ na CVM | `BRL` | Dados diários de cota CVM / Manual |
| **`CAIXA`** | Saldo em Conta Corrente / Reserva / Câmbio | Conta em R$, Conta Global em US$ / EUR | `BRL` / `USD` / `EUR` | Cotação PTAX / Comercial (BCB / AwesomeAPI) |

---

## 3. Tabela Descritiva Geral de Funcionalidades (Master Feature Matrix)

Esta é a tabela mestre do **SIM**, detalhando cada funcionalidade, módulo, regras de negócio, entradas, saídas e prioridade sugerida:

| ID | Módulo | Funcionalidade | Descrição Detalhada e Regras de Negócio | Entradas / Fontes de Dados | Saídas / Visualização na Interface | Prioridade |
| :---: | :--- | :--- | :--- | :--- | :--- | :---: |
| **F01** | **1. Dashboard Consolidado** | **Cards de Resumo Patrimonial (KPIs)** | Exibe no topo da tela: 1) Patrimônio Bruto e Líquido Total (`R$` e `US$`), 2) Valor Total Investido (Custo de Aquisição), 3) Lucro/Prejuízo Latente (`R$` e `%`), 4) Variação do Dia (`R$` e `%`), 5) Proventos Acumulados (no mês, no ano e total). | Posições ativas + Preços ao vivo + Câmbio `USD/BRL` | 5 Cards de destaque com indicadores visuais verdes/vermelhos e modo privacidade (botão "olho" para ocultar valores em R$). | **P0 (Essencial)** |
| **F02** | **1. Dashboard Consolidado** | **Gráfico de Alocação por Classe e Subclasse** | Gráfico de rosca (*Donut Chart*) interativo mostrando o percentual e valor de cada classe de ativo (`Ações BR`, `FIIs`, `Renda Fixa`, `Exterior`, `Cripto`, `Caixa`). Ao clicar em uma fatia, abre o *drill-down* mostrando o peso de cada ativo dentro daquela classe. | Posições consolidadas em `BRL` | Gráfico interativo + Tabela lateral com `% Atual` vs `% Meta`. | **P0 (Essencial)** |
| **F03** | **1. Dashboard Consolidado** | **Evolução Patrimonial Histórica** | Gráfico de área/barras empilhadas mostrando o crescimento do patrimônio mês a mês, separando claramente o que veio de **Novos Aportes (dinheiro do bolso)** vs. **Rendimentos/Valorização de Mercado**. | Histórico de aportes + snapshots diários/mensais da carteira | Gráfico temporal com filtros (`1M`, `6M`, `YTD`, `1A`, `5A`, `Máx`). | **P0 (Essencial)** |
| **F04** | **1. Dashboard Consolidado** | **Rentabilidade Comparada (Carteira vs. Benchmarks)** | Calcula a rentabilidade da carteira pelo método de **Cota (Time-Weighted Return - TWR)** — para que novos aportes não distorçam o percentual de ganho — e plota em gráfico de linha contra **CDI**, **IPCA**, **Ibovespa (`^BVSP`)**, **S&P 500 (`^GSPC`)** e **Bitcoin**. | Cota diária da carteira + Séries históricas do BCB e Yahoo Finance | Gráfico comparativo de linhas em `%` acumulado no período selecionado. | **P0 (Essencial)** |
| **F05** | **2. Mercado Ao Vivo** | **Ticker Tape e Painel Macroeconômico** | Barra superior ou painel em tempo real com: **Ibovespa**, **S&P 500**, **Nasdaq**, **Dólar Comercial (`USD/BRL`)**, **Euro (`EUR/BRL`)**, **Bitcoin (`BTC/USD` e `BTC/BRL`)**, **Taxa Selic Meta**, **CDI Atual** e **IPCA 12 meses**. | Binance WebSocket + AwesomeAPI + API BCB + Yahoo Finance | Barra dinâmica no topo + Painel de Indicadores Macroeconômicos. | **P0 (Essencial)** |
| **F06** | **2. Mercado Ao Vivo** | **Gráficos Interativos de Ativos (Candlestick / Linha)** | Visualização de gráfico de velas (*Candlestick*) ou linha para qualquer ativo da carteira ou da *Watchlist*, com indicadores básicos (Médias Móveis `MM9`, `MM21`, `MM200`, Volume e linha horizontal marcando o **seu Preço Médio** no gráfico!). | OHLCV histórico e intraday (Yahoo Finance / Binance) | Gráfico interativo estilo TradingView (Lightweight Charts) com marcação visual do seu Preço Médio. | **P1 (Alta)** |
| **F07** | **2. Mercado Ao Vivo** | **Watchlist (Lista de Observação) e Alertas de Preço** | Permite cadastrar ativos que você ainda não comprou (ou quer comprar mais) e definir **Preço Alvo de Compra** e **Preço Alvo de Venda**. Quando a cotação ao vivo atingir o alvo, destaca na tela e emite notificação no Windows. | Ticker + Preço Alvo Mín/Máx + Cotação Ao Vivo | Tabela de Watchlist com barra de proximidade do preço-alvo + Notificação. | **P1 (Alta)** |
| **F08** | **2. Mercado Ao Vivo** | **Indicadores Fundamentalistas Rápidos** | Para Ações BR e FIIs, exibe indicadores fundamentais ao lado da cotação: `P/L` (Preço/Lucro), `P/VP` (Preço/Valor Patrimonial), `Dividend Yield (12m)`, `ROE`, `Margem Líquida`, `Máxima/Mínima 52 semanas`. | Yahoo Finance / Brapi / Fundamentus | Ficha resumo do ativo ao clicar em qualquer ticker da carteira. | **P2 (Média)** |
| **F09** | **3. Gestão de Carteira e Ordens** | **Lançamento de Operações (Compra e Venda)** | Registro de compras e vendas com: Data, Ticker, Classe, Corretora/Instituição, Quantidade (suporta frações de até 8 casas decimais para Cripto e Stocks), Preço Unitário, Taxas/Corretagem/Emolumentos e Moeda (`BRL`/`USD`) com câmbio da data. | Formulário de lançamento ou importação CSV/Nota de Corretagem | Histórico de ordens auditável e recálculo instantâneo da posição. | **P0 (Essencial)** |
| **F10** | **3. Gestão de Carteira e Ordens** | **Motor de Cálculo de Preço Médio (PM) e Lucro Realizado** | Regra oficial brasileira: **Compras** recalculam o Preço Médio ponderado incluindo taxas ($\text{PM}_{\text{novo}} = \frac{\text{Qtd}_{\text{atual}} \times \text{PM}_{\text{atual}} + \text{Qtd}_{\text{compra}} \times \text{Preço} + \text{Taxas}}{\text{Qtd}_{\text{total}}}$). **Vendas** NÃO alteram o Preço Médio; apenas reduzem a quantidade e apuram o **Lucro/Prejuízo Realizado**. | Lançamentos de compra, venda, bonificações e eventos corporativos | Tabela de posições mostrando `Qtd`, `PM`, `Preço Atual`, `Custo Total`, `Saldo Atual`, `Lucro Latente` e `Lucro Realizado`. | **P0 (Essencial)** |
| **F11** | **3. Gestão de Carteira e Ordens** | **Eventos Corporativos (Desdobramento, Grupamento e Bonificação)** | Permite registrar *Splits* (ex: 1 para 4), *Inplits* (grupamentos) e Bonificações em ações com custo atribuído, ajustando automaticamente a quantidade e o Preço Médio histórico sem precisar editar compras antigas. | Fator de proporção + Data com + Custo unitário (em bonificação) | Ajuste automático do histórico e do PM da posição. | **P2 (Média)** |
| **F12** | **3. Gestão de Carteira e Ordens** | **Múltiplas Carteiras / Corretoras** | Permite filtrar ou separar ativos por **Corretora/Banco** (ex: XP, BTG, Nubank, Inter, Binance, Avenue) e por **Objetivo/Subcarteira** (ex: "Reserva de Emergência", "Aposentadoria", "Curto Prazo"). | Cadastro de Instituições e Tags de Carteira | Filtro global no topo do app para ver tudo consolidado ou apenas uma corretora/objetivo. | **P1 (Alta)** |
| **F13** | **4. Módulo de Renda Fixa** | **Motor de Curva de Renda Fixa (CDI, Selic, IPCA+ e Pré)** | Calcula o saldo atualizado diariamente de títulos de Renda Fixa sem precisar digitar o valor na mão: 1) **Pós-fixado (`% do CDI` ou `CDI + taxa`)** usando a série diária oficial do CDI do Banco Central (SGS série `12`), 2) **IPCA+ (`IPCA + taxa% a.a.`)**, 3) **Prefixado (`taxa% a.a.`)** considerando 252 dias úteis. | Valor aplicado, Data de aplicação, Vencimento, Indexador (`CDI`, `IPCA`, `SELIC`, `PRE`), Taxa contratada, Liquidez e Isenção de IR (LCI/LCA vs CDB) | Saldo Bruto atualizado até hoje, Alíquota atual da Tabela Regressiva de IR (`22,5%` a `15%`), IOF (se < 30 dias) e **Saldo Líquido de Resgate**. | **P0 (Essencial)** |
| **F14** | **4. Módulo de Renda Fixa** | **Controle de Vencimentos e Liquidez** | Painel mostrando quanto do seu dinheiro tem **Liquidez Diária** (disponível hoje) vs. **No Vencimento**, com alerta de títulos próximos do vencimento. | Títulos de Renda Fixa e Tesouro cadastrados | Linha do tempo de vencimentos e gráfico de liquidez (`D+0`, `D+30`, `> 1 ano`). | **P1 (Alta)** |
| **F15** | **5. Dividendos e Proventos** | **Mapa de Proventos (Dividendos, JCP, Rendimentos de FIIs)** | Registro e acompanhamento de proventos recebidos e "A Receber" (provisionados). Calcula automaticamente: **Média Mensal de Renda Passiva**, **Dividend Yield da Carteira (%)** e **Yield on Cost (YoC %)** de cada ativo (quanto o ativo paga de dividendo sobre o preço que *você* pagou nele). | Histórico de proventos (Automático via histórico de dividendos do ativo nas datas em que você tinha posição + ajuste manual) | Gráfico de barras de renda passiva mensal ("Escadinha de Dividendos") + Tabela de Yield on Cost por ativo. | **P1 (Alta)** |
| **F16** | **6. Rebalanceamento Inteligente** | **Calculadora de Novo Aporte ("Onde aportar hoje?")** | Você define a **Alocação Meta (%)** para cada classe de ativo e uma **Nota / Peso Meta** para cada ativo dentro da classe. Ao digitar *"Quero investir R$ 2.000,00 hoje"*, o SIM calcula exatamente quais ativos estão mais descontados/atrasados na sua carteira e quanto comprar de cada um para equilibrar o portfólio sem precisar vender nada. | Pesos/Metas definidos pelo usuário + Posição atual + Valor em R$ do novo aporte | Lista de compras sugeridas (`Ticker`, `Quantidade a comprar`, `Valor em R$`, `% antes -> % depois`). | **P1 (Alta)** |
| **F17** | **7. Metas e Independência Financeira** | **Simulador de Liberdade Financeira (F.I.R.E.) e Metas** | Acompanhamento de metas (ex: "1º R$ 100 mil", "Reserva de 6 meses", "Renda passiva de R$ 5.000/mês"). Inclui projetor de juros compostos mostrando em que data você atingirá a meta mantendo seu aporte mensal atual. | Patrimônio atual + Aporte médio mensal + Taxa real estimada | Barras de progresso de metas + Gráfico de projeção futura. | **P2 (Média)** |
| **F18** | **8. Apoio Fiscal (IRPF)** | **Relatório Auxiliar de Imposto de Renda e Isenções** | Consolida: 1) Total de vendas de Ações BR no mês (alertando se está abaixo do limite de isenção de **R$ 20.000,00/mês**), 2) Lucro tributável em FIIs, ETFs, BDRs e Swing/Day Trade com compensação de prejuízos acumulados, 3) Relatório anual de "Bens e Direitos" pronto para copiar e colar no programa da Receita Federal (com CNPJ da empresa, quantidade e custo total em 31/12). | Todas as operações de compra/venda e posições em 31/12 de cada ano | Tela de resumo mensal de isenção (termômetro dos R$ 20 mil) + Tabela "Bens e Direitos" pronta para o IRPF. | **P2 (Média)** |
| **F19** | **9. Sistema e Dados** | **Importação / Exportação e Backup Local** | Permite exportar e importar todas as transações em **CSV / Excel (`.xlsx`)** e fazer backup/restauração do banco de dados SQLite com um clique. | Banco de dados local SQLite | Botões de Exportar Excel/CSV e Backup instantâneo. | **P1 (Alta)** |

---

## 4. Fontes de Dados e APIs Gratuitas (Arquitetura de Integração)

Para que o **SIM** funcione 100% gratuito e sem depender de assinaturas pagas, utilizaremos um motor híbrido de coleta de dados com cache inteligente:

| Tipo de Dado | Fonte Primária (Gratuita) | Fonte Secundária (Fallback) | Frequência de Atualização |
| :--- | :--- | :--- | :--- |
| **Ações B3, FIIs, ETFs, BDRs** | **Yahoo Finance (`yfinance`)** — sufixo `.SA` | **Brapi API** (`brapi.dev`) | A cada 1 a 5 min (ou botão "Atualizar Agora") |
| **Stocks EUA, REITs, Índices Globais** | **Yahoo Finance (`yfinance`)** | — | A cada 1 min |
| **Criptomoedas (`BTC`, `ETH`, `SOL`, etc.)** | **Binance Public API / WebSocket** | **CoinGecko API** | **Tempo Real (1s - 5s)** |
| **Dólar (`USD/BRL`) e Euro (`EUR/BRL`)** | **AwesomeAPI** (`economia.awesomeapi.com.br`) | **Yahoo Finance (`USDBRL=X`) / BCB PTAX** | A cada 30 segundos |
| **CDI, Taxa Selic e IPCA Oficiais** | **API do Banco Central do Brasil (SGS/BCB)**<br>• Selic Meta: Série `432`<br>• CDI Diário: Série `12`<br>• CDI Anualizado: Série `4389`<br>• IPCA Mensal: Série `433` | Cache local da última taxa oficial | Ao abrir o app / Diário |

---

## 5. Arquitetura Técnica Proposta

* **Linguagem / Backend:** **Python 3.12** com **FastAPI** (alta velocidade, suporte assíncrono para buscar cotações em paralelo e WebSockets para preços em tempo real).
* **Banco de Dados:** **SQLite 3** local (`sim_database.db`), rápido, seguro, sem necessidade de instalar servidores pesados de banco de dados.
* **Frontend / Interface Visual:** Interface Web Moderna *Dark Mode FinTech* (HTML5 + Tailwind CSS + **TradingView Lightweight Charts** para gráficos financeiros + **Chart.js / ApexCharts** para gráficos de carteira), rodando localmente e acessível via atalho dedicado na Área de Trabalho (em janela estilo aplicativo nativo via `--app` do navegador).

---

## 6. Pontos em Aberto para Decisão (Próximo Passo)

Antes de começarmos a programar, revise a tabela acima e defina:
1. **Quais módulos/funcionalidades você quer alterar, remover ou adicionar?**
2. **Como você organiza seus investimentos hoje?** (Ex: planilha Excel, app de corretora, ou ainda vai cadastrar do zero?)
3. **Na Renda Fixa:** Você usa mais **Caixinhas/CDBs em % do CDI** (ex: Nubank, Inter, bancos), **Tesouro Direto**, ou ambos?
4. **Quer incluir controle de gastos pessoais/fluxo de caixa mensal** (Receitas vs. Despesas para saber quanto sobra para aportar), ou quer que o **SIM** seja **100% focado apenas em Investimentos e Patrimônio**?
