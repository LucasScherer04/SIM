# Provedores de Dados de Mercado, Câmbio e Notícias — Etapa 3

**Data:** 06/11/2026  
**Escopo:** documentação técnica e operacional das integrações externas do SIM para mercados do Brasil e dos Estados Unidos, câmbio BRL/USD, indicadores macroeconômicos e notícias.

---

## 1. Princípios Operacionais

1. **Não presumir tempo real nem disponibilidade contínua:** todas as fontes gratuitas possuem atraso (15–20 minutos ou fechamento diário), limites de requisição por IP e podem falhar sem aviso.
2. **Cache local obrigatório em SQLite:** toda cotação, série histórica, indicador macro e lista de notícias bem-sucedida é gravada localmente com `source` (origem), `fetched_at` (data/hora da coleta) e `data_state` (`LIVE`, `CACHED`, `CATALOG` ou `UNAVAILABLE`).
3. **Degradação elegante (offline-first):** falhas de rede ou bloqueios de provedores nunca interrompem a consulta da carteira nem o carregamento da tela do ativo; o SIM exibe o último dado armazenado em cache identificando claramente a data da última atualização.
4. **Proibição de dados sintéticos:** quando não há rede nem cache local, o SIM informa que o dado está indisponível — nunca gera preços, gráficos ou manchetes fictícias.

---

## 2. Inventário e Especificação dos Provedores

### 2.1 Cotações e Séries Históricas — Brasil (B3) e Estados Unidos (NYSE / NASDAQ)

| Atributo | Especificação |
|---|---|
| **Provedor principal** | Yahoo Finance (via biblioteca `yfinance` / HTTP) |
| **Adaptador no SIM** | `YahooFinanceAdapter` (`app/market_adapters.py`) |
| **Cobertura Brasil** | Ações (`ACAO_BR`), Fundos Imobiliários (`FII`), ETFs e BDRs (`ETF_BR`) listados na B3 usando sufixo `.SA` (ex.: `PETR4.SA`, `HGLG11.SA`, `BOVA11.SA`) e índice Ibovespa (`^BVSP`). |
| **Cobertura EUA** | Stocks, REITs e ETFs listados na NYSE/NASDAQ usando ticker direto em USD (ex.: `AAPL`, `MSFT`, `NVDA`, `VOO`) e índice S&P 500 (`^GSPC`). |
| **Campos utilizados** | `Close` (preço de fechamento/último negócio), `Volume` (volume negociado), série histórica por intervalo (`1D`, `5D`, `1M`, `6M`, `1Y`, `5Y`, `10Y`, `MAX`) e histórico de dividendos (`dividends`). |
| **Moeda retornada** | `BRL` para ativos `.SA`; `USD` para ativos listados nos EUA. |
| **Autenticação** | Nenhuma (acesso público por IP). |
| **Custo** | Gratuito para consulta pessoal. |
| **Limites e atraso** | Atraso típico de 15 a 20 minutos durante o pregão; sujeito a *rate limiting* por IP (~2.000 requisições/hora). No SIM, a sincronização em lote respeita intervalo mínimo de 90 segundos e o cache de gráfico evita chamadas repetidas. |
| **Termos de uso** | Uso exclusivamente pessoal, local e informativo; vedada redistribuição comercial. Sem garantia de SLA. |

### 2.2 Criptoativos (Cobertura Complementar)

| Atributo | Especificação |
|---|---|
| **Provedor de cotação** | Binance Public API (`https://api.binance.com/api/v3/ticker/24hr`) |
| **Provedor de histórico** | Yahoo Finance (`BTC-USD`, `ETH-USD`, `SOL-USD`) |
| **Campos utilizados** | `lastPrice`, `priceChangePercent`, `quoteVolume` (em `USDT`/`USD`). |
| **Autenticação / Custo** | Pública sem chave / Gratuito. |
| **Limites** | Limite por peso de IP da Binance; timeout configurado em 4 segundos. |

### 2.3 Câmbio BRL/USD e Indicadores Macroeconômicos

| Indicador | Provedor Primário | Provedor de Contingência (Fallback) | Campos e Série | Autenticação / Custo / Limites |
|---|---|---|---|---|
| **Câmbio USD/BRL e EUR/BRL** | **AwesomeAPI** (`https://economia.awesomeapi.com.br/last/USD-BRL,EUR-BRL,BTC-USD`) | **Banco Central do Brasil — SGS Série 1** (Dólar PTAX venda: `https://api.bcb.gov.br/dados/serie/bcdata.sgs.1/dados/ultimos/1?formato=json`) | `bid` / `pctChange` (AwesomeAPI) ou `valor` / `data` (BCB PTAX) | Pública, gratuita. AwesomeAPI tem limite de cortesia por IP; BCB SGS é serviço público oficial sem chave. |
| **Taxa Selic Meta (% a.a.)** | **BCB SGS Série 432** (`.../bcdata.sgs.432/dados/ultimos/1?formato=json`) | Cache persistente em `macro_indicators_cache` | `valor` (% a.a.) e `data` | Pública, gratuita, fonte oficial do Banco Central. |
| **Taxa CDI (% a.a.)** | **BCB SGS Série 4389** (`.../bcdata.sgs.4389/dados/ultimos/1?formato=json`) | Estimativa `Selic − 0,10 p.p.` (identificada como estimada) + cache local | `valor` (% a.a.) | Pública, gratuita, fonte oficial do Banco Central. |
| **IPCA acumulado 12 meses (%)** | **BCB SGS Série 13522** (`.../bcdata.sgs.13522/dados/ultimos/1?formato=json`) | Cache persistente em `macro_indicators_cache` | `valor` (% acum. 12m) | Pública, gratuita, fonte oficial do Banco Central. |

### 2.4 Notícias de Mercado e de Ativos (Brasil e EUA)

| Atributo | Especificação |
|---|---|
| **Provedor** | Google News RSS (`https://news.google.com/rss/search`) via `feedparser` |
| **Adaptador no SIM** | `GoogleNewsRssAdapter` (`app/market_adapters.py`) |
| **Cobertura Brasil** | Parâmetros `hl=pt-BR&gl=BR&ceid=BR:pt-419`, consulta por ticker + nome da empresa/fundo + contexto B3 nos últimos 90 dias. |
| **Cobertura EUA** | Consulta para ativos `STOCK_US` em português/inglês com contexto NYSE/NASDAQ (`stock market`). |
| **Campos extraídos** | `title` (título limpo), `source` (veículo original), `published` e `published_iso` (data/hora de publicação), `link` (URL da matéria), `summary` (resumo textual limpo do RSS quando presente) e `sentiment` (heurística léxica local, rotulada como cálculo do SIM). |
| **Autenticação / Custo** | Pública sem chave / Gratuito. |
| **Limites e termos** | Sujeito a bloqueio temporário se consultado em alta frequência; o SIM armazena cache persistente em `asset_news_cache` (TTL de 15 minutos em uso normal e fallback ilimitado quando offline). Uso pessoal para leitura dos links originais. |

### 2.5 Documentos Regulatórios Oficiais (Brasil)

| Fonte | Cobertura | Observações |
|---|---|---|
| **B3 Fundos.NET** (`fnet.bmfbovespa.com.br`) | Relatórios gerenciais e fatos relevantes de FIIs | Consulta pública por CNPJ do fundo. |
| **CVM RAD / Dados Abertos** (`dados.cvm.gov.br`) | Comunicados, fatos relevantes e ITR/DFP de companhias abertas | Índice IPE em cache local por 12 horas. |

---

## 3. Estrutura de Cache e Estado do Dado no SQLite

| Tabela | Chave Primária | Conteúdo | Comportamento em Falha Externa |
|---|---|---|---|
| `assets_catalog` | `ticker` | Último preço, variação diária, múltiplos, `quote_source` e `updated_at`. | Mantém última cotação conhecida; `is_stale=True` se `updated_at` > 24h ou vazio. |
| `market_history_cache` | `(ticker, period)` | Série histórica JSON (`points_json`), `source`, `currency`, `fetched_at`. | Retorna a série armazenada com `data_state="CACHED"` e data da coleta. Se inexistente, retorna `points=[]` e `data_state="UNAVAILABLE"`. |
| `asset_news_cache` | `ticker` | Lista de notícias JSON (`items_json`), `source`, `fetched_at`. | Retorna notícias armazenadas com `data_state="CACHED"`. Se inexistente, retorna lista vazia (`[]`). |
| `macro_indicators_cache` | `key` | Valor (`value`), variação (`change_pct`), `source`, `fetched_at`. | Carrega na inicialização e em falhas de rede, preservando a última taxa real de câmbio/juros/inflação. |
