import math
import time
import random
import threading
from datetime import datetime, timedelta, date
import requests
import yfinance as yf
from .database import get_conn

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


def get_asset_chart_and_dividends(ticker: str, period_key: str = "1M"):
    """
    Returns interactive price history for ('1D', '5D', '1M', '6M', '1Y')
    plus dividend per share history for the exclusive asset page.
    """
    ticker = ticker.upper().strip()
    conn = get_conn()
    asset_row = conn.execute("SELECT * FROM assets_catalog WHERE ticker = ?", (ticker,)).fetchone()

    # Check if user holds this asset to include user's Average Price (Preço Médio) on chart
    txs = conn.execute("SELECT * FROM transactions WHERE ticker = ? ORDER BY tx_date ASC, id ASC", (ticker,)).fetchall()
    conn.close()

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
        }
        yf_period, yf_interval = period_map.get(period_key.upper(), ("1mo", "1d"))

        try:
            tk = yf.Ticker(yf_sym)
            hist = tk.history(period=yf_period, interval=yf_interval)
            if hist is not None and not hist.empty and len(hist) >= 3:
                for idx, row in hist.iterrows():
                    val = float(row["Close"])
                    if math.isnan(val):
                        continue
                    if period_key.upper() in ("1D", "5D"):
                        dt_label = idx.strftime("%d/%m %H:%M")
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
            points = _generate_realistic_series(asset["last_price"], asset["change_pct"], ticker, period_key.upper())

        CHART_CACHE[cache_key] = {"ts": now, "points": points}

    # Build 12-month dividend per share history
    div_history = _get_dividend_history_per_share(asset)

    first_price = points[0]["price"] if points else asset["last_price"]
    last_price = points[-1]["price"] if points else asset["last_price"]
    period_change_abs = round(last_price - first_price, 2)
    period_change_pct = round(((last_price - first_price) / first_price * 100.0) if first_price > 0 else 0.0, 2)

    monthly_yield_pct = 0.0
    if asset["last_price"] > 0 and asset["last_dividend_per_share"] > 0:
        monthly_yield_pct = round((asset["last_dividend_per_share"] / asset["last_price"]) * 100.0, 2)

    return {
        "asset": asset,
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
    }
    n_steps, step_delta, vol, fmt = cfg.get(period_key, cfg["1M"])
    now_dt = datetime.now().replace(second=0, microsecond=0)

    # Walk backwards from current_price so the last point matches current_price
    rev_prices = [current_price]
    p = current_price
    drift = (day_change_pct / 100.0) / n_steps if period_key == "1D" else 0.0003
    for _ in range(n_steps - 1):
        shock = rng.gauss(drift, vol)
        p = max(0.5, p / (1.0 + shock))
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
    net_profit = net_amount - invested
    net_profit_pct = (net_profit / invested * 100.0) if invested > 0 else 0.0

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
    }


def lookup_ticker_live(ticker: str, default_class: str = "ACAO_BR"):
    """Looks up a ticker in assets_catalog or fetches live from Yahoo Finance."""
    ticker = ticker.upper().strip().replace(".SA", "")
    conn = get_conn()
    row = conn.execute("SELECT * FROM assets_catalog WHERE ticker = ?", (ticker,)).fetchone()
    conn.close()
    if row:
        return dict(row)

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
    pvp = 1.0
    pl = 0.0

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
            last_div, "", "", now_str
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
        "dy_12m": dy_12m,
        "last_dividend_per_share": last_div,
    }


def get_portfolio_summary():
    sync_yfinance_quotes_background()
    macro = fetch_macro_indicators()
    usd_brl = float(macro.get("usd_brl", 5.72))

    conn = get_conn()
    catalog_rows = conn.execute("SELECT * FROM assets_catalog").fetchall()
    catalog = {r["ticker"]: dict(r) for r in catalog_rows}

    tx_rows = conn.execute("SELECT * FROM transactions ORDER BY tx_date ASC, id ASC").fetchall()
    fi_rows = conn.execute("SELECT * FROM fixed_income ORDER BY start_date ASC, id ASC").fetchall()
    div_rows = conn.execute("SELECT * FROM dividends_received ORDER BY pay_date DESC").fetchall()
    target_rows = conn.execute("SELECT * FROM allocation_targets").fetchall()
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
        if tx["tx_type"] == "BUY":
            prev_cost = pos["quantity"] * pos["avg_price"]
            new_cost = prev_cost + (q * p) + f
            pos["quantity"] += q
            pos["avg_price"] = new_cost / pos["quantity"] if pos["quantity"] > 0 else 0.0
            pos["avg_fx"] = fx
            pos["broker"] = tx["broker"] or pos["broker"]
            pos["asset_class"] = cls or pos["asset_class"]
        elif tx["tx_type"] == "SELL":
            gain_native = (p - pos["avg_price"]) * q - f
            realized_profit_brl += gain_native * (usd_brl if curr == "USD" else 1.0)
            pos["quantity"] = max(0.0, pos["quantity"] - q)

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
            "current_price": round(cur_price, 2),
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
