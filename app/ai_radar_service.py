import os
import re
import json
from datetime import datetime
from typing import Dict, List, Any, Optional
import requests

from .database import get_conn
from .crypto_service import encrypt_secret, decrypt_secret
from .market_service import get_portfolio_summary, get_asset_specialized_profile
from .intelligence_service import (
    fetch_asset_news,
    fetch_official_reports,
    _build_valuation_and_viability_models,
)

DEFAULT_SETTINGS = {
    "ai_provider": "GEMINI",  # 'GEMINI' | 'OPENAI' | 'GROQ'
    "ai_model": "gemini-2.5-flash",
    "ai_api_key": "",
    "investor_profile": "RENDA_E_VALOR",  # 'RENDA_E_VALOR' | 'DIVIDENDOS' | 'CRESCIMENTO' | 'MODERADO'
    "min_dy_target": "8.0",
    "whatsapp_enabled": "0",
    "whatsapp_provider": "CALLMEBOT",  # 'CALLMEBOT' | 'EVOLUTION' | 'ZAPI' | 'WEBHOOK'
    "whatsapp_phone": "",
    "whatsapp_apikey": "",
    "whatsapp_instance_url": "",
    "whatsapp_instance_id": "",
    "whatsapp_daily_time": "18:30",
    "whatsapp_notify_opportunities": "1",
    "whatsapp_last_daily_sent": "",
}


def ensure_settings_tables():
    conn = get_conn()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS app_settings (
            user_id INTEGER NOT NULL DEFAULT 1,
            key TEXT NOT NULL,
            value TEXT NOT NULL,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (user_id, key)
        )
    """)

    # Migra ai_radar_cache se necessário
    cache_exists = conn.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='ai_radar_cache'").fetchone()
    if cache_exists and "user_id" not in cache_exists[0]:
        conn.execute("DROP TABLE ai_radar_cache")

    conn.execute("""
        CREATE TABLE IF NOT EXISTS ai_radar_cache (
            user_id INTEGER PRIMARY KEY,
            radar_json TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """)

    # Seed default settings for user_id=1 if empty
    for k, v in DEFAULT_SETTINGS.items():
        conn.execute(
            "INSERT OR IGNORE INTO app_settings (user_id, key, value) VALUES (1, ?, ?)",
            (k, str(v)),
        )

    # Migra chaves sensíveis existentes em texto puro para criptografia em repouso
    rows = conn.execute("SELECT user_id, key, value FROM app_settings WHERE key IN ('ai_api_key', 'whatsapp_apikey')").fetchall()
    for r in rows:
        val = str(r["value"] or "").strip()
        if val and not val.startswith("ENC:") and "••••" not in val:
            enc = encrypt_secret(val)
            conn.execute("UPDATE app_settings SET value = ? WHERE user_id = ? AND key = ?", (enc, r["user_id"], r["key"]))

    conn.commit()
    conn.close()


def get_raw_settings(user_id: int = 1) -> Dict[str, str]:
    ensure_settings_tables()
    conn = get_conn()
    rows = conn.execute("SELECT key, value FROM app_settings WHERE user_id = ?", (user_id,)).fetchall()
    conn.close()
    data = dict(DEFAULT_SETTINGS)
    for r in rows:
        data[r["key"]] = r["value"]

    # Descriptografa segredos em repouso
    for sec_key in ("ai_api_key", "whatsapp_apikey"):
        if data.get(sec_key):
            data[sec_key] = decrypt_secret(data[sec_key])

    # Fallback to environment variable if ai_api_key not set in DB
    if not data.get("ai_api_key") and os.environ.get("GEMINI_API_KEY"):
        data["ai_api_key"] = os.environ.get("GEMINI_API_KEY", "").strip()
    return data


def _mask_secret(secret: str) -> str:
    s = (secret or "").strip()
    if not s:
        return ""
    if len(s) <= 8:
        return "••••••••"
    return f"{s[:4]}••••••••{s[-4:]}"


def get_public_settings(user_id: int = 1) -> Dict[str, Any]:
    raw = get_raw_settings(user_id=user_id)
    api_key = raw.get("ai_api_key", "").strip()
    wa_key = raw.get("whatsapp_apikey", "").strip()
    sched_status = {}
    try:
        from .whatsapp_service import get_whatsapp_scheduler_status
        sched_status = get_whatsapp_scheduler_status(user_id=user_id)
    except Exception:
        pass
    return {
        "ai_provider": raw.get("ai_provider", "GEMINI"),
        "ai_model": raw.get("ai_model", "gemini-2.5-flash"),
        "ai_api_key_configured": bool(api_key),
        "ai_api_key_masked": _mask_secret(api_key),
        "investor_profile": raw.get("investor_profile", "RENDA_E_VALOR"),
        "min_dy_target": float(raw.get("min_dy_target") or 8.0),
        "whatsapp_enabled": raw.get("whatsapp_enabled") == "1",
        "whatsapp_provider": raw.get("whatsapp_provider", "CALLMEBOT"),
        "whatsapp_phone": raw.get("whatsapp_phone", ""),
        "whatsapp_apikey_configured": bool(wa_key),
        "whatsapp_apikey_masked": _mask_secret(wa_key),
        "whatsapp_instance_url": raw.get("whatsapp_instance_url", ""),
        "whatsapp_instance_id": raw.get("whatsapp_instance_id", ""),
        "whatsapp_daily_time": raw.get("whatsapp_daily_time", "18:30"),
        "whatsapp_notify_opportunities": raw.get("whatsapp_notify_opportunities") == "1",
        "whatsapp_last_daily_sent": raw.get("whatsapp_last_daily_sent", ""),
        "whatsapp_scheduler_status": sched_status,
    }


def update_app_settings(updates: Dict[str, Any], user_id: int = 1) -> Dict[str, Any]:
    ensure_settings_tables()
    conn = get_conn()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    for k, v in updates.items():
        if k not in DEFAULT_SETTINGS:
            continue
        if v is None:
            continue
        str_val = str(v).strip()
        # Do not overwrite secret keys if user sent masked placeholder or empty string when keeping existing
        if k in ("ai_api_key", "whatsapp_apikey") and ("••••" in str_val or str_val == "__KEEP__"):
            continue
        if isinstance(v, bool):
            str_val = "1" if v else "0"

        # Criptografa chaves sensíveis antes de salvar no banco
        if k in ("ai_api_key", "whatsapp_apikey") and str_val:
            str_val = encrypt_secret(str_val)

        conn.execute(
            """
            INSERT INTO app_settings (user_id, key, value, updated_at) VALUES (?, ?, ?, ?)
            ON CONFLICT(user_id, key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at
            """,
            (user_id, k, str_val, now_str),
        )

    conn.commit()
    conn.close()
    return get_public_settings(user_id=user_id)


def _clean_json_markdown(text: str) -> str:
    """Strips markdown code fences (```json ... ```) or extracts JSON object from LLM responses."""
    if not text:
        return "{}"
    t = text.strip()
    # 1. Search for markdown code fences (```json ... ``` or ``` ... ```)
    m = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", t, flags=re.IGNORECASE)
    if m:
        t = m.group(1).strip()
    # 2. Extract outermost JSON object if surrounded by conversational filler
    if not (t.startswith("{") and t.endswith("}")):
        start = t.find("{")
        end = t.rfind("}")
        if start != -1 and end != -1 and end > start:
            t = t[start:end + 1].strip()
    return t.strip()


def call_configured_llm(
    prompt: str,
    system_prompt: str = "Você é um analista CNPI sênior certificado pela B3 e CVM.",
    json_mode: bool = False,
    timeout: int = 18,
    user_id: int = 1,
) -> Optional[str]:
    """
    Calls the user-configured LLM provider (Google Gemini, OpenAI, or Groq) using the saved API key.
    Returns the raw text/JSON string from the model, or None if not configured or on error.
    """
    settings = get_raw_settings(user_id=user_id)
    provider = (settings.get("ai_provider") or "GEMINI").upper().strip()
    model = (settings.get("ai_model") or "gemini-2.5-flash").strip()
    api_key = (settings.get("ai_api_key") or "").strip()

    if not api_key:
        return None

    if provider == "GEMINI":
        if not model or not model.startswith("gemini"):
            model = "gemini-2.5-flash"
        # Passa a chave via cabeçalho x-goog-api-key para evitar expô-la em query string/logs
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        headers = {
            "x-goog-api-key": api_key,
            "Content-Type": "application/json",
        }
        gen_cfg: Dict[str, Any] = {"temperature": 0.25}
        if json_mode:
            gen_cfg["responseMimeType"] = "application/json"
        payload = {
            "systemInstruction": {"parts": [{"text": system_prompt}]},
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": gen_cfg,
        }
        r = requests.post(url, headers=headers, json=payload, timeout=timeout)
        if r.status_code == 400 and ("API_KEY_INVALID" in r.text or "key" in r.text.lower()):
            raise ValueError("Chave de API Gemini inválida ou não autorizada (Erro 400).")
        elif r.status_code == 429:
            raise ValueError("Limite de cota do Google Gemini excedido (Erro 429: Resource Exhausted / Rate limit).")
        elif r.status_code != 200:
            raise ValueError(f"Erro Gemini ({r.status_code}): {r.text[:220]}")
        data = r.json()
        try:
            return data["candidates"][0]["content"]["parts"][0]["text"]
        except (KeyError, IndexError):
            raise ValueError("Resposta inesperada do Gemini (nenhum candidato retornado).")

    elif provider in ("OPENAI", "GROQ"):
        if provider == "OPENAI":
            url = "https://api.openai.com/v1/chat/completions"
            if not model or model.startswith("gemini"):
                model = "gpt-4o-mini"
        else:
            url = "https://api.groq.com/openai/v1/chat/completions"
            if not model or model.startswith("gemini") or model.startswith("gpt"):
                model = "llama-3.3-70b-versatile"

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.25,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}

        r = requests.post(url, headers=headers, json=payload, timeout=timeout)
        if r.status_code in (401, 403):
            raise ValueError(f"Chave da API {provider} inválida ou não autorizada (Erro {r.status_code}).")
        elif r.status_code == 429:
            raise ValueError(f"Limite de cota ou taxa do {provider} excedido (Erro 429: Quota / Rate limit).")
        elif r.status_code != 200:
            raise ValueError(f"Erro {provider} ({r.status_code}): {r.text[:220]}")
        data = r.json()
        try:
            return data["choices"][0]["message"]["content"]
        except (KeyError, IndexError):
            raise ValueError(f"Resposta inesperada do {provider} (mensagem vazia).")

    return None


def test_ai_connection(override_provider: str = "", override_model: str = "", override_key: str = "", user_id: int = 1) -> Dict[str, Any]:
    """
    Tests the AI API connection with a quick prompt and returns status, latency, and sample response.
    """
    raw = get_raw_settings(user_id=user_id)
    provider = (override_provider or raw.get("ai_provider") or "GEMINI").upper().strip()
    model = (override_model or raw.get("ai_model") or "gemini-2.5-flash").strip()
    api_key = override_key.strip() if (override_key and "••••" not in override_key) else raw.get("ai_api_key", "").strip()

    if not api_key:
        raise ValueError("Nenhuma API Key de IA foi informada. Cole sua chave do Google AI Studio (Gemini), OpenAI ou Groq.")

    # Temporarily save if overrides were provided
    t0 = datetime.now()
    if provider == "GEMINI":
        if not model.startswith("gemini"):
            model = "gemini-2.5-flash"
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        headers = {"x-goog-api-key": api_key, "Content-Type": "application/json"}
        r = requests.post(
            url,
            headers=headers,
            json={"contents": [{"parts": [{"text": "Responda em 1 frase curta: Conexão com o analista IA do SIM estabelecida com sucesso!"}]}]},
            timeout=12,
        )
        if r.status_code != 200:
            raise ValueError(f"Falha na chave Gemini ({r.status_code}): verifique se a API Key é válida.")
        reply = r.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
    else:
        url = "https://api.openai.com/v1/chat/completions" if provider == "OPENAI" else "https://api.groq.com/openai/v1/chat/completions"
        if provider == "OPENAI" and not model.startswith("gpt"):
            model = "gpt-4o-mini"
        elif provider == "GROQ" and (model.startswith("gemini") or model.startswith("gpt")):
            model = "llama-3.3-70b-versatile"
        r = requests.post(
            url,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": model,
                "messages": [{"role": "user", "content": "Responda em 1 frase curta: Conexão com o analista IA do SIM estabelecida com sucesso!"}],
                "max_tokens": 60,
            },
            timeout=12,
        )
        if r.status_code != 200:
            raise ValueError(f"Falha na chave {provider} ({r.status_code}): verifique se a API Key é válida.")
        reply = r.json()["choices"][0]["message"]["content"].strip()

    latency_ms = int((datetime.now() - t0).total_seconds() * 1000)
    return {
        "status": "ok",
        "provider": provider,
        "model": model,
        "latency_ms": latency_ms,
        "reply": reply,
    }


def _score_market_opportunity(
    asset: Dict[str, Any],
    held_tickers: set,
    deficit_classes: Dict[str, float],
    min_dy_target: float,
    investor_profile: str,
) -> Optional[Dict[str, Any]]:
    """
    Scores an asset from assets_catalog from 0 to 100 based on:
      - Valuation discount (P/VP, P/L, Graham Intrinsic Value, Bazin Ceiling Price)
      - Dividend Yield vs user's target
      - Portfolio allocation deficit bonus
    """
    ticker = asset["ticker"]
    cls = asset["asset_class"]
    price = float(asset.get("last_price") or 0.0)
    if price <= 0:
        return None

    dy = float(asset.get("dy_12m") or 0.0)
    pl = float(asset.get("pl") or 0.0)
    pvp = float(asset.get("pvp") or 1.0)
    chg = float(asset.get("change_pct") or 0.0)
    prof = get_asset_specialized_profile(asset)
    val_models = _build_valuation_and_viability_models(asset, prof)

    bazin = val_models.get("bazin", {})
    graham = val_models.get("graham", {})
    bazin_margin = float(bazin.get("margin_pct") or 0.0) if bazin.get("applicable") else 0.0
    graham_margin = float(graham.get("margin_pct") or 0.0) if graham.get("applicable") else 0.0

    score = 50.0
    reasons: List[str] = []
    opportunity_tag = "QUALIDADE & FUNDAMENTOS"

    if cls == "FII":
        # FII scoring: P/VP discount + DY 12M
        if 0.70 <= pvp <= 0.96:
            discount_pct = round((1.0 - pvp) * 100.0, 1)
            score += min(25.0, discount_pct * 2.2)
            reasons.append(f"Negociando com {discount_pct}% de desconto patrimonial (P/VP {pvp:.2f}x)")
            opportunity_tag = "FII DESCONTADO + RENDA"
        elif pvp <= 1.01:
            score += 10.0
            reasons.append(f"P/VP alinhado ao valor justo ({pvp:.2f}x)")
        else:
            score -= 12.0

        if dy >= max(9.5, min_dy_target):
            score += min(20.0, (dy - 8.0) * 3.5)
            reasons.append(f"Dividend Yield elevado de {dy:.1f}% a.a. isento de IR")
        if bazin_margin > 5.0:
            score += 6.0
            reasons.append(f"Margem de +{bazin_margin:.1f}% abaixo do Preço Teto Bazin (R$ {bazin.get('ceiling_price', 0):.2f})")

    elif cls == "ACAO_BR":
        # B3 Stock scoring: Graham + Bazin + P/L + ROE
        if graham_margin > 10.0:
            score += min(22.0, graham_margin * 0.45)
            reasons.append(f"Margem de segurança de Graham de +{graham_margin:.1f}% (Valor Intrínseco R$ {graham.get('intrinsic_value', 0):.2f})")
            opportunity_tag = "DESCONTO GRAHAM & BAZIN"
        if bazin_margin > 5.0:
            score += min(16.0, bazin_margin * 0.4)
            reasons.append(f"Abaixo do Preço Teto de Bazin (R$ {bazin.get('ceiling_price', 0):.2f}) com DY de {dy:.1f}%")
            if opportunity_tag == "QUALIDADE & FUNDAMENTOS":
                opportunity_tag = "VACAS LEITEIRAS (BAZIN)"
        if 0 < pl <= 10.5:
            score += 12.0
            reasons.append(f"Múltiplo P/L descontado em {pl:.1f}x lucros")
        if 0 < pvp <= 1.25:
            score += 8.0
            reasons.append(f"P/VP atrativo em {pvp:.2f}x")

    elif cls in ("ETF_BR", "STOCK_US", "CRIPTO"):
        ret12 = float(prof.get("return_12m_pct") or prof.get("roe") or 12.0)
        if ret12 >= 15.0:
            score += 15.0
            reasons.append(f"Forte geração de valor e eficiência operacional ({ret12:.1f}%)")
        if chg < -1.0:
            score += 8.0
            reasons.append(f"Correção recente de {chg:.2f}% abrindo janela de entrada")

    # Investor profile weighting
    if investor_profile == "DIVIDENDOS" and dy >= 9.0:
        score += 7.0
    elif investor_profile == "CRESCIMENTO" and cls in ("ACAO_BR", "STOCK_US", "ETF_BR"):
        score += 5.0

    # Allocation deficit bonus: if user needs more of this asset class
    class_deficit_brl = deficit_classes.get(cls, 0.0)
    if class_deficit_brl > 100.0:
        score += 8.0
        reasons.append(f"Sua carteira está abaixo da meta ideal em {cls} (déficit de R$ {class_deficit_brl:,.0f})")

    score = max(10, min(99, round(score)))
    if score < 64 or not reasons:
        return None

    return {
        "ticker": ticker,
        "name": asset["name"],
        "asset_class": cls,
        "sector": asset.get("sector", ""),
        "currency": asset.get("currency", "BRL"),
        "last_price": price,
        "change_pct": chg,
        "dy_12m": dy,
        "pl": pl,
        "pvp": pvp,
        "in_portfolio": ticker in held_tickers,
        "score": int(score),
        "opportunity_tag": opportunity_tag,
        "bazin_ceiling": bazin.get("ceiling_price", 0.0),
        "bazin_margin_pct": round(bazin_margin, 1),
        "graham_intrinsic": graham.get("intrinsic_value", 0.0),
        "graham_margin_pct": round(graham_margin, 1),
        "reasons": reasons[:3],
    }


def generate_portfolio_and_market_radar(force_refresh: bool = False, user_id: int = 1) -> Dict[str, Any]:
    """
    Builds the complete Portfolio Intelligence & Market Opportunity Radar:
      1. Daily Portfolio Evolution Summary (Patrimônio, Variação do Dia, Destaques de Alta/Baixa, Renda Passiva)
      2. Portfolio Alerts (Notícias relevantes, Fatos Relevantes/Relatórios Gerenciais B3/CVM e alertas de Preço Médio)
      3. Top Market Opportunities (filtradas por Valuation Bazin/Graham/P-VP, Notícias e Relatórios Gerenciais)
      4. AI Analyst Executive Briefing (gerado pelo Gemini/OpenAI/Groq quando configurado, ou motor analítico CNPI nativo)
    """
    ensure_settings_tables()
    conn = get_conn()

    if not force_refresh:
        cached = conn.execute("SELECT radar_json, updated_at FROM ai_radar_cache WHERE user_id = ?", (user_id,)).fetchone()
        if cached:
            try:
                dt_up = datetime.strptime(cached["updated_at"], "%Y-%m-%d %H:%M:%S")
                if (datetime.now() - dt_up).total_seconds() < 600:
                    cached_data = json.loads(cached["radar_json"])
                    if not cached_data.get("ai_error"):
                        conn.close()
                        return cached_data
            except Exception:
                pass

    settings = get_raw_settings(user_id=user_id)
    investor_profile = settings.get("investor_profile", "RENDA_E_VALOR")
    min_dy_target = float(settings.get("min_dy_target") or 8.0)

    portfolio = get_portfolio_summary(user_id=user_id)
    kpis = portfolio.get("kpis", {})
    positions = portfolio.get("positions", [])
    allocations = portfolio.get("allocation", [])

    held_tickers = {p["ticker"].upper() for p in positions}

    # Map allocation deficits by class
    total_patrimony = float(kpis.get("total_current_brl") or 0.0)
    deficit_classes: Dict[str, float] = {}
    for al in allocations:
        ideal_brl = total_patrimony * (float(al.get("target_pct") or 0.0) / 100.0)
        deficit_classes[al["asset_class"]] = max(0.0, ideal_brl - float(al.get("current_brl") or 0.0))

    # 1. Build Portfolio Alerts for held positions (checking price vs PM, day change, news & official reports)
    portfolio_alerts: List[Dict[str, Any]] = []
    sorted_positions = sorted(positions, key=lambda x: x.get("current_total_brl", 0), reverse=True)

    for idx, pos in enumerate(sorted_positions):
        t = pos["ticker"]
        chg_day = float(pos.get("change_pct") or 0.0)
        profit_pct = float(pos.get("profit_pct") or 0.0)
        cur_price = float(pos.get("current_price") or 0.0)
        avg_price = float(pos.get("avg_price") or 0.0)
        dy = float(pos.get("dy_12m") or 0.0)
        pvp = float(pos.get("pvp") or 1.0)

        # Fetch news and official reports for top 4 positions to enrich alerts without slowing down
        latest_news_title = ""
        latest_doc_title = ""
        latest_doc_date = ""
        if idx < 4:
            try:
                news_list = fetch_asset_news(t)
                if news_list and isinstance(news_list, list):
                    latest_news_title = news_list[0].get("title", "")
                elif isinstance(news_list, dict) and news_list.get("items"):
                    latest_news_title = news_list["items"][0].get("title", "")
            except Exception:
                pass
            try:
                rep_data = fetch_official_reports(t)
                reps = rep_data.get("reports", []) if isinstance(rep_data, dict) else []
                if reps:
                    latest_doc_title = reps[0].get("title", "")
                    latest_doc_date = reps[0].get("date", "")
            except Exception:
                pass

        if cur_price < avg_price * 0.97 and dy >= 8.0:
            portfolio_alerts.append({
                "ticker": t,
                "name": pos["name"],
                "severity": "OPORTUNIDADE_CARTEIRA",
                "badge": "REDUZIR PREÇO MÉDIO",
                "title": f"{t} está {abs(profit_pct):.1f}% abaixo do seu Preço Médio (R$ {avg_price:.2f}) mantendo DY de {dy:.1f}%",
                "detail": (
                    f"Cotação atual em R$ {cur_price:.2f} (P/VP {pvp:.2f}x). "
                    + (f"Último documento oficial: {latest_doc_title} ({latest_doc_date})." if latest_doc_title else "Fundamentos permitem aporte para redução de PM.")
                ),
            })
        elif abs(chg_day) >= 1.5:
            portfolio_alerts.append({
                "ticker": t,
                "name": pos["name"],
                "severity": "MOVIMENTO_DIA" if chg_day > 0 else "ATENCAO_DIA",
                "badge": f"{chg_day:+.2f}% HOJE",
                "title": f"{t} registra oscilação relevante de {chg_day:+.2f}% no pregão de hoje",
                "detail": (
                    f"Notícia recente no radar: \"{latest_news_title}\""
                    if latest_news_title else
                    f"Posição atual de R$ {pos.get('current_total_brl', 0):,.2f} ({profit_pct:+.1f}% sobre o seu PM)."
                ),
            })
        elif latest_doc_title:
            portfolio_alerts.append({
                "ticker": t,
                "name": pos["name"],
                "severity": "RELATORIO_OFICIAL",
                "badge": f"RELATÓRIO {latest_doc_date}",
                "title": f"{t}: {latest_doc_title}",
                "detail": (
                    f"Comunicado/Relatório oficial monitorado na CVM/B3 Fundos.NET. "
                    + (f"Radar de mídia: \"{latest_news_title}\"" if latest_news_title else f"DY atual de {dy:.1f}% a.a.")
                ),
            })

    # 2. Scan all catalog assets for Top Market Opportunities
    all_rows = conn.execute("SELECT * FROM assets_catalog").fetchall()
    conn.close()

    scored_candidates: List[Dict[str, Any]] = []
    for r in all_rows:
        cand = _score_market_opportunity(dict(r), held_tickers, deficit_classes, min_dy_target, investor_profile)
        if cand:
            scored_candidates.append(cand)

    scored_candidates.sort(key=lambda x: (x["score"], x["dy_12m"]), reverse=True)
    top_opportunities = scored_candidates[:6]

    # Enrich top 4 opportunities with real latest headline + official report metadata
    for opp in top_opportunities[:4]:
        t = opp["ticker"]
        try:
            n_data = fetch_asset_news(t)
            items = n_data if isinstance(n_data, list) else n_data.get("items", [])
            if items:
                opp["latest_news"] = items[0].get("title", "")
                opp["news_sentiment"] = items[0].get("sentiment", "NEUTRO")
        except Exception:
            opp["latest_news"] = ""
            opp["news_sentiment"] = "NEUTRO"
        try:
            r_data = fetch_official_reports(t)
            reps = r_data.get("reports", []) if isinstance(r_data, dict) else []
            if reps:
                opp["latest_report"] = f"{reps[0].get('title', 'Relatório Oficial')} ({reps[0].get('date', '')})"
        except Exception:
            opp["latest_report"] = ""

    # 3. Generate Executive AI Analyst Briefing (via LLM if API key is configured, or Quantitative CNPI Engine)
    ai_generated = False
    ai_provider_used = "Motor Analítico Quantitativo CNPI (Nativo)"
    ai_error = ""
    executive_briefing = ""
    action_recommendations: List[str] = []

    top_gainer = max(positions, key=lambda x: x.get("change_pct", 0.0)) if positions else None
    top_loser = min(positions, key=lambda x: x.get("change_pct", 0.0)) if positions else None

    if settings.get("ai_api_key"):
        try:
            port_summary_txt = (
                f"Patrimônio Total: R$ {kpis.get('total_current_brl', 0):,.2f} | "
                f"Variação Hoje: {kpis.get('day_change_pct', 0):+.2f}% (R$ {kpis.get('day_change_brl', 0):+,.2f}) | "
                f"Lucro Acumulado: R$ {kpis.get('total_profit_brl', 0):+,.2f} ({kpis.get('total_profit_pct', 0):+.2f}%) | "
                f"Renda Passiva Mensal Estimada: R$ {kpis.get('estimated_monthly_divs_brl', 0):,.2f}/mês.\n"
                f"Ativos na carteira ({len(positions)}): "
                + ", ".join(
                    f"{p['ticker']} (Qtd {p['quantity']}, PM R$ {p['avg_price']:.2f}, Atual R$ {p['current_price']:.2f}, Dia {p['change_pct']:+.2f}%, DY {p['dy_12m']:.1f}%)"
                    for p in sorted_positions[:10]
                )
            )
            opps_txt = "\n".join(
                f"- {o['ticker']} ({o['name']}): Score {o['score']}/100, Preço R$ {o['last_price']:.2f}, P/VP {o['pvp']:.2f}x, P/L {o['pl']:.1f}x, DY {o['dy_12m']:.1f}%, Motivos: {'; '.join(o['reasons'])} | Notícia: {o.get('latest_news', 'N/A')} | Relatório: {o.get('latest_report', 'N/A')}"
                for o in top_opportunities[:5]
            )
            prompt = (
                f"Analise a carteira do investidor (Perfil: {investor_profile}) e as oportunidades de mercado na B3 hoje:\n\n"
                f"DADOS DA CARTEIRA:\n{port_summary_txt}\n\n"
                f"TOP OPORTUNIDADES DETECTADAS (VALUATION + RELATÓRIOS + NOTÍCIAS):\n{opps_txt}\n\n"
                f"Retorne estritamente um objeto JSON com as chaves:\n"
                f"- \"executive_briefing\": string (parágrafo denso, direto e profissional de 3 a 4 frases comentando o desempenho da carteira hoje e as melhores assimetrias encontradas)\n"
                f"- \"action_recommendations\": lista de 3 strings curtas e acionáveis recomendando movimentos táticos (aportes, rebalanceamento ou acompanhamento de relatórios)."
            )
            llm_resp = call_configured_llm(prompt, json_mode=True, user_id=user_id)
            if llm_resp:
                cleaned = _clean_json_markdown(llm_resp)
                try:
                    parsed_llm = json.loads(cleaned)
                except Exception as parse_err:
                    raise ValueError(f"Resposta da IA não pôde ser convertida em JSON ({parse_err}). Resposta: {cleaned[:140]}")
                executive_briefing = parsed_llm.get("executive_briefing", "")
                action_recommendations = parsed_llm.get("action_recommendations", [])
                if executive_briefing:
                    ai_generated = True
                    ai_provider_used = f"{settings.get('ai_provider')} · {settings.get('ai_model')}"
                else:
                    raise ValueError("O modelo de IA não retornou o campo 'executive_briefing' no formato esperado.")
            else:
                ai_error = "A API do provedor de IA retornou uma resposta em branco."
        except Exception as exc:
            ai_error = str(exc)

    if ai_error:
        ai_provider_used = f"Motor Quantitativo CNPI (Contingência — {settings.get('ai_provider', 'IA')} offline)"

    if not executive_briefing:
        day_brl = float(kpis.get("day_change_brl") or 0.0)
        day_pct = float(kpis.get("day_change_pct") or 0.0)
        monthly_div = float(kpis.get("estimated_monthly_divs_brl") or 0.0)
        best_opp = top_opportunities[0] if top_opportunities else None

        if positions:
            executive_briefing = (
                f"Sua carteira consolida R$ {total_patrimony:,.2f} com variação diária de {day_pct:+.2f}% "
                f"(R$ {day_brl:+,.2f} hoje) e geração de renda passiva projetada em R$ {monthly_div:,.2f}/mês. "
                + (
                    f"No pregão, o principal destaque positivo da carteira é {top_gainer['ticker']} ({top_gainer['change_pct']:+.2f}%), "
                    f"enquanto {top_loser['ticker']} ({top_loser['change_pct']:+.2f}%) apresenta a maior retração. "
                    if top_gainer and top_loser and top_gainer["ticker"] != top_loser["ticker"]
                    else ""
                )
                + (
                    f"Cruzando múltiplos de Bazin/Graham, relatórios gerenciais da B3 e notícias, a maior assimetria atual é "
                    f"{best_opp['ticker']} (Score {best_opp['score']}/100 — {best_opp['reasons'][0]})."
                    if best_opp else ""
                )
            )
        else:
            executive_briefing = (
                "Sua carteira ainda não possui ativos sincronizados, mas o Radar de Inteligência já escaneou os relatórios da CVM/B3 e múltiplos do mercado. "
                + (
                    f"O destaque número #1 de oportunidade hoje é {best_opp['ticker']} ({best_opp['name']}) com Score {best_opp['score']}/100: {best_opp['reasons'][0]}."
                    if best_opp else ""
                )
            )

        action_recommendations = []
        if top_opportunities:
            o1 = top_opportunities[0]
            action_recommendations.append(
                f"Avaliar aporte em {o1['ticker']} (R$ {o1['last_price']:.2f}): {o1['reasons'][0]}."
            )
        if len(top_opportunities) > 1:
            o2 = top_opportunities[1]
            action_recommendations.append(
                f"Monitorar {o2['ticker']} ({o2['opportunity_tag']}): DY de {o2['dy_12m']:.1f}% a.a. e P/VP de {o2['pvp']:.2f}x."
            )
        if portfolio_alerts:
            a1 = portfolio_alerts[0]
            action_recommendations.append(f"Carteira ({a1['ticker']}): {a1['title']}.")
        else:
            action_recommendations.append(
                "Sincronize sua planilha da B3 (.xlsx) mensalmente para manter o cálculo de rebalanceamento e proventos exato."
            )

    result = {
        "generated_at": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
        "ai_generated": ai_generated,
        "ai_provider_used": ai_provider_used,
        "investor_profile": investor_profile,
        "daily_evolution": {
            "total_patrimony_brl": round(total_patrimony, 2),
            "day_change_brl": round(float(kpis.get("day_change_brl") or 0.0), 2),
            "day_change_pct": round(float(kpis.get("day_change_pct") or 0.0), 2),
            "total_profit_brl": round(float(kpis.get("total_profit_brl") or 0.0), 2),
            "total_profit_pct": round(float(kpis.get("total_profit_pct") or 0.0), 2),
            "estimated_monthly_divs_brl": round(float(kpis.get("estimated_monthly_divs_brl") or 0.0), 2),
            "positions_count": len(positions),
            "top_gainer": {
                "ticker": top_gainer["ticker"],
                "change_pct": top_gainer["change_pct"],
                "current_price": top_gainer["current_price"],
            } if top_gainer else None,
            "top_loser": {
                "ticker": top_loser["ticker"],
                "change_pct": top_loser["change_pct"],
                "current_price": top_loser["current_price"],
            } if top_loser else None,
        },
        "executive_briefing": executive_briefing,
        "action_recommendations": action_recommendations,
        "ai_error": ai_error,
        "portfolio_alerts": portfolio_alerts[:6],
        "opportunities": top_opportunities,
    }

    # Só grava no cache se a geração não tiver sofrido erro de IA, permitindo retry imediato após ajuste de chave
    if not ai_error:
        try:
            conn2 = get_conn()
            conn2.execute(
                "INSERT OR REPLACE INTO ai_radar_cache (user_id, radar_json, updated_at) VALUES (?, ?, ?)",
                (user_id, json.dumps(result, ensure_ascii=False), datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
            )
            conn2.commit()
            conn2.close()
        except Exception:
            pass

    return result
