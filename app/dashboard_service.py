"""
Dashboard da Etapa 2: consolida carteira, distribuicao, concentracao, proventos e evolucao.

Reaproveita get_portfolio_summary (fonte unica dos calculos). Este modulo apenas filtra,
agrega e confere totais; nenhuma regra financeira e redefinida aqui.

Dados nao disponiveis nao sao inventados:
  * historico de patrimonio so existe a partir dos snapshots diarios gravados pelo SIM;
  * aportes liquidos sao reconstruidos das operacoes registradas (fato), nao do valor de mercado passado;
  * rentabilidade do periodo so e calculada quando ha pelo menos dois snapshots no periodo.
"""
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional

from . import market_service
from .database import get_conn

PERIODS = ("1M", "3M", "6M", "12M", "YTD", "ALL")
BUY_TYPES = ("BUY", "COMPRA")
SELL_TYPES = ("SELL", "VENDA")

COUNTRY_LABELS = {"BR": "Brasil", "US": "Estados Unidos", "GLOBAL": "Global (cripto)"}


def country_of(asset_class: str) -> str:
    """Pais de exposicao inferido da classe do ativo (STOCK_US -> EUA, CRIPTO -> Global, demais -> Brasil)."""
    if asset_class == "STOCK_US":
        return "US"
    if asset_class == "CRIPTO":
        return "GLOBAL"
    return "BR"


def period_start(period: str, today: Optional[date] = None) -> Optional[date]:
    today = today or date.today()
    p = (period or "ALL").upper()
    if p == "1M":
        return today - timedelta(days=30)
    if p == "3M":
        return today - timedelta(days=91)
    if p == "6M":
        return today - timedelta(days=182)
    if p == "12M":
        return today - timedelta(days=365)
    if p == "YTD":
        return date(today.year, 1, 1)
    return None


def _norm(v: Optional[str]) -> str:
    v = (v or "ALL").strip().upper()
    return v or "ALL"


def _match(filters: Dict[str, str], asset_class: str, currency: str) -> bool:
    if filters["asset_class"] != "ALL" and asset_class != filters["asset_class"]:
        return False
    if filters["currency"] != "ALL" and (currency or "BRL").upper() != filters["currency"]:
        return False
    if filters["country"] != "ALL" and country_of(asset_class) != filters["country"]:
        return False
    return True


def _holdings(summary: Dict[str, Any]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for p in summary.get("positions", []):
        cur = (p.get("currency") or "BRL").upper()
        out.append({
            "id": f"VAR_{p['ticker']}",
            "code": p["ticker"],
            "name": p.get("name") or p["ticker"],
            "asset_class": p["asset_class"],
            "country": country_of(p["asset_class"]),
            "currency": cur,
            "sector": (p.get("sector") or "").strip() or "Não informado",
            "invested_brl": float(p["invested_brl"]),
            "current_brl": float(p["current_brl"]),
            "profit_brl": float(p["profit_brl"]),
            "profit_pct": float(p["profit_pct"]),
            "is_fixed_income": False,
            "current_native": float(p.get("current_native", 0.0)) if cur != "BRL" else None,
            "fx_current": float(p.get("fx_current", 1.0)),
            "avg_fx": round(float(p.get("avg_fx", 1.0)), 4) if cur != "BRL" else None,
            "is_stale": bool(p.get("is_stale")),
            "updated_at": p.get("updated_at") or "",
        })
    for f in summary.get("fixed_income", []):
        invested = float(f["invested_amount"])
        current = float(f["net_amount"])
        out.append({
            "id": f"FI_{f['id']}",
            "code": f["title_name"],
            "name": f"{f['issuer']} ({f['rate_label']})",
            "asset_class": f["asset_class"],
            "country": "BR",
            "currency": "BRL",
            "sector": "Renda fixa",
            "invested_brl": round(invested, 2),
            "current_brl": round(current, 2),
            "profit_brl": round(float(f["net_profit"]), 2),
            "profit_pct": float(f["net_profit_pct"]),
            "is_fixed_income": True,
            "current_native": None,
            "fx_current": 1.0,
            "avg_fx": None,
            "is_stale": False,
            "updated_at": f.get("value_anchor_date") or "",
        })
    return out


def _group(holdings: List[Dict[str, Any]], key: str, total_current: float, labels: Optional[Dict[str, str]] = None):
    groups: Dict[str, Dict[str, Any]] = {}
    for h in holdings:
        k = h[key]
        g = groups.setdefault(k, {"key": k, "label": (labels or {}).get(k, k), "count": 0,
                                  "invested_brl": 0.0, "current_brl": 0.0, "current_native": 0.0})
        g["count"] += 1
        g["invested_brl"] += h["invested_brl"]
        g["current_brl"] += h["current_brl"]
        if h.get("current_native") is not None:
            g["current_native"] += h["current_native"]
    rows = []
    for g in groups.values():
        profit = g["current_brl"] - g["invested_brl"]
        rows.append({
            "key": g["key"],
            "label": g["label"],
            "count": g["count"],
            "invested_brl": round(g["invested_brl"], 2),
            "current_brl": round(g["current_brl"], 2),
            "current_native": round(g["current_native"], 2) if g["current_native"] else None,
            "profit_brl": round(profit, 2),
            "profit_pct": round(profit / g["invested_brl"] * 100.0, 2) if g["invested_brl"] > 0 else 0.0,
            "weight_pct": round(g["current_brl"] / total_current * 100.0, 2) if total_current > 0 else 0.0,
        })
    rows.sort(key=lambda r: r["current_brl"], reverse=True)
    return rows


def _concentration(holdings: List[Dict[str, Any]], total_current: float) -> Dict[str, Any]:
    ranked = sorted(holdings, key=lambda h: h["current_brl"], reverse=True)
    weights = [(h["current_brl"] / total_current) if total_current > 0 else 0.0 for h in ranked]
    hhi = sum(w * w for w in weights)
    return {
        "top": [
            {"code": h["code"], "name": h["name"], "asset_class": h["asset_class"],
             "current_brl": round(h["current_brl"], 2), "weight_pct": round(w * 100.0, 2)}
            for h, w in list(zip(ranked, weights))[:10]
        ],
        "top1_pct": round(weights[0] * 100.0, 2) if weights else 0.0,
        "top5_pct": round(sum(weights[:5]) * 100.0, 2),
        "top10_pct": round(sum(weights[:10]) * 100.0, 2),
        "hhi": round(hhi * 10000.0, 0),  # 0-10000; quanto maior, mais concentrada
        "effective_positions": round(1.0 / hhi, 1) if hhi > 0 else 0.0,
        "holdings_count": len(holdings),
    }


def _class_map_for(tickers: List[str]) -> Dict[str, str]:
    if not tickers:
        return {}
    conn = get_conn()
    marks = ",".join("?" for _ in tickers)
    rows = conn.execute(f"SELECT ticker, asset_class FROM assets_catalog WHERE ticker IN ({marks})", tickers).fetchall()
    conn.close()
    return {r["ticker"]: r["asset_class"] for r in rows}


def _dividends(summary: Dict[str, Any], filters: Dict[str, str], start: Optional[date]) -> Dict[str, Any]:
    divs = summary.get("dividends", [])
    cmap = _class_map_for(sorted({d["ticker"] for d in divs}))
    tx_class = {t["ticker"].upper(): t["asset_class"] for t in summary.get("transactions", [])}

    selected = []
    for d in divs:
        cls = cmap.get(d["ticker"]) or tx_class.get(d["ticker"].upper()) or ""
        if filters["asset_class"] != "ALL" and cls != filters["asset_class"]:
            continue
        if filters["currency"] != "ALL" and (d.get("currency") or "BRL").upper() != filters["currency"]:
            continue
        if filters["country"] != "ALL" and country_of(cls) != filters["country"]:
            continue
        selected.append(d)

    def in_period(d):
        try:
            return start is None or datetime.strptime(str(d["pay_date"])[:10], "%Y-%m-%d").date() >= start
        except ValueError:
            return False

    in_range = [d for d in selected if in_period(d)]

    def agg(rows, keyfn):
        acc: Dict[str, float] = {}
        for d in rows:
            acc[keyfn(d)] = acc.get(keyfn(d), 0.0) + float(d["total_brl"])
        return acc

    by_month = agg(in_range, lambda d: str(d["pay_date"])[:7])
    by_year = agg(selected, lambda d: str(d["pay_date"])[:4])
    by_ticker = agg(in_range, lambda d: d["ticker"])

    by_currency: Dict[str, float] = {}
    for d in in_range:
        c = (d.get("currency") or "BRL").upper()
        by_currency[c] = by_currency.get(c, 0.0) + float(d["total_amount"])

    return {
        "total_brl": round(sum(float(d["total_brl"]) for d in in_range), 2),
        "count": len(in_range),
        "by_month": [{"month": k, "total_brl": round(v, 2)} for k, v in sorted(by_month.items())],
        "by_year": [{"year": k, "total_brl": round(v, 2)} for k, v in sorted(by_year.items())],
        "by_ticker": sorted(
            [{"ticker": k, "total_brl": round(v, 2)} for k, v in by_ticker.items()],
            key=lambda r: r["total_brl"], reverse=True,
        ),
        "by_currency_original": {k: round(v, 2) for k, v in by_currency.items()},
        "has_estimated_fx": any(d.get("fx_estimated") for d in in_range),
    }


def _contributions(summary: Dict[str, Any], filters: Dict[str, str]) -> List[Dict[str, Any]]:
    """Movimentos de aporte/retirada em BRL reconstruidos das operacoes e da renda fixa registradas."""
    moves: List[Dict[str, Any]] = []
    for t in summary.get("transactions", []):
        cur = (t.get("currency") or "BRL").upper()
        if not _match(filters, t["asset_class"], cur):
            continue
        fx = float(t.get("fx_rate") or 1.0) if cur == "USD" else 1.0
        q, p, fee = float(t["quantity"]), float(t["unit_price"]), float(t.get("fees") or 0.0)
        typ = str(t["tx_type"]).upper().strip()
        if typ in BUY_TYPES:
            amount = (q * p + fee) * fx
        elif typ in SELL_TYPES:
            amount = -((q * p - fee) * fx)
        else:
            continue
        moves.append({"date": str(t["tx_date"])[:10], "amount_brl": amount})
    for f in summary.get("fixed_income", []):
        if not _match(filters, f["asset_class"], "BRL"):
            continue
        moves.append({"date": str(f["start_date"])[:10], "amount_brl": float(f["invested_amount"])})
    return moves


def _evolution(moves: List[Dict[str, Any]], start: Optional[date]) -> List[Dict[str, Any]]:
    by_month: Dict[str, float] = {}
    for m in moves:
        by_month[m["date"][:7]] = by_month.get(m["date"][:7], 0.0) + m["amount_brl"]
    series, cumulative = [], 0.0
    start_month = start.strftime("%Y-%m") if start else None
    for month in sorted(by_month):
        cumulative += by_month[month]
        if start_month is None or month >= start_month:
            series.append({"month": month, "net_contribution_brl": round(by_month[month], 2),
                           "cumulative_contribution_brl": round(cumulative, 2)})
    return series


def record_snapshot(user_id: int, kpis: Dict[str, Any], usd_brl: float, today: Optional[date] = None) -> bool:
    """Grava (ou atualiza) o snapshot do dia com o patrimonio atual. Retorna False se carteira vazia."""
    if float(kpis.get("total_current_brl") or 0.0) <= 0:
        return False
    d = (today or date.today()).strftime("%Y-%m-%d")
    conn = get_conn()
    conn.execute(
        "INSERT INTO portfolio_snapshots (user_id, snap_date, total_current_brl, total_invested_brl, usd_brl) "
        "VALUES (?, ?, ?, ?, ?) "
        "ON CONFLICT(user_id, snap_date) DO UPDATE SET total_current_brl = excluded.total_current_brl, "
        "total_invested_brl = excluded.total_invested_brl, usd_brl = excluded.usd_brl, created_at = CURRENT_TIMESTAMP",
        (user_id, d, float(kpis["total_current_brl"]), float(kpis["total_invested_brl"]), float(usd_brl or 0.0)),
    )
    conn.commit()
    conn.close()
    return True


def _snapshots(user_id: int, start: Optional[date]) -> List[Dict[str, Any]]:
    conn = get_conn()
    if start:
        rows = conn.execute(
            "SELECT snap_date, total_current_brl, total_invested_brl, usd_brl FROM portfolio_snapshots "
            "WHERE user_id = ? AND snap_date >= ? ORDER BY snap_date", (user_id, start.strftime("%Y-%m-%d"))).fetchall()
    else:
        rows = conn.execute(
            "SELECT snap_date, total_current_brl, total_invested_brl, usd_brl FROM portfolio_snapshots "
            "WHERE user_id = ? ORDER BY snap_date", (user_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def _period_return(snaps: List[Dict[str, Any]], moves: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Retorno do periodo pelo metodo Dietz modificado, entre o primeiro e o ultimo snapshot do periodo."""
    if len(snaps) < 2:
        return {"available": False,
                "reason": "Histórico insuficiente: o SIM precisa de ao menos dois dias registrados no período."}
    s0, s1 = snaps[0], snaps[-1]
    d0, d1 = s0["snap_date"], s1["snap_date"]
    flows = [m for m in moves if d0 < m["date"] <= d1]
    c = sum(m["amount_brl"] for m in flows)
    v0, v1 = float(s0["total_current_brl"]), float(s1["total_current_brl"])
    gain = v1 - v0 - c
    denom = v0 + c / 2.0
    return {
        "available": True,
        "method": "Dietz modificado (aportes líquidos do período ponderados a 50%)",
        "from": d0, "to": d1,
        "start_value_brl": round(v0, 2), "end_value_brl": round(v1, 2),
        "net_contributions_brl": round(c, 2),
        "gain_brl": round(gain, 2),
        "return_pct": round(gain / denom * 100.0, 2) if denom > 0 else None,
    }


def get_dashboard(user_id: int = 1, period: str = "ALL", country: str = "ALL", currency: str = "ALL",
                  asset_class: str = "ALL", record: bool = True) -> Dict[str, Any]:
    period = _norm(period)
    if period not in PERIODS:
        period = "ALL"
    filters = {"country": _norm(country), "currency": _norm(currency), "asset_class": _norm(asset_class)}
    is_filtered = any(v != "ALL" for v in filters.values())
    start = period_start(period)

    summary = market_service.get_portfolio_summary(user_id=user_id)
    macro = summary.get("macro", {})
    usd_brl = float(macro.get("usd_brl") or 0.0)

    all_holdings = _holdings(summary)
    holdings = [h for h in all_holdings if _match(filters, h["asset_class"], h["currency"])]

    total_current = sum(h["current_brl"] for h in holdings)
    total_invested = sum(h["invested_brl"] for h in holdings)
    profit = total_current - total_invested
    for h in holdings:
        h["weight_pct"] = round(h["current_brl"] / total_current * 100.0, 2) if total_current > 0 else 0.0

    kpis_src = summary["kpis"]
    tol = 0.01 * max(1, len(all_holdings))
    recon: Dict[str, Any] = {"checked": not is_filtered}
    if not is_filtered:
        full_current = sum(h["current_brl"] for h in all_holdings)
        full_invested = sum(h["invested_brl"] for h in all_holdings)
        recon.update({
            "diff_current_brl": round(full_current - float(kpis_src["total_current_brl"]), 2),
            "diff_invested_brl": round(full_invested - float(kpis_src["total_invested_brl"]), 2),
            "tolerance_brl": round(tol, 2),
        })
        recon["ok"] = abs(recon["diff_current_brl"]) <= tol and abs(recon["diff_invested_brl"]) <= tol

    snapshot_recorded = False
    if record and not is_filtered:
        try:
            snapshot_recorded = record_snapshot(user_id, kpis_src, usd_brl)
        except Exception:
            snapshot_recorded = False

    moves = _contributions(summary, filters)
    snaps = _snapshots(user_id, start) if not is_filtered else []
    all_snaps_first = None
    if not is_filtered:
        first = _snapshots(user_id, None)
        all_snaps_first = first[0]["snap_date"] if first else None

    stale = [h for h in holdings if not h["is_fixed_income"] and h["is_stale"]]
    quote_dates = [h["updated_at"] for h in holdings if not h["is_fixed_income"] and h["updated_at"]]

    fx_ts = macro.get("usd_brl_updated_at") or None
    usd_holdings = [h for h in holdings if h["currency"] == "USD"]

    return {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "filters": {"period": period, **filters},
        "kpis": {
            "total_current_brl": round(total_current, 2),
            "total_invested_brl": round(total_invested, 2),
            "profit_brl": round(profit, 2),
            "profit_pct": round(profit / total_invested * 100.0, 2) if total_invested > 0 else 0.0,
            "holdings_count": len(holdings),
            "realized_profit_brl": round(float(kpis_src["realized_profit_brl"]), 2) if not is_filtered else None,
            "realized_note": None if not is_filtered else "Resultado realizado só é exibido para a carteira completa.",
        },
        "fx": {
            "usd_brl": round(usd_brl, 4),
            "updated_at": fx_ts,
            "is_live": bool(fx_ts),
            "source": "AwesomeAPI (cotação atual)" if fx_ts else "Valor padrão (câmbio ainda não atualizado)",
            "usd_holdings": len(usd_holdings),
            "note": ("Valor atual em USD convertido pelo câmbio acima. O custo em BRL usa o câmbio de cada compra; "
                     "o lucro em BRL inclui, portanto, o efeito cambial."),
        },
        "data_quality": {
            "positions_with_stale_quote": len(stale),
            "positions_total": len([h for h in holdings if not h["is_fixed_income"]]),
            "oldest_quote_at": min(quote_dates) if quote_dates else None,
            "stale_codes": [h["code"] for h in stale][:20],
        },
        "distribution": {
            "by_class": _group(holdings, "asset_class", total_current, market_service_class_labels()),
            "by_country": _group(holdings, "country", total_current, COUNTRY_LABELS),
            "by_currency": _group(holdings, "currency", total_current),
            "by_sector": _group(holdings, "sector", total_current),
        },
        "concentration": _concentration(holdings, total_current),
        "holdings": sorted(holdings, key=lambda h: h["current_brl"], reverse=True),
        "dividends": _dividends(summary, filters, start),
        "evolution": {
            "contributions": _evolution(moves, start),
            "contributions_note": "Aportes líquidos reconstruídos das operações e aplicações registradas "
                                  "(compras − vendas, em BRL pelo câmbio da operação).",
            "snapshots": [{"date": s["snap_date"], "total_current_brl": round(s["total_current_brl"], 2),
                           "total_invested_brl": round(s["total_invested_brl"], 2)} for s in snaps],
            "snapshots_since": all_snaps_first,
            "snapshot_recorded_today": snapshot_recorded,
            "snapshots_note": ("Histórico de patrimônio registrado pelo SIM a cada dia de uso; não há dados "
                               "anteriores à primeira data registrada." if not is_filtered else
                               "O histórico de patrimônio só é registrado para a carteira completa (sem filtros)."),
            "period_return": _period_return(snaps, moves) if not is_filtered else
                             {"available": False, "reason": "Rentabilidade do período só é calculada para a carteira completa."},
        },
        "reconciliation": recon,
        "benchmark": {"available": False,
                      "reason": "Comparação com índices não implementada: não há série histórica confiável "
                                "de índices armazenada (previsto para a Etapa 3)."},
    }


def market_service_class_labels() -> Dict[str, str]:
    return {
        "FII": "Fundos Imobiliários", "ACAO_BR": "Ações Brasileiras", "CAIXINHA": "Caixinhas e Liquidez",
        "RENDA_FIXA": "CDB, LCI, LCA e Renda Fixa", "TESOURO": "Tesouro Direto", "FUNDO_INV": "Fundos de Investimento",
        "ETF_BR": "ETFs e BDRs", "STOCK_US": "Stocks EUA", "CRIPTO": "Criptomoedas",
    }
