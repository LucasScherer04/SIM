# Diagnóstico do SIM — Etapa 0

**Data:** 06/11/2026
**Escopo:** inspeção somente leitura. Nenhum código de produção nem o banco `sim_database.db` foram alterados.
**Legenda:** ✅ verificado nesta execução · 🔎 lido no código, não executado · ❓ não verificado

---

## 1. Tecnologias e comandos

| Item | Observado |
|---|---|
| Linguagem | Python 3.12.10 ✅ |
| Backend | FastAPI + Uvicorn (`app/main.py`, versão da API `1.3.0`) |
| Frontend | HTML/CSS/JS puro servido pelo backend (`static/index.html`, `app.js` ≈ 5.000 linhas, `styles.css`), com PWA (`manifest.json`, `sw.js`) |
| Banco | SQLite (`sim_database.db`), modo WAL, caminho fixo em `app/database.py:DB_PATH` |
| Dependências | `fastapi, uvicorn, httpx, requests, yfinance, feedparser, pymupdf, pydantic, openpyxl, cryptography` (`requirements.txt`, sem versões fixas, só `>=`) |
| Iniciar | `Iniciar_SIM.bat`: abre Chrome em modo app e roda `python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload` |
| Executável | `SIM.exe` (154 KB) versionado no git; conteúdo/origem não inspecionados ❓ |
| Testes | `python -m pytest -q` |
| Segredos | `.sim_secret.key` (chave Fernet) e `*.db` estão no `.gitignore`; nenhum está rastreado pelo git ✅ |

## 2. Telas (views em `static/index.html`)

`DASHBOARD`, `MARKET_CLASS` (listagem por classe), `ASSET_DETAIL`, `RENDA_FIXA`, `DIVIDENDS`, `AI_RADAR`. Há também login/PIN, configurações e importação B3. 🔎 Não foi feita inspeção visual da interface ❓.

## 3. Rotas da API (`app/main.py`)

- **Auth/multiusuário:** `/api/auth/{status,users,login,setup,register,logout,change-pin}`
- **Carteira:** `GET /api/portfolio`, `POST /api/transactions`, `DELETE /api/transactions/{id}`, `DELETE /api/portfolio/position/{ticker}`, `POST .../adjust-avg-price`, `POST /api/portfolio/clear`, `GET /api/rebalance`
- **Renda fixa:** `POST /api/fixed-income`, `POST .../{id}/adjust`, `DELETE .../{id}`
- **Proventos:** `POST /api/dividends`, `DELETE /api/dividends/{id}`
- **Mercado/ativo:** `/api/market/assets`, `/api/asset/{ticker}`, `/api/asset/{ticker}/analyze-report`, `/api/lookup-ticker`, `/api/favorites`
- **Importação/exportação B3 (xlsx):** `/api/b3/{preview,sync,logs,template-xlsx,export-xlsx}`
- **IA:** `/api/settings`, `/api/ai/test`, `/api/ai/radar`
- **WhatsApp:** `/api/whatsapp/{test,dispatch-daily,status,preview-daily}`
- **Outros:** `/api/system/mobile-access`

Todas as rotas `/api/*` de dados exigem o cabeçalho `X-SIM-Token` ✅ (smoke test: 401 sem token). Há middleware de proteção CSRF por Origin/Referer.

## 4. Banco de dados (contagem de linhas em 06/11/2026)

| Tabela | Linhas | Função |
|---|---|---|
| `assets_catalog` | 75 | Catálogo + última cotação e indicadores por ticker |
| `transactions` | 6 | Compras/vendas (`tx_type`, `quantity`, `unit_price`, `fees`, `currency`, `fx_rate`, `user_id`) |
| `fixed_income` | 21 | Renda fixa/Tesouro (indexador, taxa, valor aplicado, âncora de mercado) |
| `dividends_received` | **0** | Proventos |
| `allocation_targets` | 7 | Metas de alocação por classe |
| `app_settings` | 14 | Configurações (inclui chaves de API cifradas) |
| `ai_report_cache` / `ai_radar_cache` | 20 / 0 | Cache de relatórios e do radar de IA |
| `b3_sync_logs` | 8 | Log de importações B3 |
| `users` / `user_sessions` | 1 / 1 | Usuários e sessões |
| `favorites` | 0 | Favoritos |

Observações:
- Todos os valores monetários são `REAL` (ponto flutuante binário).
- Não existe tabela de histórico de patrimônio/snapshots nem de notícias.
- `transactions` tem apenas 6 linhas e `dividends_received` está vazia: a carteira real está majoritariamente em `fixed_income` e/ou foi carregada via sincronização B3 ❓ (não analisado o conteúdo dos dados pessoais).

## 5. Regras financeiras atuais (🔎 `app/market_service.py`)

**Renda variável (`get_portfolio_summary`)**
- Preço médio móvel: compra soma `qtd×preço + taxas` ao custo; venda não altera o PM; zera posição quando qtd ≤ 1e-8.
- Resultado realizado em BRL: `(preço_venda − PM) × qtd − taxas`.
- Ativos em USD: custo acumulado em BRL pelo câmbio de cada compra (`cost_basis_brl`); resultado da venda = `((p×q) − taxas) × câmbio_venda − custo_BRL_proporcional`.
- Posição aberta: `invested_brl = qtd × PM × câmbio_atual` e `current_brl = qtd × preço × câmbio_atual`. **O lucro em USD usa o câmbio atual nos dois lados, não o `cost_basis_brl`.** Avaliar na Etapa 1 se isso é intencional.
- Compras sintéticas (sincronização de posição B3) são marcadas como PM estimado (`pm_estimated`).
- Câmbio de fallback: `5.72` fixo quando `fx_rate` ausente e sem cotação.

**Renda fixa (`calculate_fixed_income_position`)**
- Capitalização por dias úteis estimados `dias_corridos × 252/365` (aproximação, sem calendário de feriados).
- Indexadores `CDI`, `SELIC`, `IPCA`, `PRE`; IR regressivo 22,5% / 20% / 17,5% / 15% (≤180 / ≤360 / ≤720 / >720 dias); isento se `tax_exempt`.
- Com âncora de mercado (valor importado da B3), projeta só o rendimento após a data da âncora.
- Não há tratamento de IOF, nem de come-cotas de fundos.

## 6. Integrações externas

| Finalidade | Fonte no código | Observações |
|---|---|---|
| Cotações BR/EUA | Yahoo Finance via `yfinance` (`.SA` para BR) | Sync em thread, no máximo a cada 90 s |
| Cripto | Binance (BTC, ETH, SOL) | |
| Câmbio USD/BRL, EUR/BRL, BTC/USD | AwesomeAPI | |
| Selic | BCB SGS série 432 | CDI é **estimado** como `Selic − 0,10` |
| IPCA 12m | **Não é buscado**; valor fixo `4.42` | |
| IBOV / S&P500 | Yahoo (`^BVSP`, `^GSPC`) | Valores iniciais fixos até a 1ª sincronização |
| Notícias | Google News RSS (`feedparser`) | Sem persistência/cache em banco |
| Documentos oficiais | B3 Fundos.NET, CVM RAD, extração de PDF (`pymupdf`) | Requisições com `verify=False` (TLS sem verificação) |
| IA | Google Gemini, OpenAI, Groq | Chave cifrada com Fernet em `app_settings`; chave mestra em `.sim_secret.key` |
| WhatsApp | `whatsapp_service.py` (relatório diário agendado) | Fora do escopo do plano |

Falhas de rede são tratadas com `except Exception: pass` em várias integrações, sem registro/aviso ao usuário.

## 7. Testes e execução

- `python -m pytest -q` → **47 passed, 2 warnings** em ~12 s ✅. Os testes usam banco temporário (`monkeypatch` de `DB_PATH`), não tocam no banco real 🔎. Um teste faz chamada de rede real (B3 Fundos.NET).
- Arquivos: `test_b3_fixed_income`, `test_b3_sync_reconcile`, `test_fixes_audit`, `test_portfolio_clear`, `test_security_and_auth`, `test_whatsapp_scheduler`. **Não há arquivo dedicado a compras/vendas/PM/câmbio de `get_portfolio_summary`** — cobertura desses cálculos não confirmada ❓.
- Smoke test com `TestClient` sobre **cópia** do banco: `/` → 200, `/api/auth/status` → 200, rotas protegidas → 401 sem token ✅.
- Já havia um servidor escutando em `0.0.0.0:8000` (processo do usuário). A aplicação **não** foi iniciada manualmente nem testada visualmente pelo navegador ❓.

## 8. Backup e restauração (verificados ✅)

Backup criado em `backups/20261106_172411/` com `sim_database.db` (API de backup do SQLite, consistente em modo WAL) e `.sim_secret.key`.

- `PRAGMA integrity_check`: `ok` na origem, no backup e na cópia restaurada.
- Contagem de linhas de todas as tabelas: idêntica entre origem, backup e cópia restaurada.

**Fazer backup** (com o SIM fechado ou aberto), na raiz do repositório:

```powershell
$d = "backups\$(Get-Date -Format yyyyMMdd_HHmmss)"; New-Item -ItemType Directory $d | Out-Null
python -c "import sqlite3,sys; s=sqlite3.connect('sim_database.db'); d=sqlite3.connect(sys.argv[1]); s.backup(d); d.close()" "$d\sim_database.db"
Copy-Item .sim_secret.key $d
```

**Restaurar:** 1) feche o SIM (encerre o uvicorn); 2) renomeie o banco atual para guardá-lo; 3) apague `sim_database.db-wal` e `sim_database.db-shm`; 4) copie `sim_database.db` e `.sim_secret.key` da pasta do backup para a raiz; 5) abra o SIM.

> Sem o `.sim_secret.key` correspondente, as chaves de API cifradas no banco não podem ser decifradas.

A pasta `backups/` contém a chave Fernet e dados pessoais: **não deve ser versionada**.

---

## 9. Recomendações

### Preservar
- Estrutura FastAPI + SQLite + frontend estático; autenticação por token e proteção CSRF; cifra das chaves de API.
- Importação/exportação B3 (xlsx) e sua suíte de testes; PM estimado vs. real; âncora de mercado na renda fixa.
- Suíte de testes existente com bancos temporários.

### Corrigir (problemas comprovados no código)
1. **Gráfico sintético:** `_generate_realistic_series` fabrica uma série de preços quando o Yahoo falha, sem aviso ao usuário. Viola "não inventar dados".
2. **Macro com valores fixos:** IPCA 12m (`4.42`), CDI (`Selic − 0,10`) e valores iniciais de câmbio/Selic/IBOV/S&P/BTC exibidos sem indicar que são estimativas ou padrão. Câmbio de fallback `5.72` repetido em 4 lugares.
3. **Falhas silenciosas** (`except Exception: pass`) nas integrações; o plano exige mostrar última atualização e estado do dado.
4. **TLS desativado** (`verify=False`) em B3/CVM e extração de PDF.
5. **Ponto flutuante** em todos os valores monetários (plano pede estratégia explícita de precisão).
6. **Lucro de ativos em USD** calculado com câmbio atual nos dois lados (ver §5).
7. `Iniciar_SIM.bat` usa `--reload` e `--host 0.0.0.0` (expõe o app na rede local).

### Simplificar / avaliar para remoção (exige sua autorização)
O plano coloca **fora do escopo** itens que existem hoje: **WhatsApp** (envio e agendador), **PWA/acesso por celular** (`/api/system/mobile-access`, `manifest.json`, `sw.js`, bind em `0.0.0.0`) e **multiusuário** (`users`, `register`, `user_id`). Nada foi removido. Recomendação: manter por ora e decidir caso a caso.

### Lacunas para etapas futuras
- Sem histórico de patrimônio (necessário na Etapa 2).
- Sem cache/persistência de notícias e de séries históricas (Etapa 3).
- `dividends_received` vazia: validar o fluxo de proventos (Etapa 1).
- Radar/IA já existem (`ai_radar_service.py`, `intelligence_service.py`); avaliar na Etapa 4 se atendem a rastreabilidade de fontes exigida.

## 10. Riscos
- `sim_database.db` real está em modo WAL e há um servidor em execução; backups devem usar a API de backup (como acima), não cópia simples do arquivo.
- `SIM.exe` versionado tem origem desconhecida ❓.
- Cálculos de posição/PM/câmbio sem testes dedicados confirmados: alterar na Etapa 1 exige criar testes antes.

## 11. Próxima tarefa recomendada
**Etapa 1 — Estabilizar a carteira:** começar por testes de regressão para `get_portfolio_summary` (compra, venda parcial/total, taxas, USD) registrando o comportamento atual, antes de qualquer mudança de regra.
