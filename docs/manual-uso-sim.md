# Manual de Uso do SIM — Sistema de Inteligência de Mercado e Gestão de Carteira

Este documento apresenta instruções práticas para instalar, abrir, operar, configurar provedores/IA, atualizar, fazer backup e restaurar o **SIM** no Windows sem necessidade de ferramentas de desenvolvimento.

---

## 1. Instalação e Inicialização no Windows

### 1.1 Pré-requisito Único
- **Python 3.11 ou 3.12** instalado no Windows com a opção **"Add Python to PATH"** marcada ([python.org/downloads](https://www.python.org/downloads/)).

### 1.2 Instalação Inicial (1 clique)
1. Na pasta principal do projeto, dê um duplo clique em **`Instalar_SIM_Windows.bat`**.
2. O instalador fará automaticamente:
   - Verificação do Python instalado;
   - Backup preventivo de `sim_database.db` (caso já exista);
   - Instalação/atualização das bibliotecas de `requirements.txt`;
   - Verificação e migração segura das tabelas SQLite;
   - Criação do atalho **"SIM - Investimentos"** na sua Área de Trabalho (com ícone próprio).

### 1.3 Como Abrir o SIM no Dia a Dia
Você tem duas opções equivalentes:
- **Modo Aplicativo Silencioso (recomendado):** clique duas vezes no atalho **"SIM - Investimentos"** na Área de Trabalho (ou no arquivo `Iniciar_SIM_Silencioso.vbs`). O servidor iniciará em segundo plano sem janela de comando aberta e abrirá o aplicativo em janela dedicada (`http://localhost:8000`).
- **Modo com Console Visível:** clique duas vezes em **`Iniciar_SIM.bat`** caso queira acompanhar os logs técnicos do servidor em tempo real.

---

## 2. Operação da Carteira e Dashboard

### 2.1 Registro de Operações e Proventos
- **Nova Ordem (Compra / Venda):** clique em **Nova Ordem** no topo da tela.
  - Para ativos brasileiros (`ACAO_BR`, `FII`, `ETF_BR`, `BDR`, `CRIPTO`), informe preços e custos em **BRL (R\$)**.
  - Para ativos internacionais (`STOCK_US`, `REIT_US`, `ETF_US`), informe preços e taxas em **USD (US\$)** e a **taxa de câmbio BRL/USD** da operação (se deixada em branco, o SIM usa o câmbio atual e marca a operação como *câmbio estimado* até você informar o câmbio definitivo).
- **Proventos (Dividendos / JCP / Rendimentos):** na aba **Carteira → Proventos**, registre valores recebidos ou sincronize automaticamente o histórico de dividendos dos ativos em carteira.
- **Renda Fixa & Tesouro Direto:** na aba **Renda Fixa**, cadastre títulos pós-fixados (% do CDI ou Selic), pré-fixados ou IPCA+, com cálculo diário sobre dias úteis (base 252) e alíquota regressiva de IR.
- **Importação e Exportação B3 (`.xlsx` / `.csv`):**
  - Importe planilhas de movimentação ou posição da B3 pelo botão **Importar B3**;
  - Exporte sua carteira consolidada em Excel (`.xlsx`) ou CSV auditável na aba **Análise → Exportar CSV**.

### 2.2 Aba Análise (Dashboard Auditável)
Na aba **Carteira → Análise**, você confere:
- **Consolidação por Moeda Original (BRL vs USD):** custo original em US\$, valor atual em US\$, câmbio PTAX/comercial aplicado e data/hora da cotação;
- **Qualidade dos Dados:** alerta imediato caso algum ativo esteja sem cotação de mercado (avaliado pelo preço médio) ou com operação usando câmbio estimado;
- **Composição e Concentração:** participação por classe, moeda e país + **Top 5 maiores posições**;
- **Evolução Patrimonial e Proventos por Mês:** gráficos e tabelas conciliados diretamente com os lançamentos do banco SQLite.

---

## 3. Provedores de Dados de Mercado, Câmbio e Notícias

O SIM utiliza exclusivamente fontes reais, identificando a origem e o horário de coleta em cada tela:

| Domínio | Provedor Primário | Fallback / Contingência | Cobertura e Limites |
| :--- | :--- | :--- | :--- |
| **Preços e Histórico (Brasil e EUA)** | **Yahoo Finance (`yfinance`)** | Cache persistente SQLite (`market_history_cache` / `assets_catalog`) | Ações B3, FIIs, ETFs, BDRs, Stocks/REITs/ETFs EUA e Cripto. Cotações com atraso de ~15 min ou fim de dia. Sem chave obrigatória. |
| **Câmbio BRL/USD e Macro** | **AwesomeAPI + Banco Central do Brasil (SGS BCB)** | `yfinance` (`USDBRL=X`) + Cache SQLite (`macro_indicators_cache`) | Dólar comercial (`USD-BRL`), Selic Meta (série BCB 432), CDI e IPCA 12m (série BCB 13522). |
| **Notícias Financeiras** | **Google News RSS (PT-BR)** | Cache SQLite (`asset_news_cache`) | Manchetes reais com veículo de imprensa, data de publicação e link clicável. Nunca gera manchetes sintéticas. |

- **Funcionamento Offline:** se você estiver sem internet ou se um provedor externo oscilar, o SIM **não bloqueia** a consulta da carteira e exibe o último dado salvo em cache com selo visual de aviso (*Dado em cache / desatualizado*).
- Para detalhes técnicos completos sobre limites e termos de uso, consulte [`docs/provedores-mercado.md`](provedores-mercado.md).

---

## 4. Configuração Segura da Chave de IA e Uso do Analista / Radar

### 4.1 Como Configurar sua Chave de API
1. Clique no botão **IA Config** (ícone de engrenagem no canto superior direito).
2. Escolha o **Provedor de IA**:
   - **Google Gemini (recomendado — possui nível gratuito no Google AI Studio):** modelos `gemini-2.5-flash` ou `gemini-2.5-pro`;
   - **OpenAI (ChatGPT):** modelos `gpt-4o-mini` ou `gpt-4o`;
   - **Groq Cloud:** modelo `llama-3.3-70b-versatile`.
3. Cole sua chave no campo **Sua API Key Pessoal** e clique em **Salvar Configurações**.
4. Clique em **Testar Chave Agora** para validar a comunicação em tempo real.

> **Segurança e Privacidade:** sua chave é criptografada localmente com **Fernet AES-128** usando o arquivo local `.sim_secret.key` (que nunca sai do seu computador) e **jamais** é reexibida em texto aberto na interface ou nos logs.

### 4.2 Usando o Analista de IA e o Radar de Mercado
- **Mesmo sem chave de API configurada**, o SIM gera análises completas usando seu **Motor Analítico Determinístico**, separando:
  1. **Fatos Observados** (números extraídos das suas posições, cotações e notícias reais);
  2. **Cálculos do SIM** (métricas exatas de rentabilidade, concentração, volatilidade e drawdown);
  3. **Interpretação Analítica, Riscos e Argumentos Contrários**;
  4. **Fontes Utilizadas e Alertas de Qualidade de Dados**.
- Na aba **Radar & IA**, você pode:
  - Clicar em **Analisar Minha Carteira**;
  - Comparar **Ativos Semelhantes** informando tickers (ex.: `ITUB4, BBDC4, BBAS3`);
  - Consultar o **Histórico de Análises** e clicar em **Comparar Últimas 2 Análises** para ver o que mudou no seu patrimônio e na exposição desde a análise anterior;
  - Marcar oportunidades do radar ou da sua *Watchlist* como **Relevante**, **Acompanhando** ou **Ignorar**.

---

## 5. Atualização, Backup e Restauração

### 5.1 Como Criar um Backup (2 cliques)
1. Abra **IA Config** (canto superior direito) e role até a seção **Backup & Restauração do Banco (SQLite)**.
2. Clique em **Criar Backup Agora**.
3. O SIM usará a API nativa de backup online do SQLite (`sqlite3.Connection.backup`), executará `PRAGMA integrity_check` para garantir integridade de 100% e salvará a cópia datada em `backups/<timestamp>_manual_ui/`.
4. Você também pode clicar em **Baixar** ao lado de qualquer backup da lista para salvar o arquivo `.db` em um pendrive ou nuvem pessoal.

### 5.2 Como Restaurar um Backup
- **Pela lista de backups locais:** em **IA Config → Backup & Restauração**, clique em **Restaurar** ao lado do backup desejado.
- **A partir de um arquivo `.db` externo:** clique em **Restaurar de Arquivo (.db)** e selecione o arquivo SQLite.
- **Proteção contra falhas:** antes de qualquer restauração, o SIM:
  1. Valida se o arquivo é um banco SQLite íntegro (`PRAGMA integrity_check == ok`) e se contém as tabelas essenciais do SIM (arquivos corrompidos ou inválidos são bloqueados sem tocar na sua carteira);
  2. Cria automaticamente um backup de segurança do estado atual (`pre_restore_auto`);
  3. Restaura o banco a quente e recarrega a carteira imediatamente.

### 5.3 Como Atualizar o SIM
Sempre que baixar uma nova versão do projeto (ou executar `git pull`):
1. Dê um duplo clique em **`Instalar_SIM_Windows.bat`**.
2. Ele fará um backup automático (`pre_update`) do seu banco `sim_database.db`, atualizará pacotes se necessário e aplicará eventuais novas colunas no banco sem perder nenhum dado.
