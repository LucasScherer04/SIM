import os
import sqlite3
import json
from datetime import datetime, date

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "sim_database.db")


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


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

    # Fundos Imobiliários (FIIs - B3)
    ("MXRF11", "Maxi Renda FII", "FII", "BRL", "Papel / Híbrido (CRI)", "97.521.225/0001-25", 9.96, 0.30, 12800000, 12.1, 0.0, 1.02, 0.10, "2026-09-30", "2026-10-15"),
    ("HGLG11", "CSHG Logística FII", "FII", "BRL", "Galpões Logísticos", "11.728.688/0001-47", 158.40, 0.64, 9400000, 8.5, 0.0, 0.99, 1.10, "2026-09-30", "2026-10-15"),
    ("XPML11", "XP Malls FII", "FII", "BRL", "Shoppings", "28.757.546/0001-00", 108.90, -0.45, 14200000, 10.2, 0.0, 0.94, 0.92, "2026-09-30", "2026-10-25"),
    ("KNCR11", "Kinea Rendimentos Imob. FII", "FII", "BRL", "Papel / CRI (Pós CDI)", "16.706.958/0001-32", 104.20, 0.48, 11500000, 11.8, 0.0, 1.03, 1.00, "2026-09-30", "2026-10-14"),
    ("BTLG11", "BTG Pactual Logística FII", "FII", "BRL", "Galpões Logísticos", "11.839.593/0001-09", 99.80, 0.81, 8900000, 9.4, 0.0, 0.96, 0.78, "2026-09-30", "2026-10-25"),
    ("VISC11", "Vinci Shopping Centers FII", "FII", "BRL", "Shoppings", "17.554.274/0001-25", 112.50, -0.88, 6700000, 9.8, 0.0, 0.91, 0.85, "2026-09-30", "2026-10-15"),
    ("XPLG11", "XP Log FII", "FII", "BRL", "Galpões Logísticos", "26.502.794/0001-85", 98.40, 0.20, 6100000, 9.6, 0.0, 0.89, 0.78, "2026-09-30", "2026-10-15"),
    ("CPTS11", "Capitânia Securities II FII", "FII", "BRL", "Papel / CRI (IPCA+)", "18.979.895/0001-13", 7.85, -1.12, 8300000, 11.4, 0.0, 0.88, 0.08, "2026-09-30", "2026-10-18"),
    ("HGRU11", "CSHG Renda Urbana FII", "FII", "BRL", "Renda Urbana / Varejo & Educacional", "29.641.226/0001-53", 123.60, 0.55, 5800000, 9.1, 0.0, 0.97, 0.85, "2026-09-30", "2026-10-15"),
    ("KNRI11", "Kinea Renda Imobiliária FII", "FII", "BRL", "Híbrido (Lajes + Logística)", "12.005.956/0001-65", 148.90, 0.15, 7200000, 8.1, 0.0, 0.92, 1.00, "2026-09-30", "2026-10-15"),

    # ETFs & BDRs (B3)
    ("IVVB11", "iShares S&P 500 B3 ETF", "ETF_BR", "BRL", "ETF Internacional S&P 500", "19.909.560/0001-91", 358.00, 1.25, 95000000, 0.0, 0.0, 1.00, 0.00, "", ""),
    ("BOVA11", "iShares Ibovespa ETF", "ETF_BR", "BRL", "ETF Índice Ibovespa", "10.406.511/0001-61", 128.40, 0.72, 410000000, 0.0, 0.0, 1.00, 0.00, "", ""),
    ("DIVO11", "It Now IDIV Dividendos ETF", "ETF_BR", "BRL", "ETF Índice Dividendos", "13.974.750/0001-06", 94.20, 0.88, 18000000, 0.0, 0.0, 1.00, 0.00, "", ""),

    # Stocks EUA & ETFs Globais
    ("NVDA", "NVIDIA Corporation", "STOCK_US", "USD", "Semicondutores & IA", "US-NVDA", 138.60, 2.85, 8900000000, 0.03, 52.4, 42.10, 0.01, "2026-09-05", "2026-09-26"),
    ("AAPL", "Apple Inc.", "STOCK_US", "USD", "Tecnologia & Consumo", "US-AAPL", 231.40, 1.10, 5400000000, 0.44, 34.8, 45.20, 0.25, "2026-08-12", "2026-08-15"),
    ("MSFT", "Microsoft Corporation", "STOCK_US", "USD", "Cloud & Software", "US-MSFT", 428.90, 0.92, 4800000000, 0.72, 35.1, 12.80, 0.83, "2026-08-15", "2026-09-12"),
    ("AMZN", "Amazon.com Inc.", "STOCK_US", "USD", "E-Commerce & AWS Cloud", "US-AMZN", 204.50, 1.64, 4100000000, 0.00, 41.2, 8.40, 0.00, "", ""),
    ("VOO", "Vanguard S&P 500 ETF", "STOCK_US", "USD", "ETF S&P 500 EUA", "US-VOO", 536.20, 0.84, 3200000000, 1.28, 27.5, 4.80, 1.64, "2026-09-26", "2026-10-01"),

    # Criptomoedas
    ("BTC", "Bitcoin", "CRIPTO", "USD", "Layer 1 / Reserva de Valor Digital", "CRYPTO-BTC", 89450.00, 3.45, 28500000000, 0.0, 0.0, 1.00, 0.00, "", ""),
    ("ETH", "Ethereum", "CRIPTO", "USD", "Layer 1 / Smart Contracts", "CRYPTO-ETH", 3120.00, 2.15, 14200000000, 0.0, 0.0, 1.00, 0.00, "", ""),
    ("SOL", "Solana", "CRIPTO", "USD", "Layer 1 Alta Performance", "CRYPTO-SOL", 198.40, 4.80, 5800000000, 0.0, 0.0, 1.00, 0.00, "", ""),
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
        broker TEXT DEFAULT 'Nubank / BTG'
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS dividends_received (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
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
        asset_class TEXT PRIMARY KEY,
        target_pct REAL NOT NULL
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

    # Seed catalog if empty
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    for row in SEED_CATALOG:
        cur.execute("""
        INSERT OR IGNORE INTO assets_catalog (
            ticker, name, asset_class, currency, sector, cnpj,
            last_price, change_pct, volume_day, dy_12m, pl, pvp,
            last_dividend_per_share, last_div_ex_date, last_div_pay_date, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (*row, now_str))

    # Seed default allocation targets
    default_targets = [
        ("ACAO_BR", 25.0),
        ("FII", 25.0),
        ("RENDA_FIXA", 30.0),
        ("STOCK_US", 10.0),
        ("CRIPTO", 5.0),
        ("ETF_BR", 5.0),
    ]
    for cls, pct in default_targets:
        cur.execute("INSERT OR IGNORE INTO allocation_targets (asset_class, target_pct) VALUES (?, ?)", (cls, pct))

    # Seed sample transactions if database is brand new so the user sees a complete working portfolio out of the box
    tx_count = cur.execute("SELECT COUNT(*) FROM transactions").fetchone()[0]
    fi_count = cur.execute("SELECT COUNT(*) FROM fixed_income").fetchone()[0]

    if tx_count == 0 and fi_count == 0:
        sample_txs = [
            ("2026-01-15", "PETR4", "ACAO_BR", "BUY", 100, 34.20, 0.0, "BRL", 1.0, "XP Investimentos", "Aporte inicial"),
            ("2026-03-10", "WEGE3", "ACAO_BR", "BUY", 60, 46.50, 0.0, "BRL", 1.0, "XP Investimentos", "Aporte longo prazo"),
            ("2026-04-05", "ITUB4", "ACAO_BR", "BUY", 100, 32.80, 0.0, "BRL", 1.0, "BTG Pactual", "Bancos"),
            ("2026-02-12", "MXRF11", "FII", "BUY", 350, 9.75, 0.0, "BRL", 1.0, "XP Investimentos", "FII Papel"),
            ("2026-03-18", "HGLG11", "FII", "BUY", 25, 154.00, 0.0, "BRL", 1.0, "XP Investimentos", "FII Logística"),
            ("2026-05-20", "XPML11", "FII", "BUY", 30, 105.50, 0.0, "BRL", 1.0, "BTG Pactual", "FII Shopping"),
            ("2026-06-10", "NVDA", "STOCK_US", "BUY", 4.5, 118.00, 0.0, "USD", 5.65, "Avenue", "IA & Semicondutores"),
            ("2026-07-01", "BTC", "CRIPTO", "BUY", 0.015, 76500.00, 0.0, "USD", 5.70, "Binance", "Reserva Bitcoin"),
        ]
        cur.executemany("""
        INSERT INTO transactions (tx_date, ticker, asset_class, tx_type, quantity, unit_price, fees, currency, fx_rate, broker, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, sample_txs)

        sample_fi = [
            ("Caixinha Reserva de Emergência", "Nubank", "RENDA_FIXA", "CDI", 100.0, 8500.00, "2025-11-10", "2028-11-10", 1, 0, "Nubank"),
            ("LCI Banco Inter 94% CDI", "Banco Inter", "RENDA_FIXA", "CDI", 94.0, 5000.00, "2026-02-01", "2027-08-01", 0, 1, "Banco Inter"),
            ("Tesouro IPCA+ 2029", "Tesouro Nacional", "TESOURO", "IPCA", 6.35, 4200.00, "2026-01-20", "2029-05-15", 1, 0, "BTG Pactual"),
        ]
        cur.executemany("""
        INSERT INTO fixed_income (title_name, issuer, asset_class, indexer, rate_value, invested_amount, start_date, maturity_date, daily_liquidity, tax_exempt, broker)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, sample_fi)

        sample_divs = [
            ("2026-08-15", "MXRF11", "Rendimento FII", 0.10, 350, 35.00, "BRL"),
            ("2026-08-15", "HGLG11", "Rendimento FII", 1.10, 25, 27.50, "BRL"),
            ("2026-08-25", "XPML11", "Rendimento FII", 0.92, 30, 27.60, "BRL"),
            ("2026-09-15", "MXRF11", "Rendimento FII", 0.10, 350, 35.00, "BRL"),
            ("2026-09-15", "HGLG11", "Rendimento FII", 1.10, 25, 27.50, "BRL"),
            ("2026-09-20", "PETR4", "Dividendo / JCP", 0.92, 100, 92.00, "BRL"),
            ("2026-09-25", "XPML11", "Rendimento FII", 0.92, 30, 27.60, "BRL"),
            ("2026-10-15", "MXRF11", "Rendimento FII", 0.10, 350, 35.00, "BRL"),
            ("2026-10-15", "HGLG11", "Rendimento FII", 1.10, 25, 27.50, "BRL"),
            ("2026-10-15", "WEGE3", "Dividendo", 0.24, 60, 14.40, "BRL"),
            ("2026-10-25", "XPML11", "Rendimento FII", 0.92, 30, 27.60, "BRL"),
        ]
        cur.executemany("""
        INSERT INTO dividends_received (pay_date, ticker, div_type, amount_per_share, shares_qty, total_amount, currency)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """, sample_divs)

    conn.commit()
    conn.close()
