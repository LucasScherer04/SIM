# SIM — Scherer Investments Money
## Especificação Técnica e Funcional Completa (v1.1)

> **Propósito do Documento:** Definir de ponta a ponta todos os módulos, regras de negócio, cálculos financeiros, integrações de dados ao vivo, inteligência artificial para leitura de relatórios/notícias, telas e estrutura de dados do **SIM (Scherer Investments Money)** antes do início da implementação.

---

## 1. Visão Geral do Produto

O **SIM (Scherer Investments Money)** é uma plataforma pessoal de gestão patrimonial, consolidação de carteira de investimentos, explorador de mercado ao vivo e análise inteligente de ativos (com leitura automatizada de notícias e relatórios oficiais da B3/CVM).

### Princípios do Sistema
1. **Privacidade Total (Local-First):** Todos os dados de patrimônio, transações e proventos ficam armazenados localmente no computador do usuário (SQLite + backups automáticos exportáveis em JSON/CSV/Excel).
2. **Dados de Mercado Ao Vivo e Explorador por Abas:** Navegação estilo painel financeiro com abas para cada classe de ativo (`Ações`, `FIIs`, `Stocks`, `Cripto`, `ETFs`, `Renda Fixa`) e rankings dinâmicos (*Em Alta*, *Em Baixa*, *Mais Negociados*, *Maior Dividendo*).
3. **Página Exclusiva por Ativo:** Visão profunda de cada Ação ou FII com gráfico interativo de evolução (`1D`, `5D`, `1M`, `6M`, `1A`, `5A`) com *crosshair/tooltip* ao passar o mouse, histórico de dividendos pagos **por cota** e documentos oficiais.
4. **Inteligência Artificial para Notícias e Relatórios (B3 / Fundos.NET):** Busca automática de notícias do ativo e download direto dos **Relatórios Gerenciais de FIIs** e **Fatos Relevantes de Ações** da B3/CVM, com interpretação automática por IA destacando pontos positivos, riscos, vacância e dividendos.
5. **Precisão Contábil, Fiscal e Multimoeda:** Cálculo exato de Preço Médio, rentabilidade por cota (TWR), curva diária do CDI/Selic/IPCA, controle de IRPF e consolidação em **BRL (`R$`)** e **USD (`US$`)**.

---

## 2. Classes de Ativos Suportadas

| Código | Classe de Ativo | Exemplos | Moeda Base | Fonte de Cotação Ao Vivo |
| :--- | :--- | :--- | :---: | :--- |
| **`ACAO_BR`** | Ações Brasileiras (B3) | `PETR4`, `VALE3`, `WEGE3`, `ITUB4`, `BBAS3` | `BRL` | Yahoo Finance (`*.SA`) / Brapi |
| **`FII`** | Fundos Imobiliários e Fiagros (B3) | `HGLG11`, `MXRF11`, `XPML11`, `KNCR11`, `BTLG11` | `BRL` | Yahoo Finance (`*.SA`) / Brapi |
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

Esta é a tabela mestre do **SIM**, detalhando todos os 10 módulos e suas 24 funcionalidades (`F01` a `F24`):

| ID | Módulo | Funcionalidade | Descrição Detalhada e Regras de Negócio | Entradas / Fontes de Dados | Saídas / Visualização na Interface | Prioridade |
| :---: | :--- | :--- | :--- | :--- | :--- | :---: |
| **F01** | **1. Dashboard Consolidado** | **Cards de Resumo Patrimonial (KPIs)** | Exibe no topo da tela: 1) Patrimônio Bruto e Líquido Total (`R$` e `US$`), 2) Valor Total Investido (Custo de Aquisição), 3) Lucro/Prejuízo Latente (`R$` e `%`), 4) Variação do Dia (`R$` e `%`), 5) Proventos Acumulados (no mês, no ano e total). | Posições ativas + Preços ao vivo + Câmbio `USD/BRL` | 5 Cards de destaque com indicadores visuais verdes/vermelhos e modo privacidade (botão "olho" para ocultar valores em R$). | **P0 (Essencial)** |
| **F02** | **1. Dashboard Consolidado** | **Gráfico de Alocação por Classe e Subclasse** | Gráfico de rosca (*Donut Chart*) interativo mostrando o percentual e valor de cada classe de ativo (`Ações BR`, `FIIs`, `Renda Fixa`, `Exterior`, `Cripto`, `Caixa`). Ao clicar em uma fatia, abre o *drill-down* mostrando o peso de cada ativo dentro daquela classe. | Posições consolidadas em `BRL` | Gráfico interativo + Tabela lateral com `% Atual` vs `% Meta`. | **P0 (Essencial)** |
| **F03** | **1. Dashboard Consolidado** | **Evolução Patrimonial Histórica** | Gráfico de área/barras empilhadas mostrando o crescimento do patrimônio mês a mês, separando claramente o que veio de **Novos Aportes (dinheiro do bolso)** vs. **Rendimentos/Valorização de Mercado**. | Histórico de aportes + snapshots diários/mensais da carteira | Gráfico temporal com filtros (`1M`, `6M`, `YTD`, `1A`, `5A`, `Máx`). | **P0 (Essencial)** |
| **F04** | **1. Dashboard Consolidado** | **Rentabilidade Comparada (Carteira vs. Benchmarks)** | Calcula a rentabilidade da carteira pelo método de **Cota (Time-Weighted Return - TWR)** — para que novos aportes não distorçam o percentual de ganho — e plota em gráfico de linha contra **CDI**, **IPCA**, **Ibovespa (`^BVSP`)**, **S&P 500 (`^GSPC`)** e **Bitcoin**. | Cota diária da carteira + Séries históricas do BCB e Yahoo Finance | Gráfico comparativo de linhas em `%` acumulado no período selecionado. | **P0 (Essencial)** |
| **F05** | **2. Explorador de Mercado e Abas por Classe** | **Painel Superior/Lateral com Abas por Classe de Ativo** | Navegação dedicada com abas para cada classe mapeada (**Todas**, **Ações BR**, **FIIs**, **Stocks EUA**, **ETFs/BDRs**, **Cripto**, **Renda Fixa**). Permite alternar entre ver *"Apenas Minha Carteira"* ou *"Mercado Geral (Todos os Ativos da Bolsa)"*. | Catálogo de ativos da B3 / EUA / Cripto + Posições do usuário | Barra de abas fluida com contadores e resumo rápido do setor/classe selecionada. | **P0 (Essencial)** |
| **F06** | **2. Explorador de Mercado e Abas por Classe** | **Ordenação e Filtros Inteligentes (Rankings de Mercado)** | Dentro de cada aba (ex: aba **Ações** ou aba **FIIs**), permite ordenar e filtrar todos os ativos por:<br>• **Em Alta** (Maiores valorizações do dia / semana / mês)<br>• **Em Baixa** (Maiores quedas do dia / semana / mês)<br>• **Mais Comprados / Mais Negociados** (Maior volume financeiro / liquidez diária)<br>• **Maior Dividendo** (Maior *Dividend Yield* 12m ou maior último dividendo por cota)<br>• **Mais Descontados** (Menor `P/VP` para FIIs ou menor `P/L` para Ações). | Cotações intraday, volume negociado, histórico de proventos e múltiplos fundamentalistas | Grid/Cards ou Tabela ordenável em 1 clique com *mini-sparklines* (mini-gráfico de tendência) ao lado de cada ativo. | **P0 (Essencial)** |
| **F07** | **2. Explorador de Mercado e Abas por Classe** | **Ticker Tape e Painel Macroeconômico Ao Vivo** | Barra superior em tempo real com: **Ibovespa**, **S&P 500**, **Nasdaq**, **Dólar Comercial (`USD/BRL`)**, **Euro (`EUR/BRL`)**, **Bitcoin (`BTC/USD` e `BTC/BRL`)**, **Taxa Selic Meta**, **CDI Atual** e **IPCA 12 meses**. | Binance WebSocket + AwesomeAPI + API BCB + Yahoo Finance | Barra dinâmica no topo + Painel de Indicadores Macroeconômicos. | **P0 (Essencial)** |
| **F08** | **2. Explorador de Mercado e Abas por Classe** | **Watchlist (Lista de Observação) e Alertas de Preço** | Permite favoritar ativos que você está monitorando e definir **Preço Alvo de Compra** e **Preço Alvo de Venda**, emitindo destaque visual e alerta quando a cotação atingir o valor desejado. | Ticker + Preço Alvo Mín/Máx + Cotação Ao Vivo | Aba de Favoritos/Watchlist com termômetro de proximidade do preço-alvo. | **P1 (Alta)** |
| **F09** | **3. Página Exclusiva do Ativo (Raio-X)** | **Gráfico Interativo de Evolução com Tooltip / Crosshair** | Ao clicar em qualquer Ação, FII, Cripto ou Stock, abre uma **Página Exclusiva do Ativo**. Contém gráfico interativo (Área/Linha degradê ou Candlestick) com seletores de período: **`1 Dia` (intraday de 5 em 5 min)**, **`5 Dias`**, **`1 Mês`**, **`6 Meses`**, **`1 Ano`**, **`5 Anos`** e **`Máx`**. Ao passar o mouse sobre a linha (*hover*), uma mira (*crosshair*) acompanha o cursor exibindo uma caixinha flutuante com o **Valor Exato (`R$`)**, **Data/Hora** e **Variação (`%` e `R$`)** até aquele ponto, além de uma linha tracejada indicando o **seu Preço Médio** (se você possuir o ativo). | Séries históricas intraday (`5m`, `15m`) e diárias (`1d`) do Yahoo Finance / Binance | Gráfico interativo de alta precisão estilo Google Finance / TradingView com mudança automática de cor (verde se subiu no período selecionado, vermelho se caiu). | **P0 (Essencial)** |
| **F10** | **3. Página Exclusiva do Ativo (Raio-X)** | **Painel de Dividendo por Cota e Histórico de Pagamentos** | Na Página Exclusiva do FII ou Ação, exibe em destaque:<br>1) **Valor do Último Dividendo por Cota** (ex: `R$ 0,11 / cota` ou `R$ 1,25 / ação`),<br>2) **Data Com** (data limite para ter direito) e **Data de Pagamento**,<br>3) **Rendimento Mensal (%)** e **Dividend Yield Acumulado 12 Meses (%)**,<br>4) **Simulador instantâneo na página:** mostra quanto você recebe com suas cotas atuais (ou permite digitar *"E se eu tivesse 500 cotas?"*),<br>5) Gráfico de barras com os proventos pagos por cota nos últimos 12 a 24 meses. | Histórico oficial de dividendos por cota (Yahoo Finance / Brapi / StatusInvest / B3 Fundos.NET) | Card de destaque "Último Rendimento por Cota" + Calendário de Datas Com/Pagamento + Gráfico histórico de dividendos por cota. | **P0 (Essencial)** |
| **F11** | **3. Página Exclusiva do Ativo (Raio-X)** | **Indicadores Fundamentalistas do Ativo** | Exibe os múltiplos essenciais na página do ativo:<br>• **Para FIIs:** `P/VP` (indicando com selo se está com *Ágio* > 1 ou *Desconto* < 1), Valor Patrimonial por Cota (`VPC`), Patrimônio Líquido, Nº de Cotistas, Liquidez Diária e Segmento (Logística, Shopping, Papel/CRI, Híbrido, Fiagro).<br>• **Para Ações:** `P/L`, `P/VP`, `EV/EBITDA`, `ROE`, `Margem Líquida`, `Dívida Líquida/EBITDA`, `LPA`, `VPA` e Setor. | Brapi / Yahoo Finance / Dados Fundamentalistas B3 | Grid de cards de indicadores com dicas explicativas ao passar o mouse em cada sigla. | **P1 (Alta)** |
| **F12** | **4. Inteligência de Mercado (Notícias e Relatórios IA)** | **Central Automática de Notícias por Ativo** | Na Página Exclusiva de cada Ação ou FII (e também em um feed geral da sua carteira), busca automaticamente as últimas notícias do mercado sobre aquele ticker/empresa/fundo em portais financeiros brasileiros e globais, classificando cada manchete com uma tag automática de sentimento (**Positivo**, **Neutro** ou **Negativo**). | Google News Finance RSS (`TICKER` + nome da empresa/fundo), Yahoo Finance News, InfoMoney / MoneyTimes RSS | Lista cronológica de notícias clicáveis com data/hora, fonte, resumo e etiqueta de sentimento. | **P1 (Alta)** |
| **F13** | **4. Inteligência de Mercado (Notícias e Relatórios IA)** | **Busca Automática de Relatórios Gerenciais e Fatos Relevantes (B3 / CVM)** | Integração direta com o sistema público **Fundos.NET da B3 (`fnet.bmfbovespa.com.br`)** e **RAD CVM** para localizar e baixar automaticamente os documentos oficiais divulgados pelo FII ou Empresa:<br>• **Relatórios Gerenciais Mensais (PDF)**<br>• **Fatos Relevantes**<br>• **Avisos aos Cotistas / Acionistas (Anúncio oficial de dividendos)**<br>• **Resultados Trimestrais (ITR / Release de Resultados)**. | API pública do Fundos.NET (B3) e CVM Dados Abertos | Lista dos documentos oficiais lançados pelo fundo/empresa com botão para abrir o PDF original na hora. | **P1 (Alta)** |
| **F14** | **4. Inteligência de Mercado (Notícias e Relatórios IA)** | **Leitor e Intérprete Automático de Relatórios via IA** | Ao clicar em *"Analisar Relatório com IA"* em qualquer Relatório Gerencial de FII ou Fato Relevante de Ação, o sistema extrai o texto e as tabelas do PDF (`PyMuPDF`) e processa via **LLM (Google Gemini API gratuita ou modelo configurável)**, gerando um **Resumo Estruturado Automático**:<br>1) **Resumo Executivo** (o que aconteceu no mês em 4 linhas),<br>2) **Destaques Positivos** (novas locações, aumento de lucro, redução de dívida),<br>3) **Pontos de Atenção / Riscos** (inadimplência, saída de inquilino, queda de receita),<br>4) **Métricas Extraídas do Relatório:** Vacância Física/Financeira, Alavancagem e *Guidance* (projeção da gestão para os próximos dividendos).<br>*(O resumo fica salvo no banco SQLite para leitura instantânea sempre que quiser).* | PDF oficial baixado do Fundos.NET/CVM + Extrator `PyMuPDF` + Prompt especializado de Analista CNPI via API Gemini | Painel "Análise Inteligente do Relatório" dentro da Página Exclusiva do Ativo, com selos de sentimento e métricas-chave mastigadas. | **P1 (Alta)** |
| **F15** | **5. Gestão de Carteira e Ordens** | **Lançamento de Operações (Compra e Venda)** | Registro de compras e vendas com: Data, Ticker, Classe, Corretora/Instituição, Quantidade (suporta frações de até 8 casas decimais para Cripto e Stocks), Preço Unitário, Taxas/Corretagem/Emolumentos e Moeda (`BRL`/`USD`) com câmbio da data. | Formulário de lançamento ou importação CSV/Nota de Corretagem | Histórico de ordens auditável e recálculo instantâneo da posição. | **P0 (Essencial)** |
| **F16** | **5. Gestão de Carteira e Ordens** | **Motor de Cálculo de Preço Médio (PM) e Lucro Realizado** | Regra oficial brasileira: **Compras** recalculam o Preço Médio ponderado incluindo taxas ($\text{PM}_{\text{novo}} = \frac{\text{Qtd}_{\text{atual}} \times \text{PM}_{\text{atual}} + \text{Qtd}_{\text{compra}} \times \text{Preço} + \text{Taxas}}{\text{Qtd}_{\text{total}}}$). **Vendas** NÃO alteram o Preço Médio; apenas reduzem a quantidade e apuram o **Lucro/Prejuízo Realizado**. | Lançamentos de compra, venda, bonificações e eventos corporativos | Tabela de posições mostrando `Qtd`, `PM`, `Preço Atual`, `Custo Total`, `Saldo Atual`, `Lucro Latente` e `Lucro Realizado`. | **P0 (Essencial)** |
| **F17** | **5. Gestão de Carteira e Ordens** | **Eventos Corporativos (Desdobramento, Grupamento e Bonificação)** | Permite registrar *Splits* (ex: 1 para 4), *Inplits* (grupamentos) e Bonificações em ações com custo atribuído, ajustando automaticamente a quantidade e o Preço Médio histórico sem precisar editar compras antigas. | Fator de proporção + Data com + Custo unitário (em bonificação) | Ajuste automático do histórico e do PM da posição. | **P2 (Média)** |
| **F18** | **5. Gestão de Carteira e Ordens** | **Múltiplas Carteiras / Corretoras** | Permite filtrar ou separar ativos por **Corretora/Banco** (ex: XP, BTG, Nubank, Inter, Binance, Avenue) e por **Objetivo/Subcarteira** (ex: "Reserva de Emergência", "Aposentadoria", "Curto Prazo"). | Cadastro de Instituições e Tags de Carteira | Filtro global no topo do app para ver tudo consolidado ou apenas uma corretora/objetivo. | **P1 (Alta)** |
| **F19** | **6. Módulo de Renda Fixa** | **Motor de Curva de Renda Fixa (CDI, Selic, IPCA+ e Pré)** | Calcula o saldo atualizado diariamente de títulos de Renda Fixa sem precisar digitar o valor na mão: 1) **Pós-fixado (`% do CDI` ou `CDI + taxa`)** usando a série diária oficial do CDI do Banco Central (SGS série `12`), 2) **IPCA+ (`IPCA + taxa% a.a.`)**, 3) **Prefixado (`taxa% a.a.`)** considerando 252 dias úteis. | Valor aplicado, Data de aplicação, Vencimento, Indexador (`CDI`, `IPCA`, `SELIC`, `PRE`), Taxa contratada, Liquidez e Isenção de IR (LCI/LCA vs CDB) | Saldo Bruto atualizado até hoje, Alíquota atual da Tabela Regressiva de IR (`22,5%` a `15%`), IOF (se < 30 dias) e **Saldo Líquido de Resgate**. | **P0 (Essencial)** |
| **F20** | **6. Módulo de Renda Fixa** | **Controle de Vencimentos e Liquidez** | Painel mostrando quanto do seu dinheiro tem **Liquidez Diária** (disponível hoje) vs. **No Vencimento**, com alerta de títulos próximos do vencimento. | Títulos de Renda Fixa e Tesouro cadastrados | Linha do tempo de vencimentos e gráfico de liquidez (`D+0`, `D+30`, `> 1 ano`). | **P1 (Alta)** |
| **F21** | **7. Dividendos da Carteira** | **Mapa Consolidado de Proventos e Yield on Cost (YoC)** | Registro e acompanhamento automático de todos os dividendos, JCP e rendimentos de FIIs pagos para a sua carteira. Calcula: **Média Mensal de Renda Passiva**, **Dividend Yield da Carteira (%)** e **Yield on Cost (YoC %)** de cada ativo. | Histórico de proventos por cota cruzado com a quantidade de cotas que você possuía na *Data Com* | Gráfico "Escadinha de Dividendos" mensal/anual + Calendário de próximos recebimentos da carteira. | **P0 (Essencial)** |
| **F22** | **8. Rebalanceamento Inteligente** | **Calculadora de Novo Aporte ("Onde aportar hoje?")** | Você define a **Alocação Meta (%)** para cada classe de ativo e uma **Nota / Peso Meta** para cada ativo dentro da classe. Ao digitar *"Quero investir R$ 2.000,00 hoje"*, o SIM calcula exatamente quais ativos estão mais descontados/atrasados na sua carteira e quanto comprar de cada um. | Pesos/Metas definidos pelo usuário + Posição atual + Valor em R$ do novo aporte | Lista de compras sugeridas (`Ticker`, `Quantidade a comprar`, `Valor em R$`, `% antes -> % depois`). | **P1 (Alta)** |
| **F23** | **9. Metas e Apoio Fiscal** | **Simulador de Liberdade Financeira (F.I.R.E.) e Auxiliar de IRPF** | Acompanhamento de metas patrimoniais e de renda passiva + Consolidação fiscal (termômetro de isenção de vendas de R$ 20.000/mês em Ações BR e relatório anual de "Bens e Direitos" com custo total em 31/12). | Patrimônio atual + Operações de compra/venda | Barras de progresso de metas + Termômetro fiscal mensal + Relatório anual IRPF. | **P2 (Média)** |
| **F24** | **10. Sistema e Dados** | **Importação / Exportação e Backup Local** | Permite exportar e importar todas as transações em **CSV / Excel (`.xlsx`)** e fazer backup/restauração do banco de dados SQLite com um clique. | Banco de dados local SQLite | Botões de Exportar Excel/CSV e Backup instantâneo. | **P1 (Alta)** |

---

## 4. Detalhamento Visual: Como Funcionará a "Página Exclusiva do Ativo" e as "Abas por Classe"

### 4.1. Painel de Abas por Classe + Ordenação Inteligente (`F05` e `F06`)
No topo ou menu lateral do **SIM**, você terá abas rápidas para navegar entre cada universo de ativos:
* `[ Visão Geral ]` `[ Ações BR ]` `[ Fundos Imobiliários (FIIs) ]` `[ Renda Fixa & Tesouro ]` `[ Stocks EUA ]` `[ Criptomoedas ]` `[ ETFs & BDRs ]`

Dentro das abas de renda variável (como **Ações BR** e **FIIs**), você terá pílulas de ordenação instantânea:
* **Em Alta Hoje / Semana / Mês:** Lista os ativos com maior `%` de valorização.
* **Em Baixa Hoje / Semana / Mês:** Lista os ativos que mais caíram (ótimo para encontrar oportunidades).
* **Maior Dividendo:** Ordena do maior para o menor *Dividend Yield* (12m) e mostra o valor em `R$` pago por cota no último mês.
* **Mais Negociados / Mais Comprados:** Ordena pelos ativos de maior volume financeiro e liquidez na B3.
* **Mais Descontados (`Menor P/VP` ou `P/L`):** Mostra os FIIs negociando abaixo do valor patrimonial (`P/VP < 1,00`) ou ações com menor múltiplo de lucro.

### 4.2. Página Exclusiva da Ação ou FII (`F09`, `F10`, `F11`, `F12`, `F13`, `F14`)
Ao clicar em qualquer card de Ação (ex: `PETR4`, `WEGE3`) ou FII (ex: `MXRF11`, `HGLG11`), abre a tela dedicada daquele ativo contendo **4 blocos principais**:

1. **Cabeçalho e Gráfico Interativo com Crosshair (`1D`, `5D`, `1M`, `6M`, `1A`, `5A`):**
   * Preço atual em destaque, variação em `R$` e `%` do período selecionado.
   * Gráfico interativo onde, ao mover o mouse (*hover*), uma linha vertical acompanha o cursor mostrando uma *tooltip* com a **Data/Hora exata** e o **Preço exato naquele instante**.
   * Se você tiver o ativo na carteira, aparece uma linha horizontal pontilhada marcando o **seu Preço Médio** para você visualizar na hora se o preço atual está acima ou abaixo do seu custo.
2. **Bloco de Dividendos por Cota:**
   * Mostra em destaque: **Último Rendimento por Cota (`R$ X,XX / cota`)**, **Data Com**, **Data de Pagamento**, **Rendimento % no mês** e **DY 12 meses**.
   * Mostra quanto **você** recebe com sua posição atual e um gráfico de barras com a evolução dos dividendos pagos por cota nos últimos 12 meses.
3. **Bloco "Relatórios Oficiais & Resumo por IA" (Integração B3 Fundos.NET / CVM):**
   * Lista automaticamente os últimos **Relatórios Gerenciais**, **Avisos aos Cotistas** e **Fatos Relevantes** publicados oficialmente pelo fundo/empresa na B3.
   * Botão **"Interpretar Relatório Automaticamente"**: lê o PDF oficial e exibe em segundos um resumo executivo com os pontos positivos, pontos de atenção, vacância, inadimplência e perspectivas de dividendos futuros.
4. **Bloco de Notícias Recentes do Ativo:**
   * Feed automático com as notícias recentes da mídia financeira sobre aquele ativo específico, já classificadas por sentimento (*Positivo*, *Neutro*, *Negativo*).

---

## 5. Fontes de Dados e APIs Gratuitas (Arquitetura de Integração)

| Tipo de Dado | Fonte Primária (Gratuita) | Fonte Secundária (Fallback) | Frequência de Atualização |
| :--- | :--- | :--- | :--- |
| **Ações B3, FIIs, ETFs, BDRs (Preços e Histórico `1D`/`5D`/`1M`/`6M`/`1A`)** | **Yahoo Finance (`yfinance`)** — sufixo `.SA` | **Brapi API** (`brapi.dev`) | A cada 1 min (ou em tempo real ao abrir a página do ativo) |
| **Dividendos por Cota, `P/VP`, `P/L` e Indicadores de FIIs/Ações** | **Yahoo Finance + Scraper/API StatusInvest / Fundamentus** | **Brapi API / B3 Fundos.NET** | Atualização automática diária / sob demanda |
| **Relatórios Gerenciais de FIIs e Fatos Relevantes (PDFs Oficiais)** | **API Pública B3 Fundos.NET (`fnet.bmfbovespa.com.br`)** e **RAD CVM** | — | Verificação automática ao abrir a página do ativo |
| **Notícias do Ativo em Tempo Real** | **Google News Finance RSS** (`q=TICKER`) + **Yahoo Finance News** | Feeds RSS **InfoMoney / MoneyTimes** | Ao abrir a página do ativo / A cada 15 min |
| **Interpretação Automática de Relatórios e Notícias (IA)** | **Extrator `PyMuPDF` + Google Gemini API (`gemini-2.5-flash` Free Tier)** | Analisador heurístico local de indicadores e palavras-chave financeiras | Sob demanda (salvo em cache local no SQLite após processar) |
| **Stocks EUA, REITs, Índices Globais** | **Yahoo Finance (`yfinance`)** | — | A cada 1 min |
| **Criptomoedas (`BTC`, `ETH`, `SOL`, etc.)** | **Binance Public API / WebSocket** | **CoinGecko API** | **Tempo Real (1s - 5s)** |
| **Dólar (`USD/BRL`) e Euro (`EUR/BRL`)** | **AwesomeAPI** (`economia.awesomeapi.com.br`) | **Yahoo Finance (`USDBRL=X`) / BCB PTAX** | A cada 30 segundos |
| **CDI, Taxa Selic e IPCA Oficiais** | **API do Banco Central do Brasil (SGS/BCB)** (Séries `432`, `12`, `4389`, `433`) | Cache local da última taxa oficial | Ao abrir o app / Diário |

---

## 6. Arquitetura Técnica Proposta

* **Linguagem / Backend:** **Python 3.12** com **FastAPI** (alta velocidade, chamadas assíncronas para cotações, extrator de PDFs da B3 e integração com IA).
* **Banco de Dados:** **SQLite 3** local (`sim_database.db`), guardando carteira, transações, histórico de dividendos e os resumos de relatórios gerados pela IA.
* **Frontend / Interface Visual:** Interface Web Moderna *Dark Mode FinTech* com **TradingView Lightweight Charts** (para o gráfico interativo com *crosshair* de `1D`, `5D`, `1M`, `6M`, `1A` onde o valor e a data aparecem ao passar o mouse) + **Chart.js** para gráficos de alocação e dividendos.
