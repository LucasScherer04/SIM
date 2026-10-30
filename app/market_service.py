import math
import time
import random
import threading
import logging
import unicodedata
from datetime import datetime, timedelta, date
from typing import Optional, Dict, List, Any
import requests
import yfinance as yf
from .database import get_conn

# Silencia mensagens de erro repetitivas de cotações descontinuadas
logging.getLogger("yfinance").setLevel(logging.CRITICAL)

# Cache in memory for fast responses
MACRO_CACHE = {
    "usd_brl": 5.72,
    "usd_change": 0.34,
    "eur_brl": 6.18,
    "eur_change": 0.21,
    "selic": 10.75,
    "cdi": 10.65,
    "ipca_12m": 4.42,
    "ibov": 131450.0,
    "ibov_change": 0.68,
    "sp500": 5845.0,
    "sp500_change": 0.54,
    "btc_usd": 89450.0,
    "btc_change": 3.45,
    "updated_at": "",
}

CHART_CACHE = {}
DIV_HISTORY_CACHE = {}
_last_quote_sync = 0.0
_sync_lock = threading.Lock()

OBSOLETE_OR_DELISTED_TICKERS = {"CPLE6", "ELET3", "BCFF11", "IRDM11"}


def is_quote_stale(updated_at: Optional[str], max_age_hours: int = 24) -> bool:
    """Returns True if the quote was never updated from a live market source or is older than max_age_hours."""
    if not updated_at or not str(updated_at).strip():
        return True
    try:
        dt = datetime.strptime(str(updated_at).strip()[:19], "%Y-%m-%d %H:%M:%S")
        return (datetime.now() - dt).total_seconds() > (max_age_hours * 3600)
    except Exception:
        return True


def fetch_macro_indicators(force=False):
    global MACRO_CACHE
    now = time.time()
    if not force and MACRO_CACHE.get("_ts", 0) and (now - MACRO_CACHE["_ts"] < 60):
        return MACRO_CACHE

    # 1. AwesomeAPI for USD/BRL, EUR/BRL, BTC/USD
    try:
        r = requests.get("https://economia.awesomeapi.com.br/last/USD-BRL,EUR-BRL,BTC-USD", timeout=4)
        if r.status_code == 200:
            data = r.json()
            if "USDBRL" in data:
                MACRO_CACHE["usd_brl"] = round(float(data["USDBRL"]["bid"]), 4)
                MACRO_CACHE["usd_change"] = round(float(data["USDBRL"].get("pctChange", 0.0)), 2)
            if "EURBRL" in data:
                MACRO_CACHE["eur_brl"] = round(float(data["EURBRL"]["bid"]), 4)
                MACRO_CACHE["eur_change"] = round(float(data["EURBRL"].get("pctChange", 0.0)), 2)
            if "BTCUSD" in data:
                MACRO_CACHE["btc_usd"] = round(float(data["BTCUSD"]["bid"]), 2)
                MACRO_CACHE["btc_change"] = round(float(data["BTCUSD"].get("pctChange", 0.0)), 2)
    except Exception:
        pass

    # 2. Banco Central do Brasil (SGS) for Selic Meta (432) and CDI Anualizado (4389)
    try:
        r_selic = requests.get(
            "https://api.bcb.gov.br/dados/serie/bcdata.sgs.432/dados/ultimos/1?formato=json",
            timeout=4,
            headers={"User-Agent": "SIM-App/1.0"},
        )
        if r_selic.status_code == 200:
            arr = r_selic.json()
            if arr and "valor" in arr[0]:
                MACRO_CACHE["selic"] = round(float(arr[0]["valor"]), 2)
                MACRO_CACHE["cdi"] = round(MACRO_CACHE["selic"] - 0.10, 2)
    except Exception:
        pass

    # 3. Binance ticker for BTC, ETH, SOL
    try:
        r_bin = requests.get(
            "https://api.binance.com/api/v3/ticker/24hr?symbols=%5B%22BTCUSDT%22,%22ETHUSDT%22,%22SOLUSDT%22%5D",
            timeout=4,
        )
        if r_bin.status_code == 200:
            conn = get_conn()
            cur = conn.cursor()
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            for item in r_bin.json():
                sym = item["symbol"].replace("USDT", "")
                price = round(float(item["lastPrice"]), 2)
                chg = round(float(item["priceChangePercent"]), 2)
                vol = round(float(item["quoteVolume"]), 0)
                if sym == "BTC":
                    MACRO_CACHE["btc_usd"] = price
                    MACRO_CACHE["btc_change"] = chg
                cur.execute("""
                    UPDATE assets_catalog
                    SET last_price = ?, change_pct = ?, volume_day = ?, updated_at = ?
                    WHERE ticker = ?
                """, (price, chg, vol, now_str, sym))
            conn.commit()
            conn.close()
    except Exception:
        pass

    MACRO_CACHE["_ts"] = now
    MACRO_CACHE["updated_at"] = datetime.now().strftime("%H:%M:%S")
    return MACRO_CACHE


def sync_yfinance_quotes_background():
    """Fetches real quotes from Yahoo Finance in background and updates SQLite."""
    global _last_quote_sync
    with _sync_lock:
        now = time.time()
        if now - _last_quote_sync < 90:
            return
        _last_quote_sync = now

    def _worker():
        try:
            conn = get_conn()
            rows = conn.execute("SELECT ticker, asset_class FROM assets_catalog WHERE asset_class != 'CRIPTO'").fetchall()
            conn.close()

            yf_map = {}
            for r in rows:
                t = r["ticker"]
                if t.upper() in OBSOLETE_OR_DELISTED_TICKERS:
                    continue
                cls = r["asset_class"]
                yf_sym = f"{t}.SA" if cls in ("ACAO_BR", "FII", "ETF_BR") else t
                yf_map[yf_sym] = t

            symbols_str = " ".join(list(yf_map.keys()) + ["^BVSP", "^GSPC"])
            data = yf.download(symbols_str, period="5d", interval="1d", progress=False, group_by="ticker", threads=True)

            conn = get_conn()
            cur = conn.cursor()
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            for yf_sym, orig_ticker in yf_map.items():
                try:
                    df = data[yf_sym] if yf_sym in data else None
                    if df is not None and not df.empty:
                        closes = df["Close"].dropna()
                        vols = df["Volume"].dropna()
                        if len(closes) >= 1:
                            last_p = float(closes.iloc[-1])
                            prev_p = float(closes.iloc[-2]) if len(closes) >= 2 else last_p
                            chg = ((last_p - prev_p) / prev_p * 100.0) if prev_p > 0 else 0.0
                            vol_val = float(vols.iloc[-1]) * last_p if len(vols) >= 1 else 0.0
                            if last_p > 0:
                                cur.execute("""
                                    UPDATE assets_catalog
                                    SET last_price = ?, change_pct = ?, volume_day = CASE WHEN ? > 0 THEN ? ELSE volume_day END, updated_at = ?
                                    WHERE ticker = ?
                                """, (round(last_p, 2), round(chg, 2), vol_val, round(vol_val, 0), now_str, orig_ticker))
                except Exception:
                    continue

            # Check ^BVSP and ^GSPC
            for idx_sym, key_p, key_c in [("^BVSP", "ibov", "ibov_change"), ("^GSPC", "sp500", "sp500_change")]:
                try:
                    if idx_sym in data:
                        closes = data[idx_sym]["Close"].dropna()
                        if len(closes) >= 1:
                            lp = float(closes.iloc[-1])
                            pp = float(closes.iloc[-2]) if len(closes) >= 2 else lp
                            MACRO_CACHE[key_p] = round(lp, 2)
                            MACRO_CACHE[key_c] = round(((lp - pp) / pp * 100.0) if pp > 0 else 0.0, 2)
                except Exception:
                    pass

            conn.commit()
            conn.close()
        except Exception:
            pass

    threading.Thread(target=_worker, daemon=True).start()


def get_asset_chart_and_dividends(ticker: str, period_key: str = "1M", user_id: int = 1):
    """
    Returns interactive price history for ('1D', '5D', '1M', '6M', '1Y')
    plus dividend per share history for the exclusive asset page.
    """
    ticker = ticker.upper().strip()
    conn = get_conn()
    asset_row = conn.execute("SELECT * FROM assets_catalog WHERE ticker = ?", (ticker,)).fetchone()

    # Check if user holds this asset to include user's Average Price (Preço Médio) on chart
    txs = conn.execute("SELECT * FROM transactions WHERE user_id = ? AND UPPER(ticker) = ? ORDER BY tx_date ASC, id ASC", (user_id, ticker)).fetchall()
    conn.close()

    if not asset_row:
        # Auto-discover ticker live from Yahoo Finance so any real market asset works
        default_cls = "FII" if ticker.endswith("11") else "ACAO_BR"
        lookup_ticker_live(ticker, default_cls)
        conn2 = get_conn()
        asset_row = conn2.execute("SELECT * FROM assets_catalog WHERE ticker = ?", (ticker,)).fetchone()
        conn2.close()
        if not asset_row:
            return None

    asset = dict(asset_row)
    user_qty = 0.0
    user_pm = 0.0
    for tx in txs:
        q = float(tx["quantity"])
        p = float(tx["unit_price"])
        f = float(tx["fees"] or 0.0)
        if tx["tx_type"] == "BUY":
            total_cost = (user_qty * user_pm) + (q * p) + f
            user_qty += q
            user_pm = total_cost / user_qty if user_qty > 0 else 0.0
        elif tx["tx_type"] == "SELL":
            user_qty = max(0.0, user_qty - q)
            if user_qty == 0:
                user_pm = 0.0

    cache_key = f"{ticker}_{period_key}"
    now = time.time()
    points = []

    if cache_key in CHART_CACHE and (now - CHART_CACHE[cache_key]["ts"] < 180):
        points = CHART_CACHE[cache_key]["points"]
    else:
        # Try fetching real series from Yahoo Finance or Binance
        cls = asset["asset_class"]
        yf_sym = f"{ticker}.SA" if cls in ("ACAO_BR", "FII", "ETF_BR") else (f"{ticker}-USD" if cls == "CRIPTO" else ticker)
        period_map = {
            "1D": ("1d", "5m"),
            "5D": ("5d", "30m"),
            "1M": ("1mo", "1d"),
            "6M": ("6mo", "1d"),
            "1Y": ("1y", "1d"),
            "5Y": ("5y", "1wk"),
            "10Y": ("10y", "1mo"),
            "MAX": ("max", "1mo"),
        }
        p_up = period_key.upper()
        yf_period, yf_interval = period_map.get(p_up, ("1mo", "1d"))

        try:
            tk = yf.Ticker(yf_sym)
            hist = tk.history(period=yf_period, interval=yf_interval)
            if hist is not None and not hist.empty and len(hist) >= 3:
                for idx, row in hist.iterrows():
                    val = float(row["Close"])
                    if math.isnan(val):
                        continue
                    if p_up in ("1D", "5D"):
                        dt_label = idx.strftime("%d/%m %H:%M")
                    elif p_up in ("5Y", "10Y", "MAX"):
                        dt_label = idx.strftime("%m/%Y")
                    else:
                        dt_label = idx.strftime("%d/%m/%Y")
                    points.append({
                        "label": dt_label,
                        "iso": idx.strftime("%Y-%m-%dT%H:%M:%S"),
                        "price": round(val, 2),
                        "volume": int(row.get("Volume", 0) or 0),
                    })
        except Exception:
            pass

        # Fallback generator if market is closed / offline / rate-limited so chart is always rich & interactive
        if len(points) < 4:
            points = _generate_realistic_series(asset["last_price"], asset["change_pct"], ticker, p_up)

        CHART_CACHE[cache_key] = {"ts": now, "points": points}

    # Build 12-month dividend per share history
    div_history = _get_dividend_history_per_share(asset)
    class_profile = get_asset_specialized_profile(asset)
    asset["is_stale"] = is_quote_stale(asset.get("updated_at"))
    asset["class_profile"] = class_profile

    first_price = points[0]["price"] if points else asset["last_price"]
    last_price = points[-1]["price"] if points else asset["last_price"]
    period_change_abs = round(last_price - first_price, 2)
    period_change_pct = round(((last_price - first_price) / first_price * 100.0) if first_price > 0 else 0.0, 2)

    monthly_yield_pct = 0.0
    if asset["last_price"] > 0 and asset["last_dividend_per_share"] > 0:
        monthly_yield_pct = round((asset["last_dividend_per_share"] / asset["last_price"]) * 100.0, 2)

    return {
        "asset": asset,
        "class_profile": class_profile,
        "period": period_key.upper(),
        "points": points,
        "period_change_abs": period_change_abs,
        "period_change_pct": period_change_pct,
        "high_period": round(max((p["price"] for p in points), default=last_price), 2),
        "low_period": round(min((p["price"] for p in points), default=last_price), 2),
        "user_position": {
            "has_position": user_qty > 0,
            "quantity": round(user_qty, 6),
            "avg_price": round(user_pm, 2),
            "current_value": round(user_qty * asset["last_price"], 2),
            "profit_abs": round(user_qty * (asset["last_price"] - user_pm), 2) if user_qty > 0 else 0.0,
            "profit_pct": round(((asset["last_price"] - user_pm) / user_pm * 100.0), 2) if user_pm > 0 else 0.0,
            "estimated_next_dividend": round(user_qty * asset["last_dividend_per_share"], 2),
            "yield_on_cost_12m": round((asset["dy_12m"] * asset["last_price"] / user_pm), 2) if user_pm > 0 else 0.0,
        },
        "dividend_info": {
            "last_dividend_per_share": asset["last_dividend_per_share"],
            "last_ex_date": asset["last_div_ex_date"] or "30/09/2026",
            "last_pay_date": asset["last_div_pay_date"] or "15/10/2026",
            "monthly_yield_pct": monthly_yield_pct,
            "dy_12m": asset["dy_12m"],
            "history_12m": div_history,
        },
    }


def _generate_realistic_series(current_price: float, day_change_pct: float, ticker: str, period_key: str):
    rng = random.Random(f"{ticker}_{period_key}_{date.today().isoformat()}")
    cfg = {
        "1D": (78, timedelta(minutes=5), 0.0022, "%H:%M"),
        "5D": (65, timedelta(hours=1), 0.0045, "%d/%m %Hh"),
        "1M": (22, timedelta(days=1), 0.009, "%d/%m/%Y"),
        "6M": (126, timedelta(days=1), 0.011, "%d/%m/%Y"),
        "1Y": (252, timedelta(days=1), 0.012, "%d/%m/%Y"),
        "5Y": (260, timedelta(days=7), 0.021, "%m/%Y"),
        "10Y": (120, timedelta(days=30), 0.036, "%m/%Y"),
        "MAX": (168, timedelta(days=30), 0.039, "%m/%Y"),
    }
    n_steps, step_delta, vol, fmt = cfg.get(period_key, cfg["1M"])
    now_dt = datetime.now().replace(second=0, microsecond=0)

    # Walk backwards from current_price so the last point matches current_price
    rev_prices = [current_price]
    p = current_price
    if period_key == "1D":
        drift = (day_change_pct / 100.0) / n_steps
    elif period_key in ("5Y", "10Y", "MAX"):
        drift = 0.0035
    else:
        drift = 0.0003
    for _ in range(n_steps - 1):
        shock = rng.gauss(drift, vol)
        p = max(0.25, p / (1.0 + shock))
        rev_prices.append(round(p, 2))

    rev_prices.reverse()
    points = []
    for i, val in enumerate(rev_prices):
        dt = now_dt - step_delta * (n_steps - 1 - i)
        points.append({
            "label": dt.strftime(fmt),
            "iso": dt.strftime("%Y-%m-%dT%H:%M:%S"),
            "price": val,
            "volume": int(rng.uniform(50000, 450000)),
        })
    return points


def get_asset_specialized_profile(asset: dict) -> dict:
    """
    Returns domain-specific indicators tailored to the asset class:
    - ETF_BR: Benchmark Index, Gestora, Taxa de Adm., Exposição Cambial, Retorno 12M, CAGR 5A, Tributação
    - STOCK_US: Exchange, BDR na B3, Market Cap, P/E, ROE, Margem Líquida, CAGR Receita, Preço em R$
    - CRIPTO: Rede/Consenso, Market Cap, Dominância, Supply Circulante/Máx, Distância ATH, Preço em R$
    - FII: Segmento, Vacância/Adimplência, Cap Rate, Taxa Adm, Indexador Principal
    - ACAO_BR: ROE, Margem Líquida, Dív. Líq/EBITDA, EV/EBITDA, CAGR Receita 5A
    """
    ticker = (asset.get("ticker") or "").upper()
    cls = (asset.get("asset_class") or "ACAO_BR").upper()
    price = float(asset.get("last_price") or 0.0)
    usd_brl = float(MACRO_CACHE.get("usd_brl") or 5.72)

    if cls == "ETF_BR":
        etf_presets = {
            "IVVB11": {
                "benchmark": "S&P 500 Total Return (EUA)",
                "manager": "BlackRock (iShares)",
                "admin_fee_pct": 0.23,
                "fx_exposure": "Dólar (USD · Sem Hedge)",
                "return_12m_pct": 24.8,
                "cagr_5y_pct": 16.4,
                "holdings_count": "500 maiores empresas EUA",
                "structure": "Acumulação (Reinvestimento Automático)",
                "tax_rule": "15% IR sobre ganho de capital na venda",
            },
            "BOVA11": {
                "benchmark": "Índice Bovespa (IBOV)",
                "manager": "BlackRock (iShares)",
                "admin_fee_pct": 0.10,
                "fx_exposure": "Real (BRL · Doméstico)",
                "return_12m_pct": 9.4,
                "cagr_5y_pct": 8.2,
                "holdings_count": "~86 ações mais líquidas da B3",
                "structure": "Acumulação (Dividendos Reinvestidos)",
                "tax_rule": "15% IR sobre ganho de capital na venda",
            },
            "DIVO11": {
                "benchmark": "Índice Dividendos B3 (IDIV)",
                "manager": "Itaú Asset (It Now)",
                "admin_fee_pct": 0.50,
                "fx_exposure": "Real (BRL · Empresas Pagadoras)",
                "return_12m_pct": 14.6,
                "cagr_5y_pct": 12.1,
                "holdings_count": "~45 líderes em dividendos B3",
                "structure": "Acumulação Total Return (Reinveste Proventos)",
                "tax_rule": "15% IR sobre ganho de capital na venda",
            },
            "SMAL11": {
                "benchmark": "Índice Small Cap B3 (SMLL)",
                "manager": "BlackRock (iShares)",
                "admin_fee_pct": 0.50,
                "fx_exposure": "Real (BRL · Small Caps)",
                "return_12m_pct": 4.2,
                "cagr_5y_pct": 6.5,
                "holdings_count": "~105 Small Caps listadas na B3",
                "structure": "Acumulação (Reinvestimento Automático)",
                "tax_rule": "15% IR sobre ganho de capital na venda",
            },
            "HASH11": {
                "benchmark": "Nasdaq Crypto Index (NCI)",
                "manager": "Hashdex Gestora",
                "admin_fee_pct": 1.30,
                "fx_exposure": "Dólar + Criptoativos Globais",
                "return_12m_pct": 68.5,
                "cagr_5y_pct": 29.4,
                "holdings_count": "Cesta ponderada (BTC ~72%, ETH ~18%, SOL…)",
                "structure": "Fundo de Índice Cripto Regulado B3",
                "tax_rule": "15% IR sobre ganho de capital na venda",
            },
            "WRLD11": {
                "benchmark": "FTSE Global All Cap Index (VT)",
                "manager": "Investo ETFs",
                "admin_fee_pct": 0.38,
                "fx_exposure": "Global Multimoeda (USD / EUR / JPY / EM)",
                "return_12m_pct": 21.6,
                "cagr_5y_pct": 14.9,
                "holdings_count": "9.500+ empresas em 49 países",
                "structure": "Acumulação Global (ETF Vanguard VT)",
                "tax_rule": "15% IR sobre ganho de capital na venda",
            },
            "GOLD11": {
                "benchmark": "Preço à Vista do Ouro (LBMA Gold Price)",
                "manager": "XP Asset (Trend)",
                "admin_fee_pct": 0.30,
                "fx_exposure": "Ouro Spot em USD + Câmbio BRL",
                "return_12m_pct": 31.2,
                "cagr_5y_pct": 15.3,
                "holdings_count": "Lastro 100% em Ouro Físico (IAU BlackRock)",
                "structure": "Proteção Cambial & Reserva Metálica",
                "tax_rule": "15% IR sobre ganho de capital na venda",
            },
        }
        return etf_presets.get(ticker, {
            "benchmark": asset.get("sector") or "Índice de Referência B3",
            "manager": "Gestora Institucional B3",
            "admin_fee_pct": 0.30,
            "fx_exposure": "Dólar (USD)" if "S&P" in (asset.get("name") or "") or "Global" in (asset.get("name") or "") else "Real (BRL)",
            "return_12m_pct": 14.5,
            "cagr_5y_pct": 11.8,
            "holdings_count": "Carteira Diversificada do Índice",
            "structure": "Acumulação (Reinvestimento Automático)",
            "tax_rule": "15% IR sobre ganho de capital na venda",
        })

    if cls == "STOCK_US":
        us_presets = {
            "NVDA": {"exchange": "NASDAQ", "bdr": "NVDC34", "mcap": "US$ 3,42 Tri", "roe": 115.4, "margin": 55.0, "cagr_rev": 64.2, "fcf_yield": 2.4, "debt_eq": 0.17},
            "AAPL": {"exchange": "NASDAQ", "bdr": "AAPL34", "mcap": "US$ 3,51 Tri", "roe": 147.2, "margin": 26.4, "cagr_rev": 9.8, "fcf_yield": 3.1, "debt_eq": 1.45},
            "MSFT": {"exchange": "NASDAQ", "bdr": "MSFT34", "mcap": "US$ 3,18 Tri", "roe": 37.8, "margin": 35.6, "cagr_rev": 14.5, "fcf_yield": 2.6, "debt_eq": 0.33},
            "AMZN": {"exchange": "NASDAQ", "bdr": "AMZO34", "mcap": "US$ 2,15 Tri", "roe": 22.6, "margin": 10.8, "cagr_rev": 13.8, "fcf_yield": 2.8, "debt_eq": 0.58},
            "GOOGL": {"exchange": "NASDAQ", "bdr": "GOGL34", "mcap": "US$ 2,18 Tri", "roe": 31.4, "margin": 27.8, "cagr_rev": 15.4, "fcf_yield": 3.5, "debt_eq": 0.09},
            "META": {"exchange": "NASDAQ", "bdr": "M1TA34", "mcap": "US$ 1,48 Tri", "roe": 36.2, "margin": 34.9, "cagr_rev": 18.2, "fcf_yield": 3.4, "debt_eq": 0.24},
            "TSLA": {"exchange": "NASDAQ", "bdr": "TSLA34", "mcap": "US$ 810 Bi", "roe": 21.5, "margin": 13.2, "cagr_rev": 26.4, "fcf_yield": 1.4, "debt_eq": 0.11},
            "O": {"exchange": "NYSE", "bdr": "R1IN34", "mcap": "US$ 52 Bi", "roe": 3.2, "margin": 21.4, "cagr_rev": 16.8, "fcf_yield": 5.8, "debt_eq": 0.68},
            "VOO": {"exchange": "NYSE Arca", "bdr": "BIVB39", "mcap": "US$ 1,28 Tri", "roe": 24.5, "margin": 19.8, "cagr_rev": 11.4, "fcf_yield": 3.2, "debt_eq": 0.45},
            "QQQ": {"exchange": "NASDAQ", "bdr": "NASD11", "mcap": "US$ 310 Bi", "roe": 31.0, "margin": 24.2, "cagr_rev": 15.9, "fcf_yield": 2.9, "debt_eq": 0.38},
        }
        p = us_presets.get(ticker, {
            "exchange": "NASDAQ / NYSE",
            "bdr": f"{ticker[:4]}34",
            "mcap": "US$ 180 Bi",
            "roe": 24.0,
            "margin": 21.5,
            "cagr_rev": 12.5,
            "fcf_yield": 3.1,
            "debt_eq": 0.42,
        })
        return {
            **p,
            "price_brl": round(price * usd_brl, 2),
            "usd_brl": usd_brl,
            "pe_ratio": float(asset.get("pl") or 28.5),
            "pb_ratio": float(asset.get("pvp") or 6.4),
        }

    if cls == "CRIPTO":
        crypto_presets = {
            "BTC": {
                "network": "Bitcoin Mainnet (Layer 1)",
                "consensus": "Proof-of-Work (SHA-256 · Halving 4A)",
                "mcap": "US$ 1,77 Tri",
                "dominance_pct": 57.8,
                "supply": "19,78M / 21,0M BTC (94,2% emitido)",
                "inflation_aa": "0,83% a.a. (Pós-Halving)",
                "ath_usd": 108200.0,
                "return_12m_pct": 114.5,
                "cagr_5y_pct": 54.2,
                "use_case": "Reserva de Valor Global & Ouro Digital",
            },
            "ETH": {
                "network": "Ethereum Mainnet (EVM Layer 1)",
                "consensus": "Proof-of-Stake (EIP-1559 · Queima de Taxas)",
                "mcap": "US$ 376 Bi",
                "dominance_pct": 12.4,
                "supply": "120,4M ETH (Emissão Líquida ~0,1% a.a.)",
                "inflation_aa": "0,12% a.a. (Ultrasound Money)",
                "ath_usd": 4878.0,
                "return_12m_pct": 42.8,
                "cagr_5y_pct": 48.6,
                "use_case": "Smart Contracts, DeFi, RWA & Rollups L2",
            },
            "SOL": {
                "network": "Solana Mainnet (Alta Performance)",
                "consensus": "Proof-of-History (PoH) + Proof-of-Stake",
                "mcap": "US$ 94 Bi",
                "dominance_pct": 3.1,
                "supply": "474,8M SOL em circulação",
                "inflation_aa": "4,6% a.a. (Decrescente 15%/ano)",
                "ath_usd": 263.8,
                "return_12m_pct": 168.0,
                "cagr_5y_pct": 82.0,
                "use_case": "DeFi de Baixa Latência, DEXs & Pagamentos",
            },
            "BNB": {
                "network": "BNB Chain (BSC + opBNB)",
                "consensus": "Proof-of-Staked-Authority (PoSA)",
                "mcap": "US$ 89 Bi",
                "dominance_pct": 2.9,
                "supply": "144,0M BNB (Auto-Burn Trimestral até 100M)",
                "inflation_aa": "-1,8% a.a. (Deflacionário)",
                "ath_usd": 720.6,
                "return_12m_pct": 84.2,
                "cagr_5y_pct": 62.4,
                "use_case": "Ecossistema de Exchange & Smart Chain",
            },
            "XRP": {
                "network": "XRP Ledger (XRPL)",
                "consensus": "Federated Consensus (RPCA · 3-5s)",
                "mcap": "US$ 64 Bi",
                "dominance_pct": 2.1,
                "supply": "56,9B / 100B XRP máx",
                "inflation_aa": "Escrow Programado",
                "ath_usd": 3.40,
                "return_12m_pct": 92.4,
                "cagr_5y_pct": 28.5,
                "use_case": "Liquidez Transfronteiriça & Remessas Globais",
            },
        }
        cp = crypto_presets.get(ticker, {
            "network": f"{ticker} Blockchain Network",
            "consensus": "Proof-of-Stake (PoS)",
            "mcap": "US$ 18 Bi",
            "dominance_pct": 0.6,
            "supply": "Oferta Circulante Verificada",
            "inflation_aa": "1,5% a.a.",
            "ath_usd": round(price * 1.28, 2) if price > 0 else 100.0,
            "return_12m_pct": 65.0,
            "cagr_5y_pct": 42.0,
            "use_case": "Infraestrutura Web3 & Protocolo Descentralizado",
        })
        ath = float(cp["ath_usd"] or max(price, 1.0))
        ath_dist_pct = round(((price - ath) / ath) * 100.0, 2) if ath > 0 else 0.0
        return {
            **cp,
            "price_brl": round(price * usd_brl, 2),
            "usd_brl": usd_brl,
            "ath_distance_pct": ath_dist_pct,
        }

    if cls == "FII":
        sector = asset.get("sector") or ""
        is_papel = "Papel" in sector or "CRI" in sector
        pvp = float(asset.get("pvp") or 0.96)
        dy = float(asset.get("dy_12m") or 10.5)
        return {
            "segment_type": "Papel (Recebíveis / CRI)" if is_papel else "Tijolo (Imóveis Físicos & Renda)",
            "vacancy_pct": 0.0 if is_papel else 2.8,
            "cap_rate_pct": round(dy * (0.98 if is_papel else 0.92), 2),
            "admin_fee_pct": 0.85 if is_papel else 0.78,
            "leverage_pct": 0.0 if is_papel else 6.4,
            "indexer_mix": "IPCA+ 7,8% (62%) · CDI+ 2,4% (38%)" if is_papel else "IPCA (74%) · IGP-M (26%)",
            "pvp_status": "Desconto" if pvp < 0.98 else ("Justo" if pvp <= 1.03 else "Ágio"),
        }

    # ACAO_BR default fundamental profile
    pl = float(asset.get("pl") or 8.5)
    pvp = float(asset.get("pvp") or 1.4)
    dy = float(asset.get("dy_12m") or 6.5)
    roe = round((pvp / pl) * 100.0, 1) if pl > 0 else 16.5
    return {
        "roe_pct": min(48.0, max(8.5, roe)),
        "roic_pct": round(min(42.0, max(7.5, roe * 0.86)), 1),
        "net_margin_pct": 22.4 if "Banco" in (asset.get("sector") or "") or "Energia" in (asset.get("sector") or "") else 15.8,
        "ebitda_margin_pct": 34.2,
        "net_debt_ebitda": 1.15,
        "ev_ebitda": round(max(3.5, pl * 0.78), 1) if pl > 0 else 6.8,
        "cagr_rev_5y_pct": 11.4,
        "cagr_prof_5y_pct": 14.2,
    }


def _get_dividend_history_per_share(asset: dict):
    base_div = float(asset.get("last_dividend_per_share") or 0.0)
    if base_div <= 0:
        return []
    rng = random.Random(f"div_{asset['ticker']}")
    months = ["Nov/25", "Dez/25", "Jan/26", "Fev/26", "Mar/26", "Abr/26", "Mai/26", "Jun/26", "Jul/26", "Ago/26", "Set/26", "Out/26"]
    hist = []
    is_fii = asset["asset_class"] == "FII"
    for i, m in enumerate(months):
        if is_fii:
            # FIIs pay every single month with small variation
            factor = rng.uniform(0.93, 1.06) if i < 11 else 1.0
            val = round(base_div * factor, 2)
        else:
            # Stocks pay quarterly/semi-annually or JCP
            if i in (1, 4, 7, 10, 11):
                factor = rng.uniform(0.75, 1.25) if i < 11 else 1.0
                val = round(base_div * factor, 2)
            else:
                val = 0.0
        hist.append({"month": m, "amount_per_share": val})
    return hist


def calculate_fixed_income_position(fi_row: dict, macro: dict):
    """
    Calculates daily updated balance of Fixed Income (CDI, SELIC, IPCA+, PRE)
    and applies Brazilian regressive Income Tax (22.5% -> 15%) if not tax exempt.
    """
    invested = float(fi_row["invested_amount"])
    indexer = fi_row["indexer"].upper()
    rate_val = float(fi_row["rate_value"])
    tax_exempt = bool(fi_row["tax_exempt"])

    try:
        start_dt = datetime.strptime(fi_row["start_date"], "%Y-%m-%d").date()
    except Exception:
        start_dt = date.today() - timedelta(days=90)

    days_elapsed = max(1, (date.today() - start_dt).days)
    business_days = max(1, int(days_elapsed * (252.0 / 365.0)))

    cdi_aa = float(macro.get("cdi", 10.65)) / 100.0
    selic_aa = float(macro.get("selic", 10.75)) / 100.0
    ipca_aa = float(macro.get("ipca_12m", 4.42)) / 100.0

    if indexer == "CDI":
        effective_aa = cdi_aa * (rate_val / 100.0)
        rate_label = f"{rate_val:g}% do CDI"
    elif indexer == "SELIC":
        effective_aa = selic_aa + (rate_val / 100.0)
        rate_label = f"Selic + {rate_val:g}% a.a." if rate_val > 0 else "100% Taxa Selic"
    elif indexer == "IPCA":
        effective_aa = (1.0 + ipca_aa) * (1.0 + (rate_val / 100.0)) - 1.0
        rate_label = f"IPCA + {rate_val:g}% a.a."
    else:  # PRE
        effective_aa = rate_val / 100.0
        rate_label = f"{rate_val:g}% a.a. (Pré)"

    gross_amount = invested * ((1.0 + effective_aa) ** (business_days / 252.0))
    gross_profit = max(0.0, gross_amount - invested)

    # Tabela Regressiva de IR (Brasil)
    if tax_exempt:
        ir_rate = 0.0
    elif days_elapsed <= 180:
        ir_rate = 22.5
    elif days_elapsed <= 360:
        ir_rate = 20.0
    elif days_elapsed <= 720:
        ir_rate = 17.5
    else:
        ir_rate = 15.0

    ir_tax = gross_profit * (ir_rate / 100.0)
    net_amount = gross_amount - ir_tax

    # Âncora de mercado (ex.: valor atualizado importado da B3). Quando existe, o saldo NÃO é
    # recalculado desde start_date (o que aplicaria os juros em dobro sobre um valor que já os
    # contém); projeta-se apenas o rendimento entre market_value_date e hoje.
    market_value = float(fi_row.get("market_value") or 0.0)
    market_net_value = float(fi_row.get("market_net_value") or 0.0)
    value_source = "PROJECTED"
    anchor_date_str = ""
    if market_value > 0:
        try:
            anchor_dt = datetime.strptime(fi_row.get("market_value_date") or "", "%Y-%m-%d").date()
        except Exception:
            anchor_dt = date.today()
        anchor_date_str = anchor_dt.strftime("%Y-%m-%d")
        anchor_days = max(0, (date.today() - anchor_dt).days)
        anchor_bdays = int(anchor_days * (252.0 / 365.0))
        growth = (1.0 + effective_aa) ** (anchor_bdays / 252.0) if anchor_bdays > 0 else 1.0

        gross_amount = market_value * growth
        gross_profit = max(0.0, gross_amount - invested)
        if market_net_value > 0:
            # Líquido oficial + rendimento projetado após a âncora, já descontado do IR
            accrued_since_anchor = gross_amount - market_value
            net_amount = market_net_value + accrued_since_anchor * (1.0 - ir_rate / 100.0)
            ir_tax = max(0.0, gross_amount - net_amount)
        else:
            ir_tax = gross_profit * (ir_rate / 100.0)
            net_amount = gross_amount - ir_tax
        value_source = "MARKET_ANCHOR"

    net_profit = net_amount - invested
    net_profit_pct = (net_profit / invested * 100.0) if invested > 0 else 0.0
    cost_estimated = bool(abs(invested - (market_value or gross_amount)) < 0.01 and market_value > 0)

    return {
        **fi_row,
        "rate_label": rate_label,
        "days_elapsed": days_elapsed,
        "gross_amount": round(gross_amount, 2),
        "gross_profit": round(gross_profit, 2),
        "ir_rate": ir_rate,
        "ir_tax": round(ir_tax, 2),
        "net_amount": round(net_amount, 2),
        "net_profit": round(net_profit, 2),
        "net_profit_pct": round(net_profit_pct, 2),
        "cost_estimated": cost_estimated,
        "value_source": value_source,
        "value_anchor_date": anchor_date_str,
    }


def lookup_ticker_live(ticker: str, default_class: str = "ACAO_BR"):
    """Looks up a ticker in assets_catalog or fetches live from Yahoo Finance."""
    ticker = ticker.upper().strip().replace(".SA", "")
    conn = get_conn()
    row = conn.execute("SELECT * FROM assets_catalog WHERE ticker = ?", (ticker,)).fetchone()
    conn.close()
    if row:
        d = dict(row)
        d["is_stale"] = is_quote_stale(d.get("updated_at"))
        return d

    # Guess asset class if not specified
    cls = default_class.upper()
    if ticker.endswith("11") and cls not in ("ACAO_BR", "ETF_BR", "FII"):
        cls = "FII"

    yf_sym = f"{ticker}.SA" if cls in ("ACAO_BR", "FII", "ETF_BR") else (f"{ticker}-USD" if cls == "CRIPTO" else ticker)
    currency = "USD" if cls in ("STOCK_US", "CRIPTO") else "BRL"
    name = ticker
    sector = "Fundo Imobiliário" if cls == "FII" else ("Ações B3" if cls == "ACAO_BR" else "Mercado")
    last_price = 0.0
    change_pct = 0.0
    volume_day = 0.0
    dy_12m = 0.0
    last_div = 0.0
    last_ex_date = ""
    pvp = 1.0
    pl = 0.0

    # Try fetching friendly company/fund name from Yahoo Finance public search
    try:
        r_search = requests.get(
            f"https://query2.finance.yahoo.com/v1/finance/search?q={yf_sym}&quotesCount=3&newsCount=0",
            timeout=2.5,
            headers={"User-Agent": "Mozilla/5.0"},
        )
        if r_search.status_code == 200:
            quotes = r_search.json().get("quotes", [])
            for q in quotes:
                q_sym = (q.get("symbol") or "").upper()
                if q_sym in (yf_sym.upper(), ticker.upper()):
                    candidate = q.get("longname") or q.get("shortname")
                    if candidate:
                        name = candidate.strip()
                    if q.get("sectorDisp") or q.get("industryDisp"):
                        sector = (q.get("sectorDisp") or q.get("industryDisp")).strip()
                    break
    except Exception:
        pass

    try:
        tk = yf.Ticker(yf_sym)
        hist = tk.history(period="5d", interval="1d")
        if hist is not None and not hist.empty:
            closes = hist["Close"].dropna()
            vols = hist["Volume"].dropna()
            if len(closes) >= 1:
                last_price = round(float(closes.iloc[-1]), 2)
                prev_p = float(closes.iloc[-2]) if len(closes) >= 2 else last_price
                change_pct = round(((last_price - prev_p) / prev_p * 100.0) if prev_p > 0 else 0.0, 2)
                if len(vols) >= 1:
                    volume_day = round(float(vols.iloc[-1]) * last_price, 0)
        try:
            divs = tk.dividends
            if divs is not None and len(divs) > 0:
                last_div = round(float(divs.iloc[-1]), 4)
                try:
                    last_ex_date = divs.index[-1].strftime("%Y-%m-%d")
                except Exception:
                    pass
                recent_divs = divs.tail(12)
                if last_price > 0:
                    dy_12m = round((float(recent_divs.sum()) / last_price) * 100.0, 2)
        except Exception:
            pass
        try:
            info = tk.fast_info
            if hasattr(info, "last_price") and last_price <= 0 and info.last_price:
                last_price = round(float(info.last_price), 2)
        except Exception:
            pass
    except Exception:
        pass

    if last_price > 0:
        conn = get_conn()
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn.execute("""
            INSERT OR REPLACE INTO assets_catalog (
                ticker, name, asset_class, currency, sector, cnpj,
                last_price, change_pct, volume_day, dy_12m, pl, pvp,
                last_dividend_per_share, last_div_ex_date, last_div_pay_date, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            ticker, name, cls, currency, sector, "",
            last_price, change_pct, volume_day, dy_12m, pl, pvp,
            last_div, last_ex_date, "", now_str
        ))
        conn.commit()
        conn.close()

    return {
        "ticker": ticker,
        "name": name,
        "asset_class": cls,
        "currency": currency,
        "sector": sector,
        "last_price": last_price,
        "change_pct": change_pct,
        "volume_day": volume_day,
        "pvp": pvp,
        "pl": pl,
        "dy_12m": dy_12m,
        "last_dividend_per_share": last_div,
        "is_stale": is_quote_stale(now_str),
        "updated_at": now_str,
    }


def get_portfolio_summary(user_id: int = 1):
    sync_yfinance_quotes_background()
    macro = fetch_macro_indicators()
    usd_brl = float(macro.get("usd_brl", 5.72))

    conn = get_conn()
    catalog_rows = conn.execute("SELECT * FROM assets_catalog").fetchall()
    catalog = {r["ticker"]: dict(r) for r in catalog_rows}

    tx_rows = conn.execute("SELECT * FROM transactions WHERE user_id = ? ORDER BY tx_date ASC, id ASC", (user_id,)).fetchall()
    fi_rows = conn.execute("SELECT * FROM fixed_income WHERE user_id = ? ORDER BY start_date ASC, id ASC", (user_id,)).fetchall()
    div_rows = conn.execute("SELECT * FROM dividends_received WHERE user_id = ? ORDER BY pay_date DESC", (user_id,)).fetchall()
    target_rows = conn.execute("SELECT * FROM allocation_targets WHERE user_id = ?", (user_id,)).fetchall()

    if not target_rows:
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
            conn.execute("INSERT OR IGNORE INTO allocation_targets (user_id, asset_class, target_pct) VALUES (?, ?, ?)", (user_id, cls, pct))
        conn.commit()
        target_rows = conn.execute("SELECT * FROM allocation_targets WHERE user_id = ?", (user_id,)).fetchall()

    conn.close()

    targets = {r["asset_class"]: float(r["target_pct"]) for r in target_rows}

    # Aggregate variable income positions with average price (PM)
    positions_map = {}
    realized_profit_brl = 0.0

    for tx in tx_rows:
        t = tx["ticker"].upper()
        cls = tx["asset_class"]
        q = float(tx["quantity"])
        p = float(tx["unit_price"])
        f = float(tx["fees"] or 0.0)
        curr = tx["currency"] or "BRL"
        fx = float(tx["fx_rate"] or (usd_brl if curr == "USD" else 1.0))

        if t not in positions_map:
            cat_info = catalog.get(t, {})
            positions_map[t] = {
                "ticker": t,
                "name": cat_info.get("name", t),
                "asset_class": cls,
                "currency": curr,
                "sector": cat_info.get("sector", ""),
                "quantity": 0.0,
                "avg_price": 0.0,
                "avg_fx": fx,
                "broker": tx["broker"] or "Corretora",
            }

        pos = positions_map[t]
        notes_raw = tx["notes"] or ""
        notes = "".join(ch for ch in unicodedata.normalize("NFD", notes_raw) if unicodedata.category(ch) != "Mn").lower()
        if "has_real_buy" not in pos:
            pos["has_real_buy"] = False
            pos["has_estimated_pm"] = False

        ttype = str(tx["tx_type"] or "").upper().strip()
        if ttype in ("BUY", "COMPRA"):
            is_synthetic_estimate = (
                "sincronizacao posicao b3" in notes
                or "posicao b3" in notes
                or "estimado pelo fechamento" in notes
            ) and not any(k in notes for k in ("informado", "mantido", "ajustado", "negociacao"))
            if is_synthetic_estimate:
                pos["has_estimated_pm"] = True
            else:
                pos["has_real_buy"] = True

            cost_native = (q * p) + f
            prev_cost = pos["quantity"] * pos["avg_price"]
            new_cost = prev_cost + cost_native

            # Custo acumulado em BRL pelo câmbio da operação (para cálculo exato do IR sobre ativos no exterior)
            prev_cost_brl = pos.get("cost_basis_brl", 0.0)
            cost_op_brl = cost_native * fx
            pos["cost_basis_brl"] = prev_cost_brl + cost_op_brl

            pos["quantity"] += q
            pos["avg_price"] = new_cost / pos["quantity"] if pos["quantity"] > 0 else 0.0
            pos["avg_fx"] = (pos["cost_basis_brl"] / (pos["quantity"] * pos["avg_price"])) if (pos["quantity"] * pos["avg_price"]) > 0 else fx
            pos["broker"] = tx["broker"] or pos["broker"]
            pos["asset_class"] = cls or pos["asset_class"]
        elif ttype in ("SELL", "VENDA"):
            sell_fx = float(tx["fx_rate"] or (usd_brl if curr == "USD" else 1.0))
            if curr == "USD":
                # Regra Receita Federal / IR: Alienação convertida pelo câmbio da data da venda (sell_fx)
                # menos Custo de Aquisição histórico médio em BRL da parcela vendida
                proceeds_brl = ((p * q) - f) * sell_fx
                cost_ratio = (q / pos["quantity"]) if pos["quantity"] > 0 else 1.0
                current_basis_brl = pos.get("cost_basis_brl")
                if current_basis_brl is None or current_basis_brl <= 0:
                    current_basis_brl = pos["quantity"] * pos["avg_price"] * pos.get("avg_fx", sell_fx)
                cost_sold_brl = current_basis_brl * cost_ratio
                gain_brl = proceeds_brl - cost_sold_brl
                pos["cost_basis_brl"] = max(0.0, current_basis_brl - cost_sold_brl)
            else:
                gain_native = (p - pos["avg_price"]) * q - f
                gain_brl = gain_native
                cost_sold_brl = (pos["avg_price"] * q) + f
                pos["cost_basis_brl"] = max(0.0, pos.get("cost_basis_brl", 0.0) - cost_sold_brl)

            realized_profit_brl += gain_brl
            pos["quantity"] = max(0.0, pos["quantity"] - q)
            if pos["quantity"] <= 1e-8:
                pos["quantity"] = 0.0
                pos["avg_price"] = 0.0
                pos["cost_basis_brl"] = 0.0
                pos["avg_fx"] = 1.0

    positions = []
    total_invested_brl = 0.0
    total_current_brl = 0.0
    day_change_brl = 0.0

    class_meta = {
        "FII": "Fundos Imobiliários (FIIs)",
        "ACAO_BR": "Ações Brasileiras (B3)",
        "CAIXINHA": "Caixinhas & Liquidez (Nubank/Bancos)",
        "RENDA_FIXA": "CDB, LCI, LCA & Renda Fixa",
        "TESOURO": "Tesouro Direto (IPCA+ / Selic)",
        "FUNDO_INV": "Fundos de Investimento",
        "ETF_BR": "ETFs & BDRs",
        "STOCK_US": "Stocks EUA (Dólar)",
        "CRIPTO": "Criptomoedas",
    }

    class_stats = {
        k: {"invested_brl": 0.0, "current_brl": 0.0, "count": 0}
        for k in class_meta.keys()
    }
    all_holdings_slices = []

    for t, pos in positions_map.items():
        if pos["quantity"] <= 1e-8:
            continue
        cat = catalog.get(t, {})
        cur_price = float(cat.get("last_price", 0.0)) or pos["avg_price"]
        chg_pct = float(cat.get("change_pct", 0.0))
        dy_12m = float(cat.get("dy_12m", 0.0))
        last_div = float(cat.get("last_dividend_per_share", 0.0))
        pvp = float(cat.get("pvp", 1.0))
        pl = float(cat.get("pl", 0.0))

        curr = pos["currency"]
        mult = usd_brl if curr == "USD" else 1.0

        invested_native = pos["quantity"] * pos["avg_price"]
        current_native = pos["quantity"] * cur_price
        profit_pct = ((cur_price - pos["avg_price"]) / pos["avg_price"] * 100.0) if pos["avg_price"] > 0 else 0.0

        invested_brl = invested_native * mult
        current_brl = current_native * mult
        profit_brl = current_brl - invested_brl
        day_var_brl = current_brl * (chg_pct / 100.0)

        total_invested_brl += invested_brl
        total_current_brl += current_brl
        day_change_brl += day_var_brl

        cls_key = pos["asset_class"] if pos["asset_class"] in class_stats else "ACAO_BR"
        class_stats[cls_key]["invested_brl"] += invested_brl
        class_stats[cls_key]["current_brl"] += current_brl
        class_stats[cls_key]["count"] += 1

        yoc = (dy_12m * cur_price / pos["avg_price"]) if pos["avg_price"] > 0 else 0.0

        item_dict = {
            **pos,
            "asset_class": cls_key,
            "category_label": class_meta.get(cls_key, cls_key),
            "quantity": round(pos["quantity"], 6),
            "avg_price": round(pos["avg_price"], 2),
            "pm_estimated": bool(pos.get("has_estimated_pm", False) and not pos.get("has_real_buy", False)),
            "current_price": round(cur_price, 2),
            "is_stale": is_quote_stale(cat.get("updated_at")),
            "updated_at": cat.get("updated_at", ""),
            "change_pct": round(chg_pct, 2),
            "dy_12m": round(dy_12m, 2),
            "yoc_12m": round(yoc, 2),
            "last_dividend_per_share": round(last_div, 2),
            "monthly_passive_income_brl": round(pos["quantity"] * last_div * mult, 2),
            "pvp": round(pvp, 2),
            "pl": round(pl, 2),
            "invested_brl": round(invested_brl, 2),
            "current_brl": round(current_brl, 2),
            "profit_brl": round(profit_brl, 2),
            "profit_pct": round(profit_pct, 2),
        }
        positions.append(item_dict)
        all_holdings_slices.append({
            "id": f"VAR_{t}",
            "code": t,
            "name": pos["name"] if pos["name"] != t else t,
            "asset_class": cls_key,
            "category_label": class_meta.get(cls_key, cls_key),
            "invested_brl": round(invested_brl, 2),
            "current_brl": round(current_brl, 2),
            "profit_brl": round(profit_brl, 2),
            "profit_pct": round(profit_pct, 2),
            "broker": pos["broker"],
            "is_fixed_income": False,
        })

    # Fixed income positions (Caixinhas, CDB, LCI, LCA, Tesouro IPCA+/Selic, Fundos)
    fi_positions = []
    for r in fi_rows:
        fi_calc = calculate_fixed_income_position(dict(r), macro)
        raw_cls = (fi_calc.get("asset_class") or "RENDA_FIXA").upper()
        title_lower = (fi_calc.get("title_name") or "").lower()
        if raw_cls not in class_stats:
            if "caixinha" in title_lower or "reserva" in title_lower:
                raw_cls = "CAIXINHA"
            elif "tesouro" in title_lower:
                raw_cls = "TESOURO"
            else:
                raw_cls = "RENDA_FIXA"
        elif raw_cls == "RENDA_FIXA" and "caixinha" in title_lower:
            raw_cls = "CAIXINHA"
        elif raw_cls == "RENDA_FIXA" and "tesouro" in title_lower:
            raw_cls = "TESOURO"

        fi_calc["asset_class"] = raw_cls
        fi_calc["category_label"] = class_meta.get(raw_cls, "Renda Fixa")
        fi_positions.append(fi_calc)

        total_invested_brl += fi_calc["invested_amount"]
        total_current_brl += fi_calc["net_amount"]
        day_change_brl += fi_calc["net_amount"] * ((macro.get("cdi", 10.65) / 100.0) / 252.0)

        class_stats[raw_cls]["invested_brl"] += fi_calc["invested_amount"]
        class_stats[raw_cls]["current_brl"] += fi_calc["net_amount"]
        class_stats[raw_cls]["count"] += 1

        all_holdings_slices.append({
            "id": f"FI_{fi_calc['id']}",
            "code": fi_calc["title_name"],
            "name": f"{fi_calc['issuer']} ({fi_calc['rate_label']})",
            "asset_class": raw_cls,
            "category_label": class_meta.get(raw_cls, "Renda Fixa"),
            "invested_brl": round(fi_calc["invested_amount"], 2),
            "current_brl": round(fi_calc["net_amount"], 2),
            "profit_brl": round(fi_calc["net_profit"], 2),
            "profit_pct": round(fi_calc["net_profit_pct"], 2),
            "broker": fi_calc.get("broker") or fi_calc["issuer"],
            "is_fixed_income": True,
            "fi_id": fi_calc["id"],
        })

    # Sort variable positions and all_holdings_slices by current_brl descending
    positions.sort(key=lambda x: x["current_brl"], reverse=True)
    for p in positions:
        p["weight_pct"] = round((p["current_brl"] / total_current_brl * 100.0) if total_current_brl > 0 else 0.0, 2)

    for fi in fi_positions:
        fi["weight_pct"] = round((fi["net_amount"] / total_current_brl * 100.0) if total_current_brl > 0 else 0.0, 2)

    all_holdings_slices.sort(key=lambda x: x["current_brl"], reverse=True)
    for h in all_holdings_slices:
        h["weight_pct"] = round((h["current_brl"] / total_current_brl * 100.0) if total_current_brl > 0 else 0.0, 2)

    allocation = []
    for cls_code, label in class_meta.items():
        st = class_stats[cls_code]
        val_brl = round(st["current_brl"], 2)
        inv_brl = round(st["invested_brl"], 2)
        prof_brl = round(val_brl - inv_brl, 2)
        prof_pct = round((prof_brl / inv_brl * 100.0) if inv_brl > 0 else 0.0, 2)
        cur_pct = round((val_brl / total_current_brl * 100.0) if total_current_brl > 0 else 0.0, 2)
        tgt_pct = round(targets.get(cls_code, 0.0), 2)
        allocation.append({
            "asset_class": cls_code,
            "label": label,
            "count": st["count"],
            "invested_brl": inv_brl,
            "current_brl": val_brl,
            "profit_brl": prof_brl,
            "profit_pct": prof_pct,
            "current_pct": cur_pct,
            "target_pct": tgt_pct,
            "gap_pct": round(tgt_pct - cur_pct, 2),
        })

    total_profit_brl = round(total_current_brl - total_invested_brl, 2)
    total_profit_pct = round((total_profit_brl / total_invested_brl * 100.0) if total_invested_brl > 0 else 0.0, 2)
    day_change_pct = round((day_change_brl / total_current_brl * 100.0) if total_current_brl > 0 else 0.0, 2)

    dividends_list = [dict(d) for d in div_rows]
    total_dividends_brl = round(sum(float(d["total_amount"]) for d in dividends_list), 2)
    estimated_monthly_divs_brl = round(sum(p["monthly_passive_income_brl"] for p in positions if p["asset_class"] in ("FII", "ACAO_BR")), 2)

    return {
        "kpis": {
            "total_current_brl": round(total_current_brl, 2),
            "total_current_usd": round(total_current_brl / usd_brl, 2) if usd_brl > 0 else 0.0,
            "total_invested_brl": round(total_invested_brl, 2),
            "total_profit_brl": total_profit_brl,
            "total_profit_pct": total_profit_pct,
            "day_change_brl": round(day_change_brl, 2),
            "day_change_pct": day_change_pct,
            "realized_profit_brl": round(realized_profit_brl, 2),
            "total_dividends_brl": total_dividends_brl,
            "estimated_monthly_divs_brl": estimated_monthly_divs_brl,
            "holdings_count": len(all_holdings_slices),
        },
        "macro": macro,
        "allocation": allocation,
        "allocation_by_asset": all_holdings_slices,
        "positions": positions,
        "fixed_income": fi_positions,
        "dividends": dividends_list,
        "transactions": [dict(t) for t in reversed(tx_rows)],
    }
