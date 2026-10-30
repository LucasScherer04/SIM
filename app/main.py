import os
import socket
import base64
import urllib.parse
from datetime import datetime, date
from contextlib import asynccontextmanager
from typing import Optional, Dict, List, Any
from fastapi import FastAPI, HTTPException, Query, Request, Depends, Header
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, Response, JSONResponse
from pydantic import BaseModel
import yfinance as yf

from .database import init_db, get_conn
from .auth_service import (
    get_current_user,
    create_user_session,
    delete_user_session,
    create_user,
    get_user_by_username,
    get_user_by_id,
    list_all_users,
    verify_pin,
    update_user_pin,
    get_user_from_token,
)
from .market_service import (
    get_portfolio_summary,
    get_asset_chart_and_dividends,
    fetch_macro_indicators,
    sync_yfinance_quotes_background,
    lookup_ticker_live,
    get_asset_specialized_profile,
    is_quote_stale,
)
from .intelligence_service import (
    fetch_asset_news,
    fetch_official_reports,
    generate_ai_report_interpretation,
)
from .b3_sync_service import (
    ensure_b3_sync_tables,
    parse_b3_spreadsheet,
    apply_b3_sync,
    get_b3_sync_logs,
    generate_b3_template_xlsx,
    export_portfolio_b3_xlsx,
)
from .ai_radar_service import (
    ensure_settings_tables,
    get_public_settings,
    update_app_settings,
    test_ai_connection,
    generate_portfolio_and_market_radar,
)

from .whatsapp_service import (
    send_whatsapp_message,
    trigger_daily_whatsapp_dispatch,
    format_daily_whatsapp_message,
    start_whatsapp_scheduler_thread,
    get_whatsapp_scheduler_status,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    ensure_b3_sync_tables()
    ensure_settings_tables()
    sync_yfinance_quotes_background()
    start_whatsapp_scheduler_thread()
    yield


app = FastAPI(title="SIM — Scherer Investments Money", version="1.3.0", lifespan=lifespan)

STATIC_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static")
os.makedirs(STATIC_DIR, exist_ok=True)


def get_local_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


@app.middleware("http")
async def security_csrf_and_origin_middleware(request: Request, call_next):
    """
    Proteção contra ataques CSRF e Cross-Origin em rotas de mutação de estado (/api/*).
    Bloqueia requisições forjadas vindas de páginas externas (ex: formulários ocultos ou fetch malicioso).
    """
    if request.method in ("POST", "PUT", "DELETE", "PATCH") and request.url.path.startswith("/api/"):
        origin = request.headers.get("origin")
        referer = request.headers.get("referer")

        if origin:
            try:
                parsed_origin = urllib.parse.urlparse(origin)
                origin_host = parsed_origin.hostname or ""
                request_host = (request.headers.get("host") or "").split(":")[0]
                server_ip = get_local_ip()
                allowed_hosts = {"localhost", "127.0.0.1", "0.0.0.0", server_ip, request_host}
                if origin_host not in allowed_hosts:
                    return JSONResponse(
                        status_code=403,
                        content={"detail": "Acesso negado: Requisição de origem externa bloqueada (CSRF Protection)."},
                    )
            except Exception:
                return JSONResponse(status_code=403, content={"detail": "Cabeçalho Origin inválido."})

        if referer:
            try:
                parsed_ref = urllib.parse.urlparse(referer)
                ref_host = parsed_ref.hostname or ""
                request_host = (request.headers.get("host") or "").split(":")[0]
                server_ip = get_local_ip()
                allowed_hosts = {"localhost", "127.0.0.1", "0.0.0.0", server_ip, request_host}
                if ref_host not in allowed_hosts:
                    return JSONResponse(
                        status_code=403,
                        content={"detail": "Acesso negado: Referer de origem externa bloqueado (CSRF Protection)."},
                    )
            except Exception:
                pass

    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response


class LoginPayload(BaseModel):
    username: str
    pin: str


class SetupPayload(BaseModel):
    username: str = "Lucas"
    pin: str


class RegisterPayload(BaseModel):
    username: str
    pin: str


class ChangePinPayload(BaseModel):
    current_pin: str
    new_pin: str


# =============================================================================
# ENDPOINTS DE AUTENTICAÇÃO & MULTI-USUÁRIO
# =============================================================================

@app.get("/api/auth/status")
def api_auth_status(request: Request, x_sim_token: Optional[str] = Header(None, alias="X-SIM-Token")):
    users = list_all_users()
    setup_required = len(users) == 0 or (len(users) == 1 and not users[0].get("pin_hash"))
    user = None
    if x_sim_token:
        user = get_user_from_token(x_sim_token)
    return {
        "authenticated": user is not None,
        "setup_required": setup_required,
        "users_count": len(users),
        "users": [{"id": u["id"], "username": u["username"]} for u in users],
        "current_user": user,
    }


@app.get("/api/auth/users")
def api_auth_users():
    users = list_all_users()
    return {"users": [{"id": u["id"], "username": u["username"]} for u in users]}


@app.post("/api/auth/login")
def api_auth_login(payload: LoginPayload):
    user = get_user_by_username(payload.username)
    if not user:
        raise HTTPException(status_code=401, detail="Usuário não encontrado.")
    if not user.get("pin_hash"):
        raise HTTPException(status_code=400, detail="Este usuário ainda não configurou um PIN. Utilize a tela de configuração inicial.")
    if not verify_pin(payload.pin, user["pin_hash"]):
        raise HTTPException(status_code=401, detail="PIN incorreto. Tente novamente.")

    token = create_user_session(user["id"])
    return {
        "status": "ok",
        "token": token,
        "user": {"id": user["id"], "username": user["username"], "is_admin": user["is_admin"]},
    }


@app.post("/api/auth/setup")
def api_auth_setup(payload: SetupPayload):
    users = list_all_users()
    if len(users) > 1 or (len(users) == 1 and users[0].get("pin_hash")):
        raise HTTPException(status_code=400, detail="O PIN inicial já foi configurado. Faça login normalmente.")

    pin_str = str(payload.pin).strip()
    if len(pin_str) < 4:
        raise HTTPException(status_code=400, detail="O PIN deve ter no mínimo 4 dígitos.")

    if not users:
        new_u = create_user(payload.username or "Lucas", pin_str, is_admin=1)
        user_id = new_u["id"]
        user_name = new_u["username"]
    else:
        u = users[0]
        update_user_pin(u["id"], pin_str)
        user_id = u["id"]
        user_name = u["username"]

    token = create_user_session(user_id)
    return {
        "status": "ok",
        "token": token,
        "user": {"id": user_id, "username": user_name, "is_admin": 1},
    }


@app.post("/api/auth/register")
def api_auth_register(payload: RegisterPayload):
    username = payload.username.strip()
    if not username:
        raise HTTPException(status_code=400, detail="Nome de usuário é obrigatório.")
    existing = get_user_by_username(username)
    if existing:
        raise HTTPException(status_code=400, detail="Já existe um usuário cadastrado com esse nome.")
    if len(str(payload.pin).strip()) < 4:
        raise HTTPException(status_code=400, detail="O PIN deve ter pelo menos 4 dígitos.")

    try:
        new_u = create_user(username, payload.pin, is_admin=0)
        token = create_user_session(new_u["id"])
        return {
            "status": "ok",
            "token": token,
            "user": new_u,
        }
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/api/auth/logout")
def api_auth_logout(
    current_user: Dict[str, Any] = Depends(get_current_user),
    x_sim_token: Optional[str] = Header(None, alias="X-SIM-Token"),
    authorization: Optional[str] = Header(None),
):
    token = x_sim_token or authorization
    if token:
        delete_user_session(token)
    return {"status": "ok"}


@app.post("/api/auth/change-pin")
def api_auth_change_pin(payload: ChangePinPayload, current_user: Dict[str, Any] = Depends(get_current_user)):
    user = get_user_by_id(current_user["id"])
    if not user:
        raise HTTPException(status_code=404, detail="Usuário não encontrado.")
    if not verify_pin(payload.current_pin, user["pin_hash"]):
        raise HTTPException(status_code=400, detail="PIN atual incorreto.")
    if len(str(payload.new_pin).strip()) < 4:
        raise HTTPException(status_code=400, detail="O novo PIN deve ter pelo menos 4 dígitos.")

    update_user_pin(user["id"], payload.new_pin)
    new_token = create_user_session(user["id"])
    return {"status": "ok", "token": new_token, "message": "PIN alterado com sucesso!"}


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
    market_value: Optional[float] = None
    market_net_value: Optional[float] = None


class FixedIncomeAdjust(BaseModel):
    invested_amount: Optional[float] = None
    market_value: Optional[float] = None
    market_net_value: Optional[float] = None
    start_date: Optional[str] = None
    rate_value: Optional[float] = None


class DividendCreate(BaseModel):
    pay_date: str
    ticker: str
    div_type: str = "Rendimento / Dividendo"
    amount_per_share: float
    shares_qty: float
    currency: str = "BRL"


@app.get("/api/portfolio")
def api_get_portfolio(current_user: Dict[str, Any] = Depends(get_current_user)):
    return get_portfolio_summary(user_id=current_user["id"])


def _ensure_favorites_table(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS favorites (
            user_id INTEGER NOT NULL DEFAULT 1,
            ticker TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (user_id, ticker)
        )
    """)


@app.get("/api/favorites")
def api_get_favorites(current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    _ensure_favorites_table(conn)
    rows = conn.execute("SELECT ticker FROM favorites WHERE user_id = ? ORDER BY ticker ASC", (current_user["id"],)).fetchall()
    conn.close()
    return {"favorites": [r["ticker"] for r in rows]}


@app.post("/api/favorites/{ticker}")
def api_toggle_favorite(ticker: str, current_user: Dict[str, Any] = Depends(get_current_user)):
    t = ticker.upper().strip()
    uid = current_user["id"]
    conn = get_conn()
    _ensure_favorites_table(conn)
    exists = conn.execute("SELECT ticker FROM favorites WHERE user_id = ? AND ticker = ?", (uid, t)).fetchone()
    if exists:
        conn.execute("DELETE FROM favorites WHERE user_id = ? AND ticker = ?", (uid, t))
        is_fav = False
    else:
        conn.execute("INSERT OR REPLACE INTO favorites (user_id, ticker) VALUES (?, ?)", (uid, t))
        is_fav = True
    conn.commit()
    rows = conn.execute("SELECT ticker FROM favorites WHERE user_id = ? ORDER BY ticker ASC", (uid,)).fetchall()
    conn.close()
    return {"ticker": t, "is_favorite": is_fav, "favorites": [r["ticker"] for r in rows]}


@app.get("/api/market/assets")
def api_get_market_assets(
    asset_class: str = Query("ALL"),
    sort_by: str = Query("em_alta"),
    only_mine: bool = Query(False),
    only_favorites: bool = Query(False),
    q: str = Query(""),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    sync_yfinance_quotes_background()
    conn = get_conn()
    _ensure_favorites_table(conn)
    if asset_class.upper() == "ALL":
        rows = conn.execute("SELECT * FROM assets_catalog").fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM assets_catalog WHERE asset_class = ?",
            (asset_class.upper(),),
        ).fetchall()

    # Check user's held tickers and favorites for this user
    uid = current_user["id"]
    tx_rows = conn.execute("SELECT ticker, tx_type, quantity FROM transactions WHERE user_id = ?", (uid,)).fetchall()
    fav_rows = conn.execute("SELECT ticker FROM favorites WHERE user_id = ?", (uid,)).fetchall()
    conn.close()

    fav_set = {r["ticker"].upper() for r in fav_rows}

    held_qty = {}
    for tx in tx_rows:
        t = tx["ticker"].upper()
        qty = float(tx["quantity"])
        held_qty[t] = held_qty.get(t, 0.0) + (qty if tx["tx_type"] == "BUY" else -qty)

    q_clean = q.strip().lower()
    items = []
    for r in rows:
        d = dict(r)
        d["is_stale"] = is_quote_stale(d.get("updated_at"))
        ticker_up = d["ticker"].upper()
        user_q = max(0.0, held_qty.get(ticker_up, 0.0))
        is_fav = ticker_up in fav_set
        if only_mine and user_q <= 1e-8:
            continue
        if only_favorites and not is_fav:
            continue
        if q_clean:
            haystack = f"{d.get('ticker','')} {d.get('name','')} {d.get('sector','')}".lower()
            if q_clean not in haystack:
                continue
        d["user_qty"] = round(user_q, 6)
        d["in_portfolio"] = user_q > 1e-8
        d["is_favorite"] = is_fav
        d["monthly_yield_pct"] = (
            round((d["last_dividend_per_share"] / d["last_price"]) * 100.0, 2)
            if d["last_price"] > 0 and d["last_dividend_per_share"] > 0
            else 0.0
        )
        d["class_profile"] = get_asset_specialized_profile(d)
        items.append(d)

    s = sort_by.lower()
    cls_up = asset_class.upper()
    if s == "em_alta":
        items.sort(key=lambda x: x["change_pct"], reverse=True)
    elif s == "em_baixa":
        items.sort(key=lambda x: x["change_pct"], reverse=False)
    elif s == "mais_comprados":
        items.sort(key=lambda x: x["volume_day"], reverse=True)
    elif s == "maior_dividendo":
        if cls_up == "ETF_BR":
            items.sort(key=lambda x: x["class_profile"].get("return_12m_pct", 0.0), reverse=True)
        elif cls_up == "STOCK_US":
            items.sort(key=lambda x: x["class_profile"].get("roe", 0.0), reverse=True)
        elif cls_up == "CRIPTO":
            items.sort(key=lambda x: x["class_profile"].get("return_12m_pct", 0.0), reverse=True)
        else:
            items.sort(key=lambda x: (x["dy_12m"], x["last_dividend_per_share"]), reverse=True)
    elif s == "mais_descontados":
        if cls_up == "ETF_BR":
            items.sort(key=lambda x: x["class_profile"].get("admin_fee_pct", 99.0))
        elif cls_up == "STOCK_US":
            items.sort(key=lambda x: x["pl"] if x["pl"] > 0 else 999.0)
        elif cls_up == "CRIPTO":
            items.sort(key=lambda x: x["class_profile"].get("dominance_pct", 0.0), reverse=True)
        else:
            items.sort(key=lambda x: x["pvp"] if x["pvp"] > 0 else 999.0)

    return {"count": len(items), "assets": items, "favorites": list(fav_set)}


@app.get("/api/asset/{ticker}")
def api_get_asset_detail(ticker: str, period: str = Query("1M"), current_user: Dict[str, Any] = Depends(get_current_user)):
    data = get_asset_chart_and_dividends(ticker, period, user_id=current_user["id"])
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
def api_analyze_asset_report(ticker: str, current_user: Dict[str, Any] = Depends(get_current_user)):
    ticker = ticker.upper().strip()
    conn = get_conn()
    row = conn.execute("SELECT * FROM assets_catalog WHERE ticker = ?", (ticker,)).fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="Ativo não encontrado.")
    rep_data = fetch_official_reports(ticker)
    summary = generate_ai_report_interpretation(dict(row), rep_data.get("reports", []), force_refresh=True)
    return {"status": "ok", "ai_interpretation": summary}


@app.get("/api/lookup-ticker")
def api_lookup_ticker(ticker: str = Query(...), asset_class: str = Query("ACAO_BR"), current_user: Dict[str, Any] = Depends(get_current_user)):
    info = lookup_ticker_live(ticker, asset_class)
    return info


@app.post("/api/transactions")
def api_add_transaction(payload: TransactionCreate, current_user: Dict[str, Any] = Depends(get_current_user)):
    ticker = payload.ticker.upper().strip().replace(".SA", "")
    macro = fetch_macro_indicators()
    fx = float(macro.get("usd_brl", 5.72)) if payload.currency.upper() == "USD" else 1.0

    # Try live lookup first so new tickers get real market price & dividend data
    live_info = lookup_ticker_live(ticker, payload.asset_class.upper())

    conn = get_conn()
    cur = conn.cursor()

    exists = cur.execute("SELECT ticker FROM assets_catalog WHERE ticker = ?", (ticker,)).fetchone()
    if not exists:
        cur.execute("""
            INSERT INTO assets_catalog (
                ticker, name, asset_class, currency, sector, last_price, change_pct,
                volume_day, dy_12m, pl, pvp, last_dividend_per_share, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            ticker,
            live_info.get("name") or ticker,
            payload.asset_class.upper(),
            payload.currency.upper(),
            live_info.get("sector") or "Personalizado",
            live_info.get("last_price") if live_info.get("last_price", 0) > 0 else payload.unit_price,
            live_info.get("change_pct", 0.0),
            1000000,
            live_info.get("dy_12m", 0.0),
            0.0,
            1.0,
            live_info.get("last_dividend_per_share", 0.0),
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        ))

    cur.execute("""
        INSERT INTO transactions (user_id, tx_date, ticker, asset_class, tx_type, quantity, unit_price, fees, currency, fx_rate, broker, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        current_user["id"],
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


@app.delete("/api/portfolio/position/{ticker}")
def api_delete_position_by_ticker(ticker: str, current_user: Dict[str, Any] = Depends(get_current_user)):
    t = ticker.upper().strip()
    conn = get_conn()
    conn.execute("DELETE FROM transactions WHERE user_id = ? AND UPPER(ticker) = ?", (current_user["id"], t))
    conn.commit()
    conn.close()
    return {"status": "ok"}


class AdjustAvgPricePayload(BaseModel):
    avg_price: float


@app.post("/api/portfolio/position/{ticker}/adjust-avg-price")
def api_adjust_position_avg_price(ticker: str, payload: AdjustAvgPricePayload, current_user: Dict[str, Any] = Depends(get_current_user)):
    t = ticker.upper().strip().replace(".SA", "")
    new_pm = float(payload.avg_price)
    if new_pm <= 0:
        raise HTTPException(status_code=400, detail="O Preço Médio deve ser maior que zero.")

    uid = current_user["id"]
    conn = get_conn()
    cur = conn.cursor()

    tx_rows = cur.execute("SELECT * FROM transactions WHERE user_id = ? AND UPPER(ticker) = ? ORDER BY tx_date ASC, id ASC", (uid, t)).fetchall()
    if not tx_rows:
        conn.close()
        raise HTTPException(status_code=404, detail=f"Nenhuma transação encontrada para o ativo {t}.")

    # Current held quantity
    curr_qty = sum(float(r["quantity"]) if r["tx_type"] == "BUY" else -float(r["quantity"]) for r in tx_rows)
    if curr_qty <= 1e-8:
        conn.close()
        raise HTTPException(status_code=400, detail=f"O ativo {t} não possui quantidade em custódia no momento.")

    buys = [r for r in tx_rows if r["tx_type"] == "BUY"]
    if not buys:
        conn.close()
        raise HTTPException(status_code=400, detail=f"O ativo {t} não possui operações de compra registradas.")

    synthetic_txs = [
        r for r in tx_rows
        if any(k in (r["notes"] or "") for k in (
            "Sincronização Posição B3", "Posição B3", "Ajuste de custódia B3",
            "Ajuste de quantidade B3", "Preço Médio informado", "Preço Médio ajustado",
            "estimado pelo fechamento"
        ))
    ]

    if synthetic_txs and len(synthetic_txs) == len(buys):
        # All buys are synthetic/adjustments: update their unit_price directly
        for stx in synthetic_txs:
            cur.execute("""
                UPDATE transactions
                SET unit_price = ?, notes = ?
                WHERE id = ? AND user_id = ?
            """, (round(new_pm, 4), f"Preço Médio informado (R$ {new_pm:.2f})", stx["id"], uid))
    else:
        # Proportionally calibrate buy unit prices so the resulting weighted PM matches new_pm exactly
        cur_cost = sum(float(r["quantity"]) * float(r["unit_price"]) for r in buys)
        target_cost = sum(float(r["quantity"]) for r in buys) * new_pm
        if cur_cost > 0:
            factor = target_cost / cur_cost
            for b in buys:
                new_p = round(float(b["unit_price"]) * factor, 4)
                cur.execute("UPDATE transactions SET unit_price = ? WHERE id = ? AND user_id = ?", (new_p, b["id"], uid))
        else:
            for b in buys:
                cur.execute("UPDATE transactions SET unit_price = ? WHERE id = ? AND user_id = ?", (round(new_pm, 4), b["id"], uid))

    conn.commit()
    conn.close()

    try:
        sync_yfinance_quotes_background()
    except Exception:
        pass

    return {
        "status": "ok",
        "ticker": t,
        "new_avg_price": round(new_pm, 2),
        "message": f"Preço Médio de {t} ajustado para R$ {new_pm:.2f} com sucesso.",
    }


class ClearPortfolioPayload(BaseModel):
    confirmation: str


@app.post("/api/portfolio/clear")
def api_clear_portfolio(payload: ClearPortfolioPayload, current_user: Dict[str, Any] = Depends(get_current_user)):
    if payload.confirmation != "CONFIRMAR_ZERAR_CARTEIRA":
        raise HTTPException(status_code=400, detail="Confirmação necessária para zerar a carteira.")
    uid = current_user["id"]
    conn = get_conn()
    conn.execute("DELETE FROM transactions WHERE user_id = ?", (uid,))
    conn.execute("DELETE FROM fixed_income WHERE user_id = ?", (uid,))
    conn.execute("DELETE FROM dividends_received WHERE user_id = ?", (uid,))
    conn.commit()
    conn.close()
    return {"status": "ok"}


@app.delete("/api/transactions/{tx_id}")
def api_delete_transaction(tx_id: int, current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    conn.execute("DELETE FROM transactions WHERE id = ? AND user_id = ?", (tx_id, current_user["id"]))
    conn.commit()
    conn.close()
    return {"status": "ok"}


@app.post("/api/fixed-income")
def api_add_fixed_income(payload: FixedIncomeCreate, current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    m_val = round(payload.market_value, 2) if (payload.market_value is not None and payload.market_value > 0) else None
    m_net = round(payload.market_net_value, 2) if (payload.market_net_value is not None and payload.market_net_value > 0) else None
    m_date = date.today().isoformat() if m_val else ""
    conn.execute("""
        INSERT INTO fixed_income (
            user_id, title_name, issuer, asset_class, indexer, rate_value,
            invested_amount, start_date, maturity_date, daily_liquidity,
            tax_exempt, broker, market_value, market_net_value, market_value_date
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        current_user["id"],
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
        m_val,
        m_net,
        m_date,
    ))
    conn.commit()
    conn.close()
    return {"status": "ok"}


@app.post("/api/fixed-income/{fi_id}/adjust")
def api_adjust_fixed_income(fi_id: int, payload: FixedIncomeAdjust, current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    cur = conn.cursor()
    row = cur.execute("SELECT * FROM fixed_income WHERE id = ? AND user_id = ?", (fi_id, current_user["id"])).fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Título de renda fixa não encontrado.")

    updates = []
    params = []
    if payload.invested_amount is not None and payload.invested_amount > 0:
        updates.append("invested_amount = ?")
        params.append(round(payload.invested_amount, 2))
    if payload.market_value is not None and payload.market_value > 0:
        updates.append("market_value = ?")
        params.append(round(payload.market_value, 2))
        updates.append("market_value_date = ?")
        params.append(date.today().isoformat())
    if payload.market_net_value is not None and payload.market_net_value > 0:
        updates.append("market_net_value = ?")
        params.append(round(payload.market_net_value, 2))
    if payload.start_date:
        updates.append("start_date = ?")
        params.append(payload.start_date)
    if payload.rate_value is not None and payload.rate_value >= 0:
        updates.append("rate_value = ?")
        params.append(payload.rate_value)

    if updates:
        params.extend([fi_id, current_user["id"]])
        cur.execute(f"UPDATE fixed_income SET {', '.join(updates)} WHERE id = ? AND user_id = ?", tuple(params))
        conn.commit()

    updated = cur.execute("SELECT * FROM fixed_income WHERE id = ? AND user_id = ?", (fi_id, current_user["id"])).fetchone()
    conn.close()
    return {"status": "ok", "fixed_income": dict(updated)}


@app.delete("/api/fixed-income/{fi_id}")
def api_delete_fixed_income(fi_id: int, current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    conn.execute("DELETE FROM fixed_income WHERE id = ? AND user_id = ?", (fi_id, current_user["id"]))
    conn.commit()
    conn.close()
    return {"status": "ok"}


@app.post("/api/dividends")
def api_add_dividend(payload: DividendCreate, current_user: Dict[str, Any] = Depends(get_current_user)):
    total = round(payload.amount_per_share * payload.shares_qty, 2)
    conn = get_conn()
    conn.execute("""
        INSERT INTO dividends_received (user_id, pay_date, ticker, div_type, amount_per_share, shares_qty, total_amount, currency)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        current_user["id"],
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
def api_delete_dividend(div_id: int, current_user: Dict[str, Any] = Depends(get_current_user)):
    conn = get_conn()
    conn.execute("DELETE FROM dividends_received WHERE id = ? AND user_id = ?", (div_id, current_user["id"]))
    conn.commit()
    conn.close()
    return {"status": "ok"}


@app.get("/api/rebalance")
def api_calculate_rebalance(contribution_brl: float = Query(2000.0), current_user: Dict[str, Any] = Depends(get_current_user)):
    summary = get_portfolio_summary(user_id=current_user["id"])
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


class B3FileUploadPayload(BaseModel):
    filename: str
    content_base64: str
    sync_mode: str = "MERGE"
    positions_avg_prices: Optional[Dict[str, float]] = None


@app.post("/api/b3/preview")
def api_b3_preview(payload: B3FileUploadPayload, current_user: Dict[str, Any] = Depends(get_current_user)):
    try:
        raw_b64 = payload.content_base64
        if "," in raw_b64:
            raw_b64 = raw_b64.split(",", 1)[1]
        file_bytes = base64.b64decode(raw_b64)
        parsed = parse_b3_spreadsheet(file_bytes, payload.filename)
        return {"status": "ok", "preview": parsed}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Erro ao ler planilha da B3: {str(exc)}")


@app.post("/api/b3/sync")
def api_b3_sync(payload: B3FileUploadPayload, current_user: Dict[str, Any] = Depends(get_current_user)):
    try:
        raw_b64 = payload.content_base64
        if "," in raw_b64:
            raw_b64 = raw_b64.split(",", 1)[1]
        file_bytes = base64.b64decode(raw_b64)
        parsed = parse_b3_spreadsheet(file_bytes, payload.filename)
        result = apply_b3_sync(parsed, payload.sync_mode, payload.positions_avg_prices, user_id=current_user["id"])
        sync_yfinance_quotes_background()
        return {
            **result,
            "logs": get_b3_sync_logs(8, user_id=current_user["id"]),
        }
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Falha ao sincronizar arquivo B3: {str(exc)}")


@app.get("/api/b3/logs")
def api_get_b3_logs(current_user: Dict[str, Any] = Depends(get_current_user)):
    return {"logs": get_b3_sync_logs(8, user_id=current_user["id"])}


@app.get("/api/b3/template-xlsx")
def api_download_b3_template(current_user: Dict[str, Any] = Depends(get_current_user)):
    xlsx_bytes = generate_b3_template_xlsx()
    return Response(
        content=xlsx_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="Modelo_B3_SIM.xlsx"'},
    )


@app.get("/api/b3/export-xlsx")
def api_export_b3_portfolio(current_user: Dict[str, Any] = Depends(get_current_user)):
    summary = get_portfolio_summary(user_id=current_user["id"])
    xlsx_bytes = export_portfolio_b3_xlsx(summary)
    date_tag = datetime.now().strftime("%Y-%m-%d")
    return Response(
        content=xlsx_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="Carteira_B3_SIM_{date_tag}.xlsx"'},
    )


class SettingsUpdatePayload(BaseModel):
    ai_provider: Optional[str] = None
    ai_model: Optional[str] = None
    ai_api_key: Optional[str] = None
    investor_profile: Optional[str] = None
    min_dy_target: Optional[float] = None
    whatsapp_enabled: Optional[bool] = None
    whatsapp_provider: Optional[str] = None
    whatsapp_phone: Optional[str] = None
    whatsapp_apikey: Optional[str] = None
    whatsapp_instance_url: Optional[str] = None
    whatsapp_instance_id: Optional[str] = None
    whatsapp_daily_time: Optional[str] = None
    whatsapp_notify_opportunities: Optional[bool] = None


class AiTestPayload(BaseModel):
    ai_provider: str = "GEMINI"
    ai_model: str = "gemini-2.5-flash"
    ai_api_key: str = ""


@app.get("/api/settings")
def api_get_settings(current_user: Dict[str, Any] = Depends(get_current_user)):
    return get_public_settings(user_id=current_user["id"])


@app.post("/api/settings")
def api_save_settings(payload: SettingsUpdatePayload, current_user: Dict[str, Any] = Depends(get_current_user)):
    updated = update_app_settings(payload.model_dump(exclude_none=True), user_id=current_user["id"])
    return {"status": "ok", "settings": updated}


@app.post("/api/ai/test")
def api_test_ai(payload: AiTestPayload, current_user: Dict[str, Any] = Depends(get_current_user)):
    try:
        res = test_ai_connection(payload.ai_provider, payload.ai_model, payload.ai_api_key, user_id=current_user["id"])
        return res
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.get("/api/ai/radar")
def api_get_ai_radar(force: bool = Query(False), current_user: Dict[str, Any] = Depends(get_current_user)):
    return generate_portfolio_and_market_radar(force_refresh=force, user_id=current_user["id"])


class WhatsAppTestPayload(BaseModel):
    phone: str = ""
    message: Optional[str] = None


@app.post("/api/whatsapp/test")
def api_whatsapp_test(payload: WhatsAppTestPayload, current_user: Dict[str, Any] = Depends(get_current_user)):
    try:
        msg = payload.message or "🚀 Olá! Esta é uma mensagem de teste do SIM (Scherer Investments Money). Sua integração com o WhatsApp está funcionando perfeitamente!"
        res = send_whatsapp_message(msg, custom_phone=payload.phone, user_id=current_user["id"])
        return res
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/api/whatsapp/dispatch-daily")
def api_whatsapp_dispatch_daily(force: bool = Query(False), current_user: Dict[str, Any] = Depends(get_current_user)):
    try:
        res = trigger_daily_whatsapp_dispatch(force=force, user_id=current_user["id"])
        return res
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.get("/api/whatsapp/status")
def api_whatsapp_status(current_user: Dict[str, Any] = Depends(get_current_user)):
    return get_whatsapp_scheduler_status(user_id=current_user["id"])


@app.get("/api/whatsapp/preview-daily")
def api_whatsapp_preview_daily(current_user: Dict[str, Any] = Depends(get_current_user)):
    radar_data = generate_portfolio_and_market_radar(force_refresh=False, user_id=current_user["id"])
    msg = format_daily_whatsapp_message(radar_data)
    return {"message": msg}


@app.get("/api/system/mobile-access")
def api_mobile_access(current_user: Dict[str, Any] = Depends(get_current_user)):
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


@app.get("/favicon.ico")
def get_favicon():
    return FileResponse(os.path.join(STATIC_DIR, "icon.ico"))


@app.get("/sw.js")
def get_sw():
    return FileResponse(os.path.join(STATIC_DIR, "sw.js"))


@app.get("/")
def serve_index():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))
