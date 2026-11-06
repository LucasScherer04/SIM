"""
Adaptadores substituíveis de dados de mercado, câmbio, indicadores macro e notícias (Etapa 3).

Princípios:
  * Persistência em SQLite (`market_history_cache`, `asset_news_cache`, `macro_indicators_cache`).
  * Identificação explícita de fonte (`source`), data/hora (`updated_at`), moeda (`currency`) e estado
    do dado (`LIVE`, `CACHED`, `CATALOG`, `EMPTY`, `UNAVAILABLE`).
  * Falhas externas nunca bloqueiam o uso do aplicativo nem geram séries ou manchetes fictícias.
"""
import html
import json
import math
import re
import sqlite3
import statistics
import urllib.parse
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional, Tuple

import feedparser
import requests
import yfinance as yf

from .database import get_conn, migrate_market_cache_tables

PERIOD_MAP: Dict[str, Tuple[str, str]] = {
    "1D": ("1d", "5m"),
    "5D": ("5d", "30m"),
    "1M": ("1mo", "1d"),
    "6M": ("6mo", "1d"),
    "1Y": ("1y", "1d"),
    "5Y": ("5y", "1wk"),
    "10Y": ("10y", "1mo"),
    "MAX": ("max", "1mo"),
}


def _now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _age_seconds(ts_str: Optional[str]) -> float:
    if not ts_str:
        return float("inf")
    try:
        dt = datetime.strptime(str(ts_str).strip()[:19], "%Y-%m-%d %H:%M:%S")
        return max(0.0, (datetime.now() - dt).total_seconds())
    except Exception:
        return float("inf")


def _strip_html(raw: str) -> str:
    if not raw:
        return ""
    text = re.sub(r"<[^>]+>", " ", raw)
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def market_of(asset_class: str) -> str:
    cls = (asset_class or "ACAO_BR").upper()
    if cls == "STOCK_US":
        return "US"
    if cls == "CRIPTO":
        return "GLOBAL"
    return "BR"


def provider_label_for(asset_class: str, ticker: str = "") -> str:
    if ticker in ("^BVSP", "^GSPC"):
        return "Yahoo Finance (Índice)"
    cls = (asset_class or "ACAO_BR").upper()
    if cls in ("ACAO_BR", "FII", "ETF_BR"):
        return "Yahoo Finance (B3 .SA)"
    if cls == "STOCK_US":
        return "Yahoo Finance (NYSE/NASDAQ)"
    if cls == "CRIPTO":
        return "Yahoo Finance (Crypto USD)"
    return "Yahoo Finance"


def yf_symbol_for(ticker: str, asset_class: str) -> str:
    t = ticker.upper().strip()
    if t.startswith("^"):
        return t
    cls = (asset_class or "ACAO_BR").upper()
    if cls in ("ACAO_BR", "FII", "ETF_BR"):
        return t if t.endswith(".SA") else f"{t}.SA"
    if cls == "CRIPTO":
        return t if t.endswith("-USD") else f"{t}-USD"
    return t


class YahooFinanceAdapter:
    """Adaptador de cotações e histórico para Brasil (B3) e EUA (NYSE/NASDAQ) com cache em SQLite."""

    def fetch_live_history(self, ticker: str, asset_class: str, period_key: str) -> List[Dict[str, Any]]:
        p_up = (period_key or "1M").upper()
        yf_period, yf_interval = PERIOD_MAP.get(p_up, ("1mo", "1d"))
        yf_sym = yf_symbol_for(ticker, asset_class)
        points: List[Dict[str, Any]] = []

        tk = yf.Ticker(yf_sym)
        hist = tk.history(period=yf_period, interval=yf_interval)
        if hist is None or hist.empty:
            return []

        for idx, row in hist.iterrows():
            val = float(row["Close"])
            if math.isnan(val) or val <= 0:
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
        return points

    def get_history(
        self,
        ticker: str,
        asset_class: str,
        period_key: str = "1M",
        currency: str = "BRL",
        ttl_seconds: int = 300,
        allow_network: bool = True,
    ) -> Dict[str, Any]:
        t_up = ticker.upper().strip()
        p_up = (period_key or "1M").upper()
        source_label = provider_label_for(asset_class, t_up)

        conn = get_conn()
        try:
            cached_row = conn.execute(
                "SELECT points_json, source, currency, fetched_at FROM market_history_cache WHERE ticker = ? AND period = ?",
                (t_up, p_up),
            ).fetchone()
        except sqlite3.OperationalError:
            migrate_market_cache_tables(conn)
            cached_row = None
        finally:
            conn.close()

        cached_points: List[Dict[str, Any]] = []
        cached_source = source_label
        cached_at = ""
        if cached_row:
            try:
                cached_points = json.loads(cached_row["points_json"] or "[]")
                cached_source = cached_row["source"] or source_label
                cached_at = cached_row["fetched_at"] or ""
            except Exception:
                cached_points = []

        if cached_points and _age_seconds(cached_at) <= ttl_seconds:
            return {
                "points": cached_points,
                "source": cached_source,
                "currency": cached_row["currency"] or currency,
                "updated_at": cached_at,
                "data_state": "CACHED",
                "is_fresh": True,
                "is_synthetic": False,
                "warning": "",
            }

        if allow_network:
            try:
                live_points = self.fetch_live_history(t_up, asset_class, p_up)
                if len(live_points) >= 2:
                    now_str = _now_str()
                    conn = get_conn()
                    conn.execute(
                        """
                        INSERT INTO market_history_cache (ticker, period, points_json, source, currency, fetched_at)
                        VALUES (?, ?, ?, ?, ?, ?)
                        ON CONFLICT(ticker, period) DO UPDATE SET
                            points_json = excluded.points_json,
                            source = excluded.source,
                            currency = excluded.currency,
                            fetched_at = excluded.fetched_at
                        """,
                        (t_up, p_up, json.dumps(live_points), source_label, currency, now_str),
                    )
                    conn.commit()
                    conn.close()
                    return {
                        "points": live_points,
                        "source": source_label,
                        "currency": currency,
                        "updated_at": now_str,
                        "data_state": "LIVE",
                        "is_fresh": True,
                        "is_synthetic": False,
                        "warning": "",
                    }
            except Exception:
                pass

        if len(cached_points) >= 2:
            return {
                "points": cached_points,
                "source": cached_source,
                "currency": (cached_row["currency"] if cached_row else currency) or currency,
                "updated_at": cached_at,
                "data_state": "CACHED",
                "is_fresh": False,
                "is_synthetic": False,
                "warning": (
                    f"Sem resposta do provedor externo no momento; exibindo o último histórico real "
                    f"armazenado em cache local ({cached_at})."
                ),
            }

        return {
            "points": [],
            "source": source_label,
            "currency": currency,
            "updated_at": "",
            "data_state": "UNAVAILABLE",
            "is_fresh": False,
            "is_synthetic": False,
            "warning": (
                "Série histórica indisponível: não foi possível consultar o provedor externo "
                "e ainda não há histórico salvo em cache local para este período."
            ),
        }


def compute_historical_stats(points: List[Dict[str, Any]], current_price: float, currency: str = "BRL") -> Dict[str, Any]:
    """
    Calcula métricas estatísticas do período a partir dos pontos observados.
    Separado explicitamente como CALCULO_SIM (não é dado bruto do provedor nem opinião de IA).
    """
    prices = [float(p["price"]) for p in points if float(p.get("price", 0)) > 0]
    if len(prices) < 2:
        return {
            "available": False,
            "kind": "CALCULO_SIM",
            "currency": currency,
            "reason": "Série histórica insuficiente para calcular faixas e médias do período.",
            "methodology_note": (
                "Sem série histórica disponível. O SIM não inventa cotações passadas quando o provedor "
                "está inacessível e não há cache local."
            ),
        }

    min_p = min(prices)
    max_p = max(prices)
    avg_p = sum(prices) / len(prices)
    med_p = statistics.median(prices)
    cur_p = float(current_price) if current_price and current_price > 0 else prices[-1]

    dist_avg_pct = ((cur_p - avg_p) / avg_p * 100.0) if avg_p > 0 else 0.0
    dist_high_pct = ((cur_p - max_p) / max_p * 100.0) if max_p > 0 else 0.0
    dist_low_pct = ((cur_p - min_p) / min_p * 100.0) if min_p > 0 else 0.0
    pos_in_range_pct = ((cur_p - min_p) / (max_p - min_p) * 100.0) if max_p > min_p else 50.0

    step_returns = [
        (prices[i] - prices[i - 1]) / prices[i - 1] * 100.0
        for i in range(1, len(prices))
        if prices[i - 1] > 0
    ]
    vol_step_pct = statistics.stdev(step_returns) if len(step_returns) >= 2 else 0.0

    return {
        "available": True,
        "kind": "CALCULO_SIM",
        "currency": currency,
        "points_count": len(prices),
        "first_date": points[0].get("label", ""),
        "last_date": points[-1].get("label", ""),
        "current_price": round(cur_p, 2),
        "min_price": round(min_p, 2),
        "max_price": round(max_p, 2),
        "avg_price": round(avg_p, 2),
        "median_price": round(med_p, 2),
        "distance_from_avg_pct": round(dist_avg_pct, 2),
        "distance_from_high_pct": round(dist_high_pct, 2),
        "distance_from_low_pct": round(dist_low_pct, 2),
        "position_in_range_pct": round(max(0.0, min(100.0, pos_in_range_pct)), 1),
        "step_volatility_pct": round(vol_step_pct, 2),
        "methodology_note": (
            "Cálculo estatístico do SIM sobre a série histórica observada no período. "
            "Estar abaixo ou acima da média histórica não significa que o ativo esteja barato ou caro: "
            "avalie fundamentos, proventos, eventos corporativos, juros, inflação e câmbio."
        ),
    }


def compute_benchmark_comparison(
    adapter: YahooFinanceAdapter,
    asset_points: List[Dict[str, Any]],
    asset_class: str,
    period_key: str,
    allow_network: bool = True,
) -> Dict[str, Any]:
    """Compara o retorno percentual do ativo no período com o índice de referência apropriado (IBOV ou S&P 500)."""
    cls = (asset_class or "ACAO_BR").upper()
    if cls == "STOCK_US":
        bench_symbol, bench_name, bench_currency = "^GSPC", "S&P 500", "USD"
    elif cls == "CRIPTO":
        bench_symbol, bench_name, bench_currency = "^GSPC", "S&P 500 (Ref. USD)", "USD"
    else:
        bench_symbol, bench_name, bench_currency = "^BVSP", "Ibovespa (IBOV)", "BRL"

    if len(asset_points) < 2:
        return {
            "available": False,
            "kind": "CALCULO_SIM",
            "benchmark_symbol": bench_symbol,
            "benchmark_name": bench_name,
            "reason": "Série histórica do ativo indisponível para comparação no período.",
        }

    bench_hist = adapter.get_history(
        bench_symbol,
        asset_class="INDEX",
        period_key=period_key,
        currency=bench_currency,
        ttl_seconds=600,
        allow_network=allow_network,
    )
    b_pts = bench_hist.get("points") or []
    if len(b_pts) < 2 or b_pts[0]["price"] <= 0 or asset_points[0]["price"] <= 0:
        return {
            "available": False,
            "kind": "CALCULO_SIM",
            "benchmark_symbol": bench_symbol,
            "benchmark_name": bench_name,
            "reason": "Série histórica do índice de referência indisponível no momento.",
        }

    asset_ret = (asset_points[-1]["price"] - asset_points[0]["price"]) / asset_points[0]["price"] * 100.0
    bench_ret = (b_pts[-1]["price"] - b_pts[0]["price"]) / b_pts[0]["price"] * 100.0
    diff_pp = asset_ret - bench_ret

    return {
        "available": True,
        "kind": "CALCULO_SIM",
        "benchmark_symbol": bench_symbol,
        "benchmark_name": bench_name,
        "benchmark_currency": bench_currency,
        "period": (period_key or "1M").upper(),
        "asset_return_pct": round(asset_ret, 2),
        "benchmark_return_pct": round(bench_ret, 2),
        "relative_diff_pp": round(diff_pp, 2),
        "source": bench_hist.get("source") or "Yahoo Finance (Índice)",
        "updated_at": bench_hist.get("updated_at") or "",
        "data_state": bench_hist.get("data_state") or "LIVE",
        "note": "Comparação simples de preço no período selecionado (não inclui reinvestimento de dividendos em ações/FIIs).",
    }


class AwesomeBcbMacroAdapter:
    """
    Adaptador de câmbio (USD/BRL, EUR/BRL) e indicadores macro (Selic, CDI, IPCA 12m)
    com persistência em `macro_indicators_cache` e fallback entre AwesomeAPI e Banco Central (SGS).
    """

    def load_cached_into(self, target_cache: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
        conn = get_conn()
        try:
            rows = conn.execute("SELECT key, value, change_pct, source, fetched_at FROM macro_indicators_cache").fetchall()
        except sqlite3.OperationalError:
            migrate_market_cache_tables(conn)
            rows = []
        finally:
            conn.close()
        sources: Dict[str, Dict[str, Any]] = {}
        change_key_map = {
            "usd_brl": "usd_change",
            "eur_brl": "eur_change",
            "btc_usd": "btc_change",
            "ibov": "ibov_change",
            "sp500": "sp500_change",
        }
        for r in rows:
            k = r["key"]
            target_cache[k] = float(r["value"])
            if k in change_key_map:
                target_cache[change_key_map[k]] = float(r["change_pct"] or 0.0)
            if k == "usd_brl" and r["fetched_at"]:
                target_cache["usd_brl_updated_at"] = r["fetched_at"]
            sources[k] = {
                "source": r["source"],
                "updated_at": r["fetched_at"],
                "data_state": "CACHED",
            }
        return sources

    def save_indicator(self, key: str, value: float, change_pct: float, source: str, fetched_at: str, conn=None):
        own_conn = conn is None
        if own_conn:
            conn = get_conn()
        try:
            conn.execute(
                """
                INSERT INTO macro_indicators_cache (key, value, change_pct, source, fetched_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET
                    value = excluded.value,
                    change_pct = excluded.change_pct,
                    source = excluded.source,
                    fetched_at = excluded.fetched_at
                """,
                (key, float(value), float(change_pct), source, fetched_at),
            )
            if own_conn:
                conn.commit()
        except sqlite3.OperationalError:
            migrate_market_cache_tables(conn)
        finally:
            if own_conn:
                conn.close()

    def refresh_macro(self, macro_cache: Dict[str, Any]) -> Dict[str, Any]:
        """Atualiza câmbio e indicadores do BCB preservando dados anteriores em caso de falha de rede."""
        sources = self.load_cached_into(macro_cache)
        now_str = _now_str()

        # 1. Câmbio primário: AwesomeAPI (USD-BRL, EUR-BRL, BTC-USD)
        usd_ok = False
        try:
            r = requests.get("https://economia.awesomeapi.com.br/last/USD-BRL,EUR-BRL,BTC-USD", timeout=4)
            if r.status_code == 200:
                data = r.json()
                if "USDBRL" in data:
                    val = round(float(data["USDBRL"]["bid"]), 4)
                    chg = round(float(data["USDBRL"].get("pctChange", 0.0)), 2)
                    macro_cache["usd_brl"] = val
                    macro_cache["usd_change"] = chg
                    macro_cache["usd_brl_updated_at"] = now_str
                    self.save_indicator("usd_brl", val, chg, "AwesomeAPI (USD/BRL comercial)", now_str)
                    sources["usd_brl"] = {"source": "AwesomeAPI (USD/BRL comercial)", "updated_at": now_str, "data_state": "LIVE"}
                    usd_ok = True
                if "EURBRL" in data:
                    val = round(float(data["EURBRL"]["bid"]), 4)
                    chg = round(float(data["EURBRL"].get("pctChange", 0.0)), 2)
                    macro_cache["eur_brl"] = val
                    macro_cache["eur_change"] = chg
                    self.save_indicator("eur_brl", val, chg, "AwesomeAPI (EUR/BRL)", now_str)
                    sources["eur_brl"] = {"source": "AwesomeAPI (EUR/BRL)", "updated_at": now_str, "data_state": "LIVE"}
                if "BTCUSD" in data:
                    val = round(float(data["BTCUSD"]["bid"]), 2)
                    chg = round(float(data["BTCUSD"].get("pctChange", 0.0)), 2)
                    macro_cache["btc_usd"] = val
                    macro_cache["btc_change"] = chg
                    self.save_indicator("btc_usd", val, chg, "AwesomeAPI (BTC/USD)", now_str)
                    sources["btc_usd"] = {"source": "AwesomeAPI (BTC/USD)", "updated_at": now_str, "data_state": "LIVE"}
        except Exception:
            pass

        # 1b. Contingência de câmbio: Banco Central do Brasil PTAX (SGS série 1) se AwesomeAPI falhar
        if not usd_ok:
            try:
                r_ptax = requests.get(
                    "https://api.bcb.gov.br/dados/serie/bcdata.sgs.1/dados/ultimos/1?formato=json",
                    timeout=4,
                    headers={"User-Agent": "SIM-App/2.0"},
                )
                if r_ptax.status_code == 200:
                    arr = r_ptax.json()
                    if arr and "valor" in arr[0]:
                        val = round(float(str(arr[0]["valor"]).replace(",", ".")), 4)
                        macro_cache["usd_brl"] = val
                        macro_cache["usd_brl_updated_at"] = now_str
                        self.save_indicator("usd_brl", val, 0.0, "Banco Central PTAX (SGS 1)", now_str)
                        sources["usd_brl"] = {"source": "Banco Central PTAX (SGS 1)", "updated_at": now_str, "data_state": "LIVE"}
            except Exception:
                pass

        # 2. Banco Central do Brasil: Selic Meta (432), CDI anualizado (4389) e IPCA 12m (13522)
        selic_ok = False
        try:
            r_selic = requests.get(
                "https://api.bcb.gov.br/dados/serie/bcdata.sgs.432/dados/ultimos/1?formato=json",
                timeout=4,
                headers={"User-Agent": "SIM-App/2.0"},
            )
            if r_selic.status_code == 200:
                arr = r_selic.json()
                if arr and "valor" in arr[0]:
                    val = round(float(str(arr[0]["valor"]).replace(",", ".")), 2)
                    macro_cache["selic"] = val
                    self.save_indicator("selic", val, 0.0, "Banco Central (SGS 432)", now_str)
                    sources["selic"] = {"source": "Banco Central (SGS 432)", "updated_at": now_str, "data_state": "LIVE"}
                    selic_ok = True
        except Exception:
            pass

        cdi_ok = False
        try:
            r_cdi = requests.get(
                "https://api.bcb.gov.br/dados/serie/bcdata.sgs.4389/dados/ultimos/1?formato=json",
                timeout=4,
                headers={"User-Agent": "SIM-App/2.0"},
            )
            if r_cdi.status_code == 200:
                arr = r_cdi.json()
                if arr and "valor" in arr[0]:
                    val = round(float(str(arr[0]["valor"]).replace(",", ".")), 2)
                    macro_cache["cdi"] = val
                    self.save_indicator("cdi", val, 0.0, "Banco Central (SGS 4389)", now_str)
                    sources["cdi"] = {"source": "Banco Central (SGS 4389)", "updated_at": now_str, "data_state": "LIVE"}
                    cdi_ok = True
        except Exception:
            pass

        if not cdi_ok and selic_ok:
            est_cdi = round(float(macro_cache["selic"]) - 0.10, 2)
            macro_cache["cdi"] = est_cdi
            self.save_indicator("cdi", est_cdi, 0.0, "Estimado (Selic - 0,10 p.p.)", now_str)
            sources["cdi"] = {"source": "Estimado (Selic - 0,10 p.p.)", "updated_at": now_str, "data_state": "LIVE"}

        try:
            r_ipca = requests.get(
                "https://api.bcb.gov.br/dados/serie/bcdata.sgs.13522/dados/ultimos/1?formato=json",
                timeout=4,
                headers={"User-Agent": "SIM-App/2.0"},
            )
            if r_ipca.status_code == 200:
                arr = r_ipca.json()
                if arr and "valor" in arr[0]:
                    val = round(float(str(arr[0]["valor"]).replace(",", ".")), 2)
                    macro_cache["ipca_12m"] = val
                    self.save_indicator("ipca_12m", val, 0.0, "Banco Central (SGS 13522 - IPCA 12m)", now_str)
                    sources["ipca_12m"] = {
                        "source": "Banco Central (SGS 13522 - IPCA 12m)",
                        "updated_at": now_str,
                        "data_state": "LIVE",
                    }
        except Exception:
            pass

        # Preenche metadado de fallback caso algum indicador nunca tenha sido sincronizado
        for k in ("usd_brl", "eur_brl", "selic", "cdi", "ipca_12m", "ibov", "sp500", "btc_usd"):
            if k not in sources:
                sources[k] = {
                    "source": "Valor padrão inicial (sem sincronização prévia)",
                    "updated_at": "",
                    "data_state": "DEFAULT",
                }

        macro_cache["sources"] = sources
        return macro_cache


class GoogleNewsRssAdapter:
    """
    Adaptador de notícias com título, fonte, data, link e resumo via Google News RSS,
    com cache persistente em `asset_news_cache` e proibição de manchetes sintéticas.
    """

    def fetch_news(
        self,
        ticker: str,
        name: str,
        asset_class: str,
        parse_dt_fn: Callable[[str, Any], Optional[datetime]],
        sentiment_fn: Callable[[str], str],
        ttl_seconds: int = 900,
        allow_network: bool = True,
    ) -> Dict[str, Any]:
        t_up = ticker.upper().strip()
        cls = (asset_class or "ACAO_BR").upper()
        feed_source = "Google News RSS (BR)" if cls in ("ACAO_BR", "FII", "ETF_BR") else "Google News RSS (US/Global)"

        conn = get_conn()
        try:
            cached_row = conn.execute(
                "SELECT items_json, source, fetched_at FROM asset_news_cache WHERE ticker = ?",
                (t_up,),
            ).fetchone()
        except sqlite3.OperationalError:
            migrate_market_cache_tables(conn)
            cached_row = None
        finally:
            conn.close()

        cached_items: List[Dict[str, Any]] = []
        cached_at = ""
        cached_source = feed_source
        if cached_row:
            try:
                cached_items = json.loads(cached_row["items_json"] or "[]")
                cached_at = cached_row["fetched_at"] or ""
                cached_source = cached_row["source"] or feed_source
            except Exception:
                cached_items = []

        if cached_row and _age_seconds(cached_at) <= ttl_seconds:
            return self._format_response(t_up, cached_items, cached_source, cached_at, "CACHED", "")

        if allow_network:
            if cls in ("ACAO_BR", "FII", "ETF_BR"):
                query = f'{t_up} OR "{name}" bolsa B3 when:90d'
            else:
                query = f'{t_up} "{name}" stock market when:90d'
            encoded_q = urllib.parse.quote(query)
            rss_url = f"https://news.google.com/rss/search?q={encoded_q}&hl=pt-BR&gl=BR&ceid=BR:pt-419"

            now_dt = datetime.now()
            cutoff_dt = now_dt - timedelta(days=90)
            parsed_entries: List[Dict[str, Any]] = []

            try:
                resp = requests.get(rss_url, timeout=5, headers={"User-Agent": "Mozilla/5.0 SIM-Finance/2.0"})
                if resp.status_code == 200:
                    feed = feedparser.parse(resp.content)
                    for entry in feed.entries:
                        raw_title = (entry.get("title") or "").strip()
                        if not raw_title:
                            continue
                        source = "Google News"
                        if " - " in raw_title:
                            parts = raw_title.rsplit(" - ", 1)
                            raw_title, source = parts[0].strip(), parts[1].strip()

                        dt = parse_dt_fn(entry.get("published", ""), entry.get("published_parsed"))
                        if dt is None or dt < cutoff_dt:
                            continue

                        raw_summary = _strip_html(entry.get("summary") or entry.get("description") or "")
                        if raw_summary.startswith(raw_title[:30]):
                            raw_summary = ""
                        if len(raw_summary) > 220:
                            raw_summary = raw_summary[:217].rstrip() + "..."

                        sentiment = sentiment_fn(raw_title)
                        parsed_entries.append({
                            "_dt": dt,
                            "title": raw_title,
                            "source": source,
                            "summary": raw_summary,
                            "published": dt.strftime("%d/%m/%Y %H:%M") if (dt.hour or dt.minute) else dt.strftime("%d/%m/%Y"),
                            "published_iso": dt.strftime("%Y-%m-%dT%H:%M:%S"),
                            "link": entry.get("link", "#"),
                            "sentiment": sentiment,
                            "sentiment_kind": "CALCULO_SIM_LEXICO",
                        })

                    parsed_entries.sort(key=lambda x: x["_dt"], reverse=True)
                    live_items = [{k: v for k, v in item.items() if k != "_dt"} for item in parsed_entries[:7]]
                    now_str = _now_str()

                    # Grava no cache quando obtém resposta HTTP 200 válida do feed
                    conn = get_conn()
                    conn.execute(
                        """
                        INSERT INTO asset_news_cache (ticker, items_json, source, fetched_at)
                        VALUES (?, ?, ?, ?)
                        ON CONFLICT(ticker) DO UPDATE SET
                            items_json = excluded.items_json,
                            source = excluded.source,
                            fetched_at = excluded.fetched_at
                        """,
                        (t_up, json.dumps(live_items), feed_source, now_str),
                    )
                    conn.commit()
                    conn.close()
                    return self._format_response(
                        t_up,
                        live_items,
                        feed_source,
                        now_str,
                        "LIVE" if live_items else "EMPTY",
                        "",
                    )
            except Exception:
                pass

        if cached_row:
            return self._format_response(
                t_up,
                cached_items,
                cached_source,
                cached_at,
                "CACHED",
                f"Provedor de notícias inacessível no momento; exibindo o último cache local ({cached_at}).",
            )

        return self._format_response(
            t_up,
            [],
            feed_source,
            "",
            "UNAVAILABLE",
            "Não foi possível consultar o provedor de notícias e não há notícias salvas em cache local.",
        )

    @staticmethod
    def _format_response(
        ticker: str,
        items: List[Dict[str, Any]],
        source: str,
        updated_at: str,
        data_state: str,
        warning: str,
    ) -> Dict[str, Any]:
        pos_count = sum(1 for n in items if n.get("sentiment") == "POSITIVO")
        neg_count = sum(1 for n in items if n.get("sentiment") == "NEGATIVO")
        if not items:
            overall = "SEM DADOS"
        elif pos_count > neg_count:
            overall = "OTIMISTA (BULLISH)"
        elif neg_count > pos_count:
            overall = "CAUTELOSO (BEARISH)"
        else:
            overall = "NEUTRO / EQUILIBRADO"

        return {
            "ticker": ticker,
            "source": source,
            "updated_at": updated_at,
            "data_state": data_state,
            "is_synthetic": False,
            "warning": warning,
            "overall_sentiment": overall,
            "sentiment_kind": "CALCULO_SIM_LEXICO",
            "positive_count": pos_count,
            "negative_count": neg_count,
            "neutral_count": len(items) - pos_count - neg_count,
            "items": items[:7],
        }
