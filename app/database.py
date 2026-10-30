import os
import sqlite3
import json
from datetime import datetime, date

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "sim_database.db")


def get_conn():
    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout = 30000")
    conn.row_factory = sqlite3.Row
    return conn


# Colunas adicionadas após a criação original das tabelas (migração idempotente).
FIXED_INCOME_EXTRA_COLUMNS = {
    # Valor de mercado/curva informado pela fonte oficial (ex.: B3) na data market_value_date.
    # Quando presente, é a "âncora" da posição: o rendimento é projetado apenas a partir dessa data,
    # evitando aplicar juros novamente sobre um valor que já os contém.
    "market_value": "REAL",
    # Valor líquido (após IR/IOF) informado pela fonte oficial na mesma data, quando disponível.
    "market_net_value": "REAL",
    # Data de referência (YYYY-MM-DD) dos valores acima.
    "market_value_date": "TEXT DEFAULT ''",
}


def migrate_fixed_income_columns(conn=None):
    """Adiciona colunas novas em fixed_income caso o banco seja de uma versão anterior."""
    own_conn = conn is None
    if own_conn:
        conn = get_conn()
    existing = {row[1] for row in conn.execute("PRAGMA table_info(fixed_income)").fetchall()}
    if existing:
        for col, ddl in FIXED_INCOME_EXTRA_COLUMNS.items():
            if col not in existing:
                conn.execute(f"ALTER TABLE fixed_income ADD COLUMN {col} {ddl}")
        conn.commit()
    if own_conn:
        conn.close()


def migrate_to_multiuser(conn=None):
    """
    Garante o suporte a múltiplos usuários e dados isolados por conta no SQLite.
    Migra tabelas existentes adicionando a coluna user_id e chave primária composta onde necessário.
    """
    own_conn = conn is None
    if own_conn:
        conn = get_conn()

    cur = conn.cursor()

    # 1. Tabela de Usuários
    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        pin_hash TEXT NOT NULL DEFAULT '',
        is_admin INTEGER DEFAULT 1,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # 2. Tabela de Sessões
    cur.execute("""
    CREATE TABLE IF NOT EXISTS user_sessions (
        token TEXT PRIMARY KEY,
        user_id INTEGER NOT NULL,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        expires_at TEXT NOT NULL,
        FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
    )
    """)

    # 3. Adicionar user_id nas tabelas com chave primária ID
    for tbl in ("transactions", "fixed_income", "dividends_received", "b3_sync_logs"):
        exists = cur.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{tbl}'").fetchone()
        if exists:
            cols = {r[1] for r in cur.execute(f"PRAGMA table_info({tbl})").fetchall()}
            if "user_id" not in cols:
                cur.execute(f"ALTER TABLE {tbl} ADD COLUMN user_id INTEGER DEFAULT 1")

    # 4. Migrar favorites para chave composta (user_id, ticker)
    fav_exists = cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='favorites'").fetchone()
    if fav_exists:
        cols = {r[1] for r in cur.execute("PRAGMA table_info(favorites)").fetchall()}
        if "user_id" not in cols:
            cur.execute("""
            CREATE TABLE IF NOT EXISTS favorites_new (
                user_id INTEGER NOT NULL DEFAULT 1,
                ticker TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (user_id, ticker)
            )
            """)
            cur.execute("INSERT OR IGNORE INTO favorites_new (user_id, ticker, created_at) SELECT 1, ticker, created_at FROM favorites")
            cur.execute("DROP TABLE favorites")
            cur.execute("ALTER TABLE favorites_new RENAME TO favorites")

    # 5. Migrar allocation_targets para chave composta (user_id, asset_class)
    alloc_exists = cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='allocation_targets'").fetchone()
    if alloc_exists:
        cols = {r[1] for r in cur.execute("PRAGMA table_info(allocation_targets)").fetchall()}
        if "user_id" not in cols:
            cur.execute("""
            CREATE TABLE IF NOT EXISTS allocation_targets_new (
                user_id INTEGER NOT NULL DEFAULT 1,
                asset_class TEXT NOT NULL,
                target_pct REAL NOT NULL,
                PRIMARY KEY (user_id, asset_class)
            )
            """)
            cur.execute("INSERT OR IGNORE INTO allocation_targets_new (user_id, asset_class, target_pct) SELECT 1, asset_class, target_pct FROM allocation_targets")
            cur.execute("DROP TABLE allocation_targets")
            cur.execute("ALTER TABLE allocation_targets_new RENAME TO allocation_targets")

    # 6. Migrar ou criar app_settings com chave composta (user_id, key)
    settings_exists = cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='app_settings'").fetchone()
    if settings_exists:
        cols = {r[1] for r in cur.execute("PRAGMA table_info(app_settings)").fetchall()}
        if "user_id" not in cols:
            cur.execute("""
            CREATE TABLE IF NOT EXISTS app_settings_new (
                user_id INTEGER NOT NULL DEFAULT 1,
                key TEXT NOT NULL,
                value TEXT NOT NULL,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (user_id, key)
            )
            """)
            cur.execute("INSERT OR IGNORE INTO app_settings_new (user_id, key, value, updated_at) SELECT 1, key, value, updated_at FROM app_settings")
            cur.execute("DROP TABLE app_settings")
            cur.execute("ALTER TABLE app_settings_new RENAME TO app_settings")
    else:
        cur.execute("""
        CREATE TABLE IF NOT EXISTS app_settings (
            user_id INTEGER NOT NULL DEFAULT 1,
            key TEXT NOT NULL,
            value TEXT NOT NULL,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (user_id, key)
        )
        """)

    # 7. Garantir usuário padrão (Lucas) caso a tabela users esteja vazia
    users_count = cur.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    if users_count == 0:
        cur.execute("INSERT INTO users (id, username, pin_hash, is_admin) VALUES (1, 'Lucas', '', 1)")

    conn.commit()
    if own_conn:
        conn.close()


SEED_CATALOG = [
    # Ações Brasileiras (B3)
    ("PETR4", "Petrobras PN", "ACAO_BR", "BRL", "Petróleo, Gás e Biocombustíveis", "33.000.167/0001-01", 36.85, 2.14, 1450000000, 14.8, 4.9, 1.08, 0.92, "2026-08-21", "2026-09-20"),
    ("VALE3", "Vale ON", "ACAO_BR", "BRL", "Mineração e Siderurgia", "33.592.510/0001-54", 61.40, 1.45, 1180000000, 9.6, 5.8, 1.32, 2.15, "2026-08-12", "2026-09-04"),
    ("WEGE3", "WEG ON", "ACAO_BR", "BRL", "Bens Industriais / Motores", "84.429.695/0001-11", 52.90, 3.12, 540000000, 1.8, 32.4, 9.85, 0.24, "2026-09-22", "2026-10-15"),
    ("ITUB4", "Itaú Unibanco PN", "ACAO_BR", "BRL", "Bancos e Financeiro", "60.872.504/0001-23", 35.10, 0.89, 890000000, 8.4, 8.2, 1.72, 0.35, "2026-09-30", "2026-10-10"),
    ("BBAS3", "Banco do Brasil ON", "ACAO_BR", "BRL", "Bancos e Financeiro", "00.000.000/0001-91", 28.45, -0.65, 760000000, 10.6, 4.6, 0.91, 0.48, "2026-09-11", "2026-09-27"),
    ("BBSE3", "BB Seguridade ON", "ACAO_BR", "BRL", "Seguros e Previdência", "17.344.597/0001-94", 36.20, 1.15, 290000000, 10.1, 8.9, 6.40, 1.38, "2026-08-16", "2026-08-30"),
    ("TAEE11", "Taesa Unit", "ACAO_BR", "BRL", "Energia Elétrica / Transmissão", "07.859.971/0001-30", 35.60, 0.42, 185000000, 9.8, 8.1, 1.75, 0.65, "2026-08-15", "2026-08-29"),
    ("PRIO3", "PRIO ON", "ACAO_BR", "BRL", "Petróleo e Gás", "10.629.105/0001-68", 43.80, -1.85, 620000000, 0.4, 7.5, 2.10, 0.08, "2026-05-10", "2026-05-25"),
    ("EGIE3", "Engie Brasil ON", "ACAO_BR", "BRL", "Energia Elétrica / Geração", "02.474.103/0001-19", 42.15, 0.78, 140000000, 7.9, 8.4, 3.12, 1.15, "2026-08-20", "2026-09-25"),
    ("SBSP3", "Sabesp ON", "ACAO_BR", "BRL", "Saneamento Básico", "43.776.517/0001-80", 94.50, 2.65, 480000000, 2.4, 15.2, 1.95, 1.42, "2026-04-28", "2026-06-24"),
    ("RENT3", "Localiza ON", "ACAO_BR", "BRL", "Aluguel de Carros / Mobilidade", "16.670.085/0001-55", 44.20, -2.30, 510000000, 3.8, 14.1, 1.82, 0.39, "2026-09-25", "2026-10-18"),
    ("VIVT3", "Telefônica Vivo ON", "ACAO_BR", "BRL", "Telecomunicações", "02.558.157/0001-62", 52.80, 0.95, 210000000, 7.2, 14.8, 1.26, 0.62, "2026-09-15", "2026-10-15"),
    ("SANB11", "Santander Brasil Unit", "ACAO_BR", "BRL", "Bancos e Financeiro", "90.400.888/0001-42", 29.10, 0.54, 195000000, 6.8, 9.1, 1.18, 0.40, "2026-09-18", "2026-10-08"),
    ("BBDC4", "Bradesco PN", "ACAO_BR", "BRL", "Bancos e Financeiro", "60.746.948/0001-12", 14.85, 0.40, 620000000, 7.5, 8.4, 0.96, 0.19, "2026-09-30", "2026-10-10"),
    ("ITSA4", "Itaúsa PN", "ACAO_BR", "BRL", "Holding Financeira & Industrial", "61.532.644/0001-15", 10.85, 0.75, 380000000, 8.9, 7.4, 1.31, 0.22, "2026-09-20", "2026-10-05"),
    ("B3SA3", "B3 Brasil Bolsa Balcão ON", "ACAO_BR", "BRL", "Serviços Financeiros / Bolsa", "09.346.601/0001-25", 11.40, 1.12, 520000000, 4.9, 14.2, 3.15, 0.14, "2026-09-15", "2026-10-04"),
    ("CMIG4", "Cemig PN", "ACAO_BR", "BRL", "Energia Elétrica", "17.155.730/0001-64", 11.30, 0.98, 240000000, 11.4, 5.9, 1.24, 0.32, "2026-09-12", "2026-09-30"),
    ("CPLE3", "Copel ON", "ACAO_BR", "BRL", "Energia Elétrica", "76.483.817/0001-20", 14.50, 0.65, 190000000, 6.2, 9.8, 1.21, 0.18, "2026-09-10", "2026-09-28"),
    ("EQTL3", "Equatorial Energia ON", "ACAO_BR", "BRL", "Energia Elétrica / Distribuição", "03.220.438/0001-73", 32.90, 1.05, 310000000, 2.1, 14.5, 1.85, 0.35, "2026-08-25", "2026-09-15"),
    ("KLBN11", "Klabin Unit", "ACAO_BR", "BRL", "Papel e Celulose", "89.637.490/0001-45", 21.40, 0.62, 175000000, 6.4, 11.8, 2.65, 0.31, "2026-08-15", "2026-09-02"),
    ("SUZB3", "Suzano ON", "ACAO_BR", "BRL", "Papel e Celulose", "16.404.287/0001-55", 57.80, 1.30, 390000000, 2.8, 9.4, 1.72, 1.10, "2026-08-10", "2026-08-28"),
    ("GGBR4", "Gerdau PN", "ACAO_BR", "BRL", "Siderurgia e Metalurgia", "33.611.500/0001-19", 18.90, 0.88, 260000000, 6.1, 6.8, 0.74, 0.28, "2026-08-22", "2026-09-12"),
    ("RADL3", "Raia Drogasil ON", "ACAO_BR", "BRL", "Varejo Farmacêutico / Saúde", "61.585.865/0001-51", 25.80, 1.15, 230000000, 1.6, 34.0, 7.10, 0.11, "2026-09-18", "2026-10-05"),
    ("CXSE3", "Caixa Seguridade ON", "ACAO_BR", "BRL", "Seguros e Previdência", "22.543.331/0001-00", 14.90, 0.90, 165000000, 9.4, 11.2, 3.45, 0.56, "2026-08-20", "2026-09-06"),
    ("ABEV3", "Ambev ON", "ACAO_BR", "BRL", "Bebidas e Consumo", "07.526.557/0001-00", 12.80, 0.35, 410000000, 5.8, 13.5, 2.15, 0.73, "2026-09-15", "2026-10-10"),

    # Fundos Imobiliários (FIIs - B3)
    ("MXRF11", "Maxi Renda FII", "FII", "BRL", "Papel / Híbrido (CRI)", "97.521.225/0001-25", 9.96, 0.30, 12800000, 12.1, 0.0, 1.02, 0.10, "2026-09-30", "2026-10-15"),
    ("GARE11", "Guardian Real Estate FII", "FII", "BRL", "Renda Urbana & Logística (Híbrido)", "37.295.919/0001-60", 8.26, -1.08, 9200000, 12.06, 0.0, 0.91, 0.083, "2026-09-30", "2026-10-07"),
    ("HGLG11", "CSHG Logística FII", "FII", "BRL", "Galpões Logísticos", "11.728.688/0001-47", 158.40, 0.64, 9400000, 8.5, 0.0, 0.99, 1.10, "2026-09-30", "2026-10-15"),
    ("XPML11", "XP Malls FII", "FII", "BRL", "Shoppings", "28.757.546/0001-00", 108.90, -0.45, 14200000, 10.2, 0.0, 0.94, 0.92, "2026-09-30", "2026-10-25"),
    ("KNCR11", "Kinea Rendimentos Imob. FII", "FII", "BRL", "Papel / CRI (Pós CDI)", "16.706.958/0001-32", 104.20, 0.48, 11500000, 11.8, 0.0, 1.03, 1.00, "2026-09-30", "2026-10-14"),
    ("BTLG11", "BTG Pactual Logística FII", "FII", "BRL", "Galpões Logísticos", "11.839.593/0001-09", 99.80, 0.81, 8900000, 9.4, 0.0, 0.96, 0.78, "2026-09-30", "2026-10-25"),
    ("VISC11", "Vinci Shopping Centers FII", "FII", "BRL", "Shoppings", "17.554.274/0001-25", 112.50, -0.88, 6700000, 9.8, 0.0, 0.91, 0.85, "2026-09-30", "2026-10-15"),
    ("XPLG11", "XP Log FII", "FII", "BRL", "Galpões Logísticos", "26.502.794/0001-85", 98.40, 0.20, 6100000, 9.6, 0.0, 0.89, 0.78, "2026-09-30", "2026-10-15"),
    ("CPTS11", "Capitânia Securities II FII", "FII", "BRL", "Papel / CRI (IPCA+)", "18.979.895/0001-13", 7.85, -1.12, 8300000, 11.4, 0.0, 0.88, 0.08, "2026-09-30", "2026-10-18"),
    ("HGRU11", "CSHG Renda Urbana FII", "FII", "BRL", "Renda Urbana / Varejo & Educacional", "29.641.226/0001-53", 123.60, 0.55, 5800000, 9.1, 0.0, 0.97, 0.85, "2026-09-30", "2026-10-15"),
    ("KNRI11", "Kinea Renda Imobiliária FII", "FII", "BRL", "Híbrido (Lajes + Logística)", "12.005.956/0001-65", 148.90, 0.15, 7200000, 8.1, 0.0, 0.92, 1.00, "2026-09-30", "2026-10-15"),
    ("VGHF11", "Valora Hedge Fund FII", "FII", "BRL", "Papel / Multiestratégia", "36.771.692/0001-19", 8.65, 0.23, 7400000, 12.6, 0.0, 0.94, 0.09, "2026-09-30", "2026-10-07"),
    ("TGAR11", "TG Ativo Real FII", "FII", "BRL", "Desenvolvimento & Multipropriedade", "25.032.881/0001-53", 109.50, 0.35, 8100000, 13.4, 0.0, 0.93, 1.25, "2026-09-30", "2026-10-15"),
    ("ALZR11", "Alianza Trust Renda Imob. FII", "FII", "BRL", "Renda Urbana / Contratos Atípicos", "28.737.771/0001-85", 103.80, 0.42, 4900000, 9.2, 0.0, 0.98, 0.80, "2026-09-30", "2026-10-25"),
    ("KNSC11", "Kinea Securities FII", "FII", "BRL", "Papel / CRI (IPCA+ & CDI)", "35.864.448/0001-38", 8.95, 0.34, 6800000, 11.5, 0.0, 0.99, 0.09, "2026-09-30", "2026-10-14"),
    ("RZTR11", "Riza Terrax FII", "FII", "BRL", "Terras Agrícolas / Agro", "36.501.128/0001-86", 92.40, 0.51, 5600000, 12.8, 0.0, 0.95, 1.00, "2026-09-30", "2026-10-08"),
    ("TRXF11", "TRX Real Estate FII", "FII", "BRL", "Renda Urbana / Varejo Essencial", "28.548.288/0001-52", 102.50, 0.28, 7900000, 10.6, 0.0, 0.99, 0.93, "2026-09-30", "2026-10-15"),
    ("LVBI11", "VBI Logístico FII", "FII", "BRL", "Galpões Logísticos", "30.629.603/0001-18", 108.20, 0.19, 4300000, 9.3, 0.0, 0.91, 0.83, "2026-09-30", "2026-10-07"),
    ("BRCO11", "Bresco Logística FII", "FII", "BRL", "Galpões Logísticos", "20.748.515/0001-81", 112.90, 0.44, 4800000, 9.2, 0.0, 0.94, 0.87, "2026-09-30", "2026-10-15"),
    ("PVBI11", "VBI Prime Properties FII", "FII", "BRL", "Lajes Corporativas Triple A", "35.652.102/0001-76", 84.50, -0.35, 4200000, 8.8, 0.0, 0.83, 0.65, "2026-09-30", "2026-10-07"),
    ("VGIR11", "Valora RE III FII", "FII", "BRL", "Papel / CRI (Pós CDI)", "29.852.732/0001-91", 9.75, 0.31, 6400000, 12.9, 0.0, 1.00, 0.11, "2026-09-30", "2026-10-18"),
    ("BTHF11", "BTG Pactual Hedge Fund FII", "FII", "BRL", "Fundo de Fundos / Multiestratégia", "11.026.627/0001-38", 8.25, 0.12, 4700000, 10.4, 0.0, 0.88, 0.07, "2026-09-30", "2026-10-15"),

    # ETFs & BDRs (B3)
    ("IVVB11", "iShares S&P 500 B3 ETF", "ETF_BR", "BRL", "ETF Internacional S&P 500", "19.909.560/0001-91", 358.00, 1.25, 95000000, 0.0, 0.0, 1.00, 0.00, "", ""),
    ("BOVA11", "iShares Ibovespa ETF", "ETF_BR", "BRL", "ETF Índice Ibovespa", "10.406.511/0001-61", 128.40, 0.72, 410000000, 0.0, 0.0, 1.00, 0.00, "", ""),
    ("DIVO11", "It Now IDIV Dividendos ETF", "ETF_BR", "BRL", "ETF Índice Dividendos", "13.974.750/0001-06", 94.20, 0.88, 18000000, 0.0, 0.0, 1.00, 0.00, "", ""),
    ("SMAL11", "iShares Small Cap B3 ETF", "ETF_BR", "BRL", "ETF Small Caps Brasil", "10.406.600/0001-08", 96.50, 0.54, 68000000, 0.0, 0.0, 1.00, 0.00, "", ""),
    ("HASH11", "Hashdex Nasdaq Crypto ETF", "ETF_BR", "BRL", "ETF Criptoativos B3", "38.488.358/0001-58", 68.40, 2.90, 45000000, 0.0, 0.0, 1.00, 0.00, "", ""),
    ("WRLD11", "Investo FTSE Global All Cap ETF", "ETF_BR", "BRL", "ETF Ações Globais (VT)", "42.318.892/0001-14", 118.90, 0.95, 22000000, 0.0, 0.0, 1.00, 0.00, "", ""),
    ("GOLD11", "Trend Ouro B3 ETF", "ETF_BR", "BRL", "ETF Ouro / Commodities", "35.910.900/0001-19", 16.80, 0.65, 29000000, 0.0, 0.0, 1.00, 0.00, "", ""),

    # Stocks EUA & ETFs Globais
    ("NVDA", "NVIDIA Corporation", "STOCK_US", "USD", "Semicondutores & IA", "US-NVDA", 138.60, 2.85, 8900000000, 0.03, 52.4, 42.10, 0.01, "2026-09-05", "2026-09-26"),
    ("AAPL", "Apple Inc.", "STOCK_US", "USD", "Tecnologia & Consumo", "US-AAPL", 231.40, 1.10, 5400000000, 0.44, 34.8, 45.20, 0.25, "2026-08-12", "2026-08-15"),
    ("MSFT", "Microsoft Corporation", "STOCK_US", "USD", "Cloud & Software", "US-MSFT", 428.90, 0.92, 4800000000, 0.72, 35.1, 12.80, 0.83, "2026-08-15", "2026-09-12"),
    ("AMZN", "Amazon.com Inc.", "STOCK_US", "USD", "E-Commerce & AWS Cloud", "US-AMZN", 204.50, 1.64, 4100000000, 0.00, 41.2, 8.40, 0.00, "", ""),
    ("GOOGL", "Alphabet Inc. (Google)", "STOCK_US", "USD", "Busca, IA & Cloud", "US-GOOGL", 176.80, 1.18, 3600000000, 0.45, 24.6, 6.80, 0.20, "2026-09-09", "2026-09-16"),
    ("META", "Meta Platforms Inc.", "STOCK_US", "USD", "Redes Sociais & IA", "US-META", 588.40, 1.45, 3100000000, 0.34, 28.9, 9.20, 0.50, "2026-09-16", "2026-09-26"),
    ("TSLA", "Tesla Inc.", "STOCK_US", "USD", "Veículos Elétricos & Robótica", "US-TSLA", 254.20, 2.10, 4900000000, 0.00, 68.0, 11.40, 0.00, "", ""),
    ("O", "Realty Income Corporation", "STOCK_US", "USD", "REIT Mensal / Renda Imobiliária EUA", "US-O", 59.80, 0.48, 820000000, 5.32, 42.0, 1.35, 0.263, "2026-09-30", "2026-10-15"),
    ("VOO", "Vanguard S&P 500 ETF", "STOCK_US", "USD", "ETF S&P 500 EUA", "US-VOO", 536.20, 0.84, 3200000000, 1.28, 27.5, 4.80, 1.64, "2026-09-26", "2026-10-01"),
    ("QQQ", "Invesco QQQ Trust (Nasdaq-100)", "STOCK_US", "USD", "ETF Tecnologia Nasdaq-100", "US-QQQ", 495.60, 1.12, 2900000000, 0.58, 32.4, 7.60, 0.68, "2026-09-23", "2026-09-30"),

    # Criptomoedas
    ("BTC", "Bitcoin", "CRIPTO", "USD", "Layer 1 / Reserva de Valor Digital", "CRYPTO-BTC", 89450.00, 3.45, 28500000000, 0.0, 0.0, 1.00, 0.00, "", ""),
    ("ETH", "Ethereum", "CRIPTO", "USD", "Layer 1 / Smart Contracts", "CRYPTO-ETH", 3120.00, 2.15, 14200000000, 0.0, 0.0, 1.00, 0.00, "", ""),
    ("SOL", "Solana", "CRIPTO", "USD", "Layer 1 Alta Performance", "CRYPTO-SOL", 198.40, 4.80, 5800000000, 0.0, 0.0, 1.00, 0.00, "", ""),
    ("BNB", "BNB Chain", "CRIPTO", "USD", "Exchange & Smart Chain", "CRYPTO-BNB", 612.50, 1.40, 1800000000, 0.0, 0.0, 1.00, 0.00, "", ""),
    ("XRP", "Ripple XRP", "CRIPTO", "USD", "Pagamentos Globais", "CRYPTO-XRP", 1.12, 2.80, 2400000000, 0.0, 0.0, 1.00, 0.00, "", ""),
]


def init_db():
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS assets_catalog (
        ticker TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        asset_class TEXT NOT NULL,
        currency TEXT NOT NULL DEFAULT 'BRL',
        sector TEXT DEFAULT '',
        cnpj TEXT DEFAULT '',
        last_price REAL DEFAULT 0.0,
        change_pct REAL DEFAULT 0.0,
        volume_day REAL DEFAULT 0.0,
        dy_12m REAL DEFAULT 0.0,
        pl REAL DEFAULT 0.0,
        pvp REAL DEFAULT 1.0,
        last_dividend_per_share REAL DEFAULT 0.0,
        last_div_ex_date TEXT DEFAULT '',
        last_div_pay_date TEXT DEFAULT '',
        updated_at TEXT DEFAULT ''
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL DEFAULT 1,
        tx_date TEXT NOT NULL,
        ticker TEXT NOT NULL,
        asset_class TEXT NOT NULL,
        tx_type TEXT NOT NULL, -- 'BUY' ou 'SELL'
        quantity REAL NOT NULL,
        unit_price REAL NOT NULL,
        fees REAL DEFAULT 0.0,
        currency TEXT DEFAULT 'BRL',
        fx_rate REAL DEFAULT 1.0,
        broker TEXT DEFAULT 'Clear / XP',
        notes TEXT DEFAULT '',
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS fixed_income (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL DEFAULT 1,
        title_name TEXT NOT NULL,
        issuer TEXT NOT NULL,
        asset_class TEXT NOT NULL DEFAULT 'RENDA_FIXA', -- 'RENDA_FIXA' ou 'TESOURO'
        indexer TEXT NOT NULL, -- 'CDI', 'SELIC', 'IPCA', 'PRE'
        rate_value REAL NOT NULL, -- ex: 110 (para 110% CDI), 6.5 (para IPCA + 6.5%), 12.5 (para 12.5% a.a.)
        invested_amount REAL NOT NULL,
        start_date TEXT NOT NULL,
        maturity_date TEXT NOT NULL,
        daily_liquidity INTEGER DEFAULT 1,
        tax_exempt INTEGER DEFAULT 0, -- 1 para LCI/LCA/CRI/CRA, 0 para CDB/Tesouro
        broker TEXT DEFAULT 'Nubank / BTG',
        market_value REAL,
        market_net_value REAL,
        market_value_date TEXT DEFAULT ''
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS dividends_received (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL DEFAULT 1,
        pay_date TEXT NOT NULL,
        ticker TEXT NOT NULL,
        div_type TEXT NOT NULL DEFAULT 'Rendimento / Dividendo',
        amount_per_share REAL NOT NULL,
        shares_qty REAL NOT NULL,
        total_amount REAL NOT NULL,
        currency TEXT DEFAULT 'BRL'
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS allocation_targets (
        user_id INTEGER NOT NULL DEFAULT 1,
        asset_class TEXT NOT NULL,
        target_pct REAL NOT NULL,
        PRIMARY KEY (user_id, asset_class)
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS ai_report_cache (
        ticker TEXT PRIMARY KEY,
        report_title TEXT,
        report_date TEXT,
        report_url TEXT,
        summary_json TEXT,
        updated_at TEXT
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS favorites (
        user_id INTEGER NOT NULL DEFAULT 1,
        ticker TEXT NOT NULL,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (user_id, ticker)
    )
    """)

    # Seed catalog if empty (seed prices have updated_at='' so they are flagged as initial/stale until synced)
    for row in SEED_CATALOG:
        cur.execute("""
        INSERT OR IGNORE INTO assets_catalog (
            ticker, name, asset_class, currency, sector, cnpj,
            last_price, change_pct, volume_day, dy_12m, pl, pvp,
            last_dividend_per_share, last_div_ex_date, last_div_pay_date, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, '')
        """, row)
        # Ensure friendly name & metadata if ticker was previously auto-discovered with raw ticker name
        cur.execute("""
        UPDATE assets_catalog
        SET name = ?, sector = ?, cnpj = ?, pvp = CASE WHEN pvp = 1.0 THEN ? ELSE pvp END
        WHERE ticker = ? AND (name = ticker OR cnpj = '')
        """, (row[1], row[4], row[5], row[11], row[0]))

    # Clean up obsolete / delisted tickers that generate 404s
    cur.execute("""
    DELETE FROM assets_catalog
    WHERE ticker IN ('CPLE6', 'ELET3', 'BCFF11', 'IRDM11')
      AND ticker NOT IN (SELECT DISTINCT ticker FROM transactions)
    """)
    cur.execute("""
    DELETE FROM favorites
    WHERE ticker IN ('CPLE6', 'ELET3', 'BCFF11', 'IRDM11')
      AND ticker NOT IN (SELECT DISTINCT ticker FROM transactions)
    """)

    conn.commit()
    migrate_fixed_income_columns(conn)
    migrate_to_multiuser(conn)

    # Seed default allocation targets
    default_targets = [
        ("ACAO_BR", 25.0),
        ("FII", 25.0),
        ("RENDA_FIXA", 30.0),
        ("TESOURO", 10.0),
        ("STOCK_US", 5.0),
        ("CRIPTO", 5.0),
        ("ETF_BR", 0.0),
    ]
    for cls, pct in default_targets:
        cur.execute("INSERT OR IGNORE INTO allocation_targets (user_id, asset_class, target_pct) VALUES (1, ?, ?)", (cls, pct))

    conn.commit()
    conn.close()
