import os
import socket
from datetime import datetime
from typing import Optional
from fastapi import FastAPI, HTTPException, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
import yfinance as yf

from .database import init_db, get_conn
from .market_service import (
    get_portfolio_summary,
    get_asset_chart_and_dividends,
    fetch_macro_indicators,
    sync_yfinance_quotes_background,
)
from .intelligence_service import (
    fetch_asset_news,
    fetch_official_reports,
    generate_ai_report_interpretation,
)

app = FastAPI(title="SIM — Scherer Investments Money", version="1.1.0")

STATIC_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static")
os.makedirs(STATIC_DIR, exist_ok=True)


@app.on_event("startup")
def on_startup():
    init_db()
    sync_yfinance_quotes_background()


def get_local_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


class TransactionCreate(BaseModel):
    tx_date: str
    ticker: str
    asset_class: str = "ACAO_BR"
    tx_type: str = "BUY"
    quantity: float
    unit_price: float
    fees: float = 0.0
    currency: str = "BRL"
    broker: str = "XP Investimentos"
    notes: str = ""


class FixedIncomeCreate(BaseModel):
    title_name: str
    issuer: str
    asset_class: str = "RENDA_FIXA"
    indexer: str = "CDI"
    rate_value: float = 100.0
    invested_amount: float
    start_date: str
    maturity_date: str
    daily_liquidity: int = 1
    tax_exempt: int = 0
    broker: str = "Nubank"


class DividendCreate(BaseModel):
    pay_date: str
    ticker: str
    div_type: str = "Rendimento / Dividendo"
    amount_per_share: float
    shares_qty: float
    currency: str = "BRL"


@app.get("/api/portfolio")
def api_get_portfolio():
    return get_portfolio_summary()


@app.get("/api/market/assets")
def api_get_market_assets(
    asset_class: str = Query("ALL"),
    sort_by: str = Query("em_alta"),
    only_mine: bool = Query(False),
):
    sync_yfinance_quotes_background()
    conn = get_conn()
    if asset_class.upper() == "ALL":
        rows = conn.execute("SELECT * FROM assets_catalog").fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM assets_catalog WHERE asset_class = ?",
            (asset_class.upper(),),
        ).fetchall()

    # Check user's held tickers
    tx_rows = conn.execute("SELECT ticker, tx_type, quantity FROM transactions").fetchall()
    conn.close()

    held_qty = {}
    for tx in tx_rows:
        t = tx["ticker"].upper()
        q = float(tx["quantity"])
        held_qty[t] = held_qty.get(t, 0.0) + (q if tx["tx_type"] == "BUY" else -q)

    items = []
    for r in rows:
        d = dict(r)
        user_q = max(0.0, held_qty.get(d["ticker"], 0.0))
        if only_mine and user_q <= 1e-8:
            continue
        d["user_qty"] = round(user_q, 6)
        d["in_portfolio"] = user_q > 1e-8
        d["monthly_yield_pct"] = (
            round((d["last_dividend_per_share"] / d["last_price"]) * 100.0, 2)
            if d["last_price"] > 0 and d["last_dividend_per_share"] > 0
            else 0.0
        )
        items.append(d)

    s = sort_by.lower()
    if s == "em_alta":
        items.sort(key=lambda x: x["change_pct"], reverse=True)
    elif s == "em_baixa":
        items.sort(key=lambda x: x["change_pct"], reverse=False)
    elif s == "mais_comprados":
        items.sort(key=lambda x: x["volume_day"], reverse=True)
    elif s == "maior_dividendo":
        items.sort(key=lambda x: (x["dy_12m"], x["last_dividend_per_share"]), reverse=True)
    elif s == "mais_descontados":
        items.sort(key=lambda x: x["pvp"] if x["pvp"] > 0 else 999.0)

    return {"count": len(items), "assets": items}


@app.get("/api/asset/{ticker}")
def api_get_asset_detail(ticker: str, period: str = Query("1M")):
    data = get_asset_chart_and_dividends(ticker, period)
    if not data:
        raise HTTPException(status_code=404, detail=f"Ativo {ticker} não encontrado.")
    news = fetch_asset_news(ticker)
    reports = fetch_official_reports(ticker)
    return {
        **data,
        "news": news,
        "reports_data": reports,
    }


@app.post("/api/asset/{ticker}/analyze-report")
def api_analyze_asset_report(ticker: str):
    ticker = ticker.upper().strip()
    conn = get_conn()
    row = conn.execute("SELECT * FROM assets_catalog WHERE ticker = ?", (ticker,)).fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="Ativo não encontrado.")
    rep_data = fetch_official_reports(ticker)
    summary = generate_ai_report_interpretation(dict(row), rep_data.get("reports", []), force_refresh=True)
    return {"status": "ok", "ai_interpretation": summary}


@app.post("/api/transactions")
def api_add_transaction(payload: TransactionCreate):
    ticker = payload.ticker.upper().strip()
    macro = fetch_macro_indicators()
    fx = float(macro.get("usd_brl", 5.72)) if payload.currency.upper() == "USD" else 1.0

    conn = get_conn()
    cur = conn.cursor()

    # Ensure ticker exists in assets_catalog
    exists = cur.execute("SELECT ticker FROM assets_catalog WHERE ticker = ?", (ticker,)).fetchone()
    if not exists:
        cur.execute("""
            INSERT INTO assets_catalog (
                ticker, name, asset_class, currency, sector, last_price, change_pct,
                volume_day, dy_12m, pl, pvp, last_dividend_per_share, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            ticker,
            ticker,
            payload.asset_class.upper(),
            payload.currency.upper(),
            "Personalizado",
            payload.unit_price,
            0.0,
            1000000,
            0.0,
            0.0,
            1.0,
            0.0,
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        ))

    cur.execute("""
        INSERT INTO transactions (tx_date, ticker, asset_class, tx_type, quantity, unit_price, fees, currency, fx_rate, broker, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        payload.tx_date,
        ticker,
        payload.asset_class.upper(),
        payload.tx_type.upper(),
        payload.quantity,
        payload.unit_price,
        payload.fees,
        payload.currency.upper(),
        fx,
        payload.broker,
        payload.notes,
    ))
    conn.commit()
    conn.close()
    return {"status": "ok"}


@app.delete("/api/transactions/{tx_id}")
def api_delete_transaction(tx_id: int):
    conn = get_conn()
    conn.execute("DELETE FROM transactions WHERE id = ?", (tx_id,))
    conn.commit()
    conn.close()
    return {"status": "ok"}


@app.post("/api/fixed-income")
def api_add_fixed_income(payload: FixedIncomeCreate):
    conn = get_conn()
    conn.execute("""
        INSERT INTO fixed_income (title_name, issuer, asset_class, indexer, rate_value, invested_amount, start_date, maturity_date, daily_liquidity, tax_exempt, broker)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        payload.title_name,
        payload.issuer,
        payload.asset_class,
        payload.indexer.upper(),
        payload.rate_value,
        payload.invested_amount,
        payload.start_date,
        payload.maturity_date,
        payload.daily_liquidity,
        payload.tax_exempt,
        payload.broker,
    ))
    conn.commit()
    conn.close()
    return {"status": "ok"}


@app.delete("/api/fixed-income/{fi_id}")
def api_delete_fixed_income(fi_id: int):
    conn = get_conn()
    conn.execute("DELETE FROM fixed_income WHERE id = ?", (fi_id,))
    conn.commit()
    conn.close()
    return {"status": "ok"}


@app.post("/api/dividends")
def api_add_dividend(payload: DividendCreate):
    total = round(payload.amount_per_share * payload.shares_qty, 2)
    conn = get_conn()
    conn.execute("""
        INSERT INTO dividends_received (pay_date, ticker, div_type, amount_per_share, shares_qty, total_amount, currency)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        payload.pay_date,
        payload.ticker.upper().strip(),
        payload.div_type,
        payload.amount_per_share,
        payload.shares_qty,
        total,
        payload.currency.upper(),
    ))
    conn.commit()
    conn.close()
    return {"status": "ok"}


@app.delete("/api/dividends/{div_id}")
def api_delete_dividend(div_id: int):
    conn = get_conn()
    conn.execute("DELETE FROM dividends_received WHERE id = ?", (div_id,))
    conn.commit()
    conn.close()
    return {"status": "ok"}


@app.get("/api/rebalance")
def api_calculate_rebalance(contribution_brl: float = Query(2000.0)):
    summary = get_portfolio_summary()
    total_after = summary["kpis"]["total_current_brl"] + contribution_brl
    suggestions = []

    for item in summary["allocation"]:
        ideal_brl = total_after * (item["target_pct"] / 100.0)
        deficit_brl = max(0.0, ideal_brl - item["current_brl"])
        suggestions.append({
            **item,
            "ideal_brl": round(ideal_brl, 2),
            "deficit_brl": round(deficit_brl, 2),
        })

    total_deficit = sum(s["deficit_brl"] for s in suggestions)
    for s in suggestions:
        if total_deficit > 0:
            s["suggested_contribution_brl"] = round(contribution_brl * (s["deficit_brl"] / total_deficit), 2)
        else:
            s["suggested_contribution_brl"] = round(contribution_brl * (s["target_pct"] / 100.0), 2)

    suggestions.sort(key=lambda x: x["suggested_contribution_brl"], reverse=True)
    return {"contribution_brl": contribution_brl, "suggestions": suggestions}


@app.get("/api/system/mobile-access")
def api_mobile_access():
    ip = get_local_ip()
    url = f"http://{ip}:8000"
    return {
        "local_ip": ip,
        "mobile_url": url,
        "qr_api_url": f"https://api.qrserver.com/v1/create-qr-code/?size=240x240&data={url}",
    }


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/manifest.json")
def get_manifest():
    return FileResponse(os.path.join(STATIC_DIR, "manifest.json"))


@app.get("/sw.js")
def get_sw():
    return FileResponse(os.path.join(STATIC_DIR, "sw.js"))


@app.get("/")
def serve_index():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))
