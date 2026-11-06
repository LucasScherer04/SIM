import os
import re
import json
from datetime import datetime
from typing import Dict, List, Any, Optional
import requests

from .database import get_conn, migrate_ai_stage4_tables
from .crypto_service import encrypt_secret, decrypt_secret
from .market_service import (
    get_portfolio_summary,
    get_asset_specialized_profile,
    get_asset_chart_and_dividends,
    fetch_macro_indicators,
    is_quote_stale,
)
from .dashboard_service import get_dashboard
from .intelligence_service import (
    fetch_asset_news,
    fetch_official_reports,
    _build_valuation_and_viability_models,
)

PROMPT_VERSION = "etapa4-v1.0"
STANDARD_LIMITATIONS = [
    "As análises têm finalidade estritamente informativa e de organização pessoal; não constituem recomendação regulada nem executam ordens de compra ou venda.",
    "Nenhuma hipótese do radar ou interpretação da IA garante rentabilidade futura ou valorização.",
    "Comparações com médias históricas não determinam sozinhas se um ativo está barato ou caro; avalie sempre fundamentos, proventos, eventos corporativos, juros, inflação e câmbio.",
]

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
    migrate_ai_stage4_tables(conn)
    conn.close()


def _sanitize_error_message(msg: str, api_key: str = "") -> str:
    """Remove qualquer ocorrência acidental de chaves de API de mensagens de erro ou logs."""
    s = str(msg or "")
    if api_key and len(api_key.strip()) >= 6:
        s = s.replace(api_key.strip(), "[CHAVE_OCULTADA]")
    s = re.sub(r"(sk-[A-Za-z0-9_\-]{10,}|AIza[A-Za-z0-9_\-]{10,}|gsk_[A-Za-z0-9_\-]{10,})", "[CHAVE_OCULTADA]", s)
    return s


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

    # Fallback para variáveis de ambiente caso ai_api_key não esteja salva no banco
    if not data.get("ai_api_key"):
        prov = (data.get("ai_provider") or "GEMINI").upper().strip()
        env_map = {
            "GEMINI": "GEMINI_API_KEY",
            "OPENAI": "OPENAI_API_KEY",
            "GROQ": "GROQ_API_KEY",
        }
        env_val = os.environ.get(env_map.get(prov, "GEMINI_API_KEY")) or os.environ.get("GEMINI_API_KEY")
        if env_val:
            data["ai_api_key"] = env_val.strip()
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
            raise ValueError(_sanitize_error_message(f"Erro Gemini ({r.status_code}): {r.text[:220]}", api_key))
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
            raise ValueError(_sanitize_error_message(f"Erro {provider} ({r.status_code}): {r.text[:220]}", api_key))
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
                        return _apply_live_item_states_to_radar(cached_data, user_id=user_id)
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

    # 2. Scan all catalog assets for Top Market Opportunities and Watchlist Signals
    fav_rows = conn.execute("SELECT ticker FROM favorites WHERE user_id = ? ORDER BY ticker ASC", (user_id,)).fetchall()
    all_rows = conn.execute("SELECT * FROM assets_catalog").fetchall()
    conn.close()

    fav_tickers = {r["ticker"].upper() for r in fav_rows}
    catalog_by_ticker = {r["ticker"].upper(): dict(r) for r in all_rows}
    item_states_map = get_radar_item_states(user_id=user_id)

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
                opp["latest_news_link"] = items[0].get("link", "")
                opp["latest_news_date"] = items[0].get("published", "")
                opp["news_sentiment"] = items[0].get("sentiment", "NEUTRO")
        except Exception:
            opp["latest_news"] = ""
            opp["news_sentiment"] = "NEUTRO"
        try:
            r_data = fetch_official_reports(t)
            reps = r_data.get("reports", []) if isinstance(r_data, dict) else []
            if reps:
                opp["latest_report"] = f"{reps[0].get('title', 'Relatório Oficial')} ({reps[0].get('date', '')})"
                opp["latest_report_url"] = reps[0].get("url", "")
        except Exception:
            opp["latest_report"] = ""

    # Attach item_key, user_status and counter-arguments/risks to opportunities and alerts
    for a in portfolio_alerts:
        ikey = f"ALERT:{a['ticker']}"
        a["item_key"] = ikey
        a["user_status"] = item_states_map.get(ikey, {}).get("status", "NOVO")
        a["user_notes"] = item_states_map.get(ikey, {}).get("notes", "")

    for opp in top_opportunities:
        ikey = f"OPP:{opp['ticker']}"
        opp["item_key"] = ikey
        opp["in_watchlist"] = opp["ticker"].upper() in fav_tickers
        opp["user_status"] = item_states_map.get(ikey, {}).get("status", "NOVO")
        opp["user_notes"] = item_states_map.get(ikey, {}).get("notes", "")
        opp["disclaimer"] = "Hipótese para investigação analítica, não constitui recomendação nem garantia de retorno."

    # Build Watchlist Signals (ativos em acompanhamento nos favoritos)
    watchlist_signals: List[Dict[str, Any]] = []
    for ft in sorted(fav_tickers):
        cat = catalog_by_ticker.get(ft)
        if not cat:
            continue
        price = float(cat.get("last_price") or 0.0)
        chg = float(cat.get("change_pct") or 0.0)
        dy = float(cat.get("dy_12m") or 0.0)
        pvp = float(cat.get("pvp") or 1.0)
        pl = float(cat.get("pl") or 0.0)
        signals = []
        if abs(chg) >= 1.5:
            signals.append(f"Variação incomum no dia ({chg:+.2f}%)")
        if cat.get("asset_class") == "FII" and 0 < pvp <= 0.95:
            signals.append(f"Desconto patrimonial relevante (P/VP {pvp:.2f}x)")
        elif cat.get("asset_class") == "ACAO_BR" and 0 < pl <= 8.5:
            signals.append(f"Múltiplo P/L baixo ({pl:.1f}x)")
        if dy >= min_dy_target:
            signals.append(f"DY 12m ({dy:.1f}%) atinge ou supera sua meta ({min_dy_target:.1f}%)")
        if not signals:
            signals.append("Ativo em acompanhamento na sua lista de observação")
        ikey = f"WATCH:{ft}"
        watchlist_signals.append({
            "item_key": ikey,
            "ticker": ft,
            "name": cat.get("name", ft),
            "asset_class": cat.get("asset_class", "ACAO_BR"),
            "currency": cat.get("currency", "BRL"),
            "last_price": price,
            "change_pct": chg,
            "dy_12m": dy,
            "pvp": pvp,
            "pl": pl,
            "in_portfolio": ft in held_tickers,
            "signals": signals,
            "quote_source": cat.get("quote_source") or "Catálogo local",
            "updated_at": cat.get("updated_at") or "",
            "is_stale": is_quote_stale(cat.get("updated_at")),
            "user_status": item_states_map.get(ikey, {}).get("status", "ACOMPANHANDO"),
            "user_notes": item_states_map.get(ikey, {}).get("notes", ""),
        })

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

    radar_warnings: List[str] = []
    stale_held = [p["ticker"] for p in positions if is_quote_stale(p.get("updated_at"))]
    if stale_held:
        radar_warnings.append(
            f"{len(stale_held)} ativo(s) da carteira possuem cotação sem atualização nas últimas 24h ({', '.join(stale_held[:5])})."
        )
    if not settings.get("ai_api_key"):
        radar_warnings.append(
            "Chave de API de IA não configurada: o parecer executivo foi gerado pelo Motor Analítico Quantitativo do SIM."
        )
    elif ai_error:
        radar_warnings.append(
            f"API de IA indisponível ({ai_error}); exibindo análise quantitativa de contingência do SIM."
        )

    radar_sources: List[Dict[str, str]] = [
        {
            "name": "Carteira Local SQLite + Cotações de Mercado",
            "kind": "FATO_OBSERVADO",
            "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "url": "",
            "ticker": "CARTEIRA",
        },
        {
            "name": "Modelos Quantitativos SIM (Bazin, Graham, Score e Alocação)",
            "kind": "CALCULO_SIM",
            "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "url": "",
            "ticker": "MERCADO",
        },
    ]
    for opp in top_opportunities[:4]:
        if opp.get("latest_report_url"):
            radar_sources.append({
                "name": opp.get("latest_report") or f"Relatório Oficial ({opp['ticker']})",
                "kind": "FATO_OBSERVADO",
                "updated_at": "",
                "url": opp["latest_report_url"],
                "ticker": opp["ticker"],
            })
        if opp.get("latest_news_link"):
            radar_sources.append({
                "name": f"Notícia ({opp['ticker']}): {opp.get('latest_news', '')[:70]}",
                "kind": "FATO_OBSERVADO",
                "updated_at": opp.get("latest_news_date", ""),
                "url": opp["latest_news_link"],
                "ticker": opp["ticker"],
            })

    radar_risks = [
        "Descontos em P/VP ou P/L podem refletir deterioração operacional, vacância, alavancagem ou risco regulatório (armadilha de valor / value trap).",
        "Dividend Yield passado de 12 meses não garante distribuição futura, especialmente em setores cíclicos (commodities) ou FIIs de papel indexados à inflação/CDI.",
    ]

    radar_facts = {
        "total_patrimony_brl": round(total_patrimony, 2),
        "positions_count": len(positions),
        "top_opportunity_ticker": top_opportunities[0]["ticker"] if top_opportunities else "",
        "top_opportunity_score": top_opportunities[0]["score"] if top_opportunities else 0,
        "alerts_count": len(portfolio_alerts),
        "watchlist_count": len(watchlist_signals),
    }
    prev_radar = _get_latest_saved_analysis(user_id=user_id, analysis_type="RADAR", target_key="RADAR_GERAL")
    delta_since_last = _compute_facts_delta(prev_radar, radar_facts, {})

    result = {
        "generated_at": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
        "prompt_version": PROMPT_VERSION,
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
        "risks_and_counterarguments": radar_risks,
        "data_warnings": radar_warnings,
        "sources": radar_sources,
        "limitations": STANDARD_LIMITATIONS,
        "delta_since_last": delta_since_last,
        "ai_error": ai_error,
        "portfolio_alerts": portfolio_alerts[:6],
        "opportunities": top_opportunities,
        "watchlist_signals": watchlist_signals,
        "item_states": item_states_map,
    }

    analysis_id = save_analysis_record(
        user_id=user_id,
        analysis_type="RADAR",
        target_key="RADAR_GERAL",
        provider=settings.get("ai_provider", "SIM_QUANT") if ai_generated else "SIM_QUANT",
        model=settings.get("ai_model", "sim-quant-v1") if ai_generated else "sim-quant-v1",
        parameters={"investor_profile": investor_profile, "min_dy_target": min_dy_target},
        facts=radar_facts,
        sources=radar_sources,
        warnings=radar_warnings,
        result={
            "executive_briefing": executive_briefing,
            "action_recommendations": action_recommendations,
            "risks_and_counterarguments": radar_risks,
            "delta_since_last": delta_since_last,
        },
    )
    result["analysis_id"] = analysis_id

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


# ==============================================================================
# ETAPA 4 — GESTÃO DE ITENS DO RADAR, HISTÓRICO E ANALISTA DE IA ESTRUTURADO
# ==============================================================================

VALID_RADAR_ITEM_STATUSES = {"NOVO", "RELEVANTE", "ACOMPANHANDO", "IGNORADO"}


def get_radar_item_states(user_id: int = 1) -> Dict[str, Dict[str, Any]]:
    """Retorna os estados marcados pelo usuário para itens do radar (oportunidades, alertas e watchlist)."""
    migrate_ai_stage4_tables()
    conn = get_conn()
    rows = conn.execute(
        "SELECT item_key, ticker, status, notes, updated_at FROM radar_item_states WHERE user_id = ?",
        (user_id,),
    ).fetchall()
    conn.close()
    return {
        r["item_key"]: {
            "item_key": r["item_key"],
            "ticker": r["ticker"],
            "status": r["status"],
            "notes": r["notes"],
            "updated_at": r["updated_at"],
        }
        for r in rows
    }


def set_radar_item_state(
    item_key: str,
    status: str,
    ticker: str = "",
    notes: str = "",
    user_id: int = 1,
) -> Dict[str, Any]:
    """Marca um item do radar como RELEVANTE, ACOMPANHANDO, IGNORADO ou NOVO."""
    migrate_ai_stage4_tables()
    clean_key = (item_key or "").strip().upper()
    if not clean_key:
        raise ValueError("Identificador do item do radar (item_key) é obrigatório.")
    clean_status = (status or "NOVO").strip().upper()
    if clean_status not in VALID_RADAR_ITEM_STATUSES:
        raise ValueError(f"Status inválido '{status}'. Valores aceitos: {', '.join(sorted(VALID_RADAR_ITEM_STATUSES))}.")
    clean_ticker = (ticker or (clean_key.split(":", 1)[1] if ":" in clean_key else clean_key)).strip().upper()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    conn = get_conn()
    conn.execute(
        """
        INSERT INTO radar_item_states (user_id, item_key, ticker, status, notes, updated_at)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(user_id, item_key) DO UPDATE SET
            ticker = excluded.ticker,
            status = excluded.status,
            notes = excluded.notes,
            updated_at = excluded.updated_at
        """,
        (user_id, clean_key, clean_ticker, clean_status, (notes or "").strip(), now_str),
    )
    conn.commit()
    conn.close()
    return {
        "item_key": clean_key,
        "ticker": clean_ticker,
        "status": clean_status,
        "notes": (notes or "").strip(),
        "updated_at": now_str,
    }


def _apply_live_item_states_to_radar(radar_data: Dict[str, Any], user_id: int = 1) -> Dict[str, Any]:
    states = get_radar_item_states(user_id=user_id)
    radar_data["item_states"] = states
    for a in radar_data.get("portfolio_alerts", []):
        ik = a.get("item_key") or f"ALERT:{a.get('ticker', '')}"
        a["item_key"] = ik
        a["user_status"] = states.get(ik, {}).get("status", a.get("user_status", "NOVO"))
    for o in radar_data.get("opportunities", []):
        ik = o.get("item_key") or f"OPP:{o.get('ticker', '')}"
        o["item_key"] = ik
        o["user_status"] = states.get(ik, {}).get("status", o.get("user_status", "NOVO"))
    for w in radar_data.get("watchlist_signals", []):
        ik = w.get("item_key") or f"WATCH:{w.get('ticker', '')}"
        w["item_key"] = ik
        w["user_status"] = states.get(ik, {}).get("status", w.get("user_status", "ACOMPANHANDO"))
    return radar_data


def save_analysis_record(
    user_id: int,
    analysis_type: str,
    target_key: str,
    provider: str,
    model: str,
    parameters: Dict[str, Any],
    facts: Dict[str, Any],
    sources: List[Dict[str, Any]],
    warnings: List[str],
    result: Dict[str, Any],
    prompt_version: str = PROMPT_VERSION,
) -> int:
    """Salva uma análise rastreável no SQLite com data/hora, parâmetros, fontes, alertas e versão do modelo/prompt."""
    migrate_ai_stage4_tables()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO ai_analysis_history (
            user_id, analysis_type, target_key, provider, model, prompt_version,
            parameters_json, facts_json, sources_json, warnings_json, result_json, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            user_id,
            analysis_type.upper().strip(),
            target_key.upper().strip(),
            provider,
            model,
            prompt_version,
            json.dumps(parameters or {}, ensure_ascii=False),
            json.dumps(facts or {}, ensure_ascii=False),
            json.dumps(sources or [], ensure_ascii=False),
            json.dumps(warnings or [], ensure_ascii=False),
            json.dumps(result or {}, ensure_ascii=False),
            now_str,
        ),
    )
    new_id = int(cur.lastrowid)
    conn.commit()
    conn.close()
    return new_id


def _row_to_analysis_dict(r: Any) -> Dict[str, Any]:
    return {
        "id": int(r["id"]),
        "user_id": int(r["user_id"]),
        "analysis_type": r["analysis_type"],
        "target_key": r["target_key"],
        "provider": r["provider"],
        "model": r["model"],
        "prompt_version": r["prompt_version"],
        "parameters": json.loads(r["parameters_json"] or "{}"),
        "facts": json.loads(r["facts_json"] or "{}"),
        "sources": json.loads(r["sources_json"] or "[]"),
        "warnings": json.loads(r["warnings_json"] or "[]"),
        "result": json.loads(r["result_json"] or "{}"),
        "created_at": r["created_at"],
    }


def _get_latest_saved_analysis(user_id: int, analysis_type: str, target_key: str) -> Optional[Dict[str, Any]]:
    migrate_ai_stage4_tables()
    conn = get_conn()
    row = conn.execute(
        """
        SELECT * FROM ai_analysis_history
        WHERE user_id = ? AND analysis_type = ? AND target_key = ?
        ORDER BY id DESC LIMIT 1
        """,
        (user_id, analysis_type.upper().strip(), target_key.upper().strip()),
    ).fetchone()
    conn.close()
    return _row_to_analysis_dict(row) if row else None


def list_analysis_history(
    user_id: int = 1,
    analysis_type: str = "",
    target_key: str = "",
    limit: int = 20,
) -> List[Dict[str, Any]]:
    """Lista o histórico de análises salvas para consulta, auditoria e comparação."""
    migrate_ai_stage4_tables()
    conn = get_conn()
    clauses = ["user_id = ?"]
    params: List[Any] = [user_id]
    if analysis_type and analysis_type.upper() != "ALL":
        clauses.append("analysis_type = ?")
        params.append(analysis_type.upper().strip())
    if target_key and target_key.upper() != "ALL":
        clauses.append("target_key = ?")
        params.append(target_key.upper().strip())
    params.append(max(1, min(100, int(limit))))
    sql = f"SELECT * FROM ai_analysis_history WHERE {' AND '.join(clauses)} ORDER BY id DESC LIMIT ?"
    rows = conn.execute(sql, tuple(params)).fetchall()
    conn.close()
    return [_row_to_analysis_dict(r) for r in rows]


def get_analysis_by_id(analysis_id: int, user_id: int = 1) -> Optional[Dict[str, Any]]:
    migrate_ai_stage4_tables()
    conn = get_conn()
    row = conn.execute(
        "SELECT * FROM ai_analysis_history WHERE id = ? AND user_id = ?",
        (int(analysis_id), user_id),
    ).fetchone()
    conn.close()
    return _row_to_analysis_dict(row) if row else None


def _compute_facts_delta(
    prev_record: Optional[Dict[str, Any]],
    current_facts: Dict[str, Any],
    current_calcs: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Calcula objetivamente 'O que mudou desde a última análise?' comparando fatos observados e cálculos."""
    if not prev_record:
        return {
            "has_previous": False,
            "previous_id": None,
            "previous_date": "",
            "changes": [],
            "summary": "Primeira análise registrada para este escopo no histórico do SIM.",
        }

    prev_facts = prev_record.get("facts") or {}
    changes: List[str] = []

    label_map = {
        "total_patrimony_brl": ("Patrimônio Total (R$)", "money_brl"),
        "total_current_brl": ("Patrimônio Atual (R$)", "money_brl"),
        "total_invested_brl": ("Total Investido (R$)", "money_brl"),
        "profit_brl": ("Resultado Acumulado (R$)", "money_brl"),
        "profit_pct": ("Rentabilidade (%)", "pct"),
        "hhi": ("Índice de Concentração HHI", "num"),
        "top1_pct": ("Peso da Maior Posição (%)", "pct"),
        "positions_count": ("Quantidade de Ativos", "int"),
        "holdings_count": ("Quantidade de Posições", "int"),
        "last_price": ("Cotação do Ativo", "num"),
        "dy_12m": ("Dividend Yield 12m (%)", "pct"),
        "pl": ("P/L", "num"),
        "pvp": ("P/VP", "num"),
        "usd_brl": ("Câmbio USD/BRL", "num"),
        "news_count": ("Notícias Recentes", "int"),
        "official_docs_count": ("Relatórios Oficiais", "int"),
    }

    for k, (lbl, fmt) in label_map.items():
        if k in current_facts and k in prev_facts:
            try:
                v_now = float(current_facts[k])
                v_old = float(prev_facts[k])
                diff = v_now - v_old
                if abs(diff) >= 0.01:
                    if fmt == "money_brl":
                        changes.append(f"{lbl}: de R$ {v_old:,.2f} para R$ {v_now:,.2f} ({diff:+,.2f})")
                    elif fmt == "pct":
                        changes.append(f"{lbl}: de {v_old:.2f}% para {v_now:.2f}% ({diff:+.2f} p.p.)")
                    elif fmt == "int":
                        changes.append(f"{lbl}: de {int(v_old)} para {int(v_now)} ({int(diff):+d})")
                    else:
                        changes.append(f"{lbl}: de {v_old:.2f} para {v_now:.2f} ({diff:+.2f})")
            except Exception:
                pass

    if not changes:
        summary = f"Sem alterações numéricas relevantes nos fatos monitorados desde a análise de {prev_record['created_at']}."
    else:
        summary = f"{len(changes)} mudança(s) detectada(s) desde a análise anterior ({prev_record['created_at']}): " + "; ".join(changes[:4]) + "."

    return {
        "has_previous": True,
        "previous_id": prev_record["id"],
        "previous_date": prev_record["created_at"],
        "previous_provider": f"{prev_record.get('provider', '')} · {prev_record.get('model', '')}".strip(" ·"),
        "changes": changes,
        "summary": summary,
    }


def compare_saved_analyses(
    id_a: Optional[int] = None,
    id_b: Optional[int] = None,
    analysis_type: str = "PORTFOLIO",
    target_key: str = "CARTEIRA",
    user_id: int = 1,
) -> Dict[str, Any]:
    """Compara duas análises salvas (ou as duas mais recentes de um mesmo escopo)."""
    if id_a and id_b:
        rec_older = get_analysis_by_id(min(id_a, id_b), user_id=user_id)
        rec_newer = get_analysis_by_id(max(id_a, id_b), user_id=user_id)
    else:
        recent = list_analysis_history(user_id=user_id, analysis_type=analysis_type, target_key=target_key, limit=2)
        if len(recent) < 2:
            return {
                "available": False,
                "reason": "São necessárias pelo menos 2 análises salvas deste escopo para comparação histórica.",
                "records_found": len(recent),
                "latest": recent[0] if recent else None,
            }
        rec_newer, rec_older = recent[0], recent[1]

    if not rec_older or not rec_newer:
        raise ValueError("Uma ou ambas as análises solicitadas não foram encontradas.")

    delta = _compute_facts_delta(rec_older, rec_newer.get("facts") or {})
    return {
        "available": True,
        "analysis_type": rec_newer["analysis_type"],
        "target_key": rec_newer["target_key"],
        "older": {
            "id": rec_older["id"],
            "created_at": rec_older["created_at"],
            "provider": rec_older["provider"],
            "model": rec_older["model"],
            "prompt_version": rec_older["prompt_version"],
            "facts": rec_older["facts"],
            "result": rec_older["result"],
            "warnings": rec_older["warnings"],
        },
        "newer": {
            "id": rec_newer["id"],
            "created_at": rec_newer["created_at"],
            "provider": rec_newer["provider"],
            "model": rec_newer["model"],
            "prompt_version": rec_newer["prompt_version"],
            "facts": rec_newer["facts"],
            "result": rec_newer["result"],
            "warnings": rec_newer["warnings"],
        },
        "delta": delta,
    }


def analyze_portfolio_deep(user_id: int = 1) -> Dict[str, Any]:
    """
    Ação do Analista de IA: 'Analisar minha carteira' + 'O que merece minha atenção?' + 'O que mudou desde a última análise?'.
    Envia apenas os dados estruturados necessários, separa Fato Observado, Cálculo SIM e Interpretação IA,
    aponta riscos/argumentos contrários e salva no histórico.
    """
    settings = get_raw_settings(user_id=user_id)
    investor_profile = settings.get("investor_profile", "RENDA_E_VALOR")
    min_dy_target = float(settings.get("min_dy_target") or 8.0)

    dash = get_dashboard(user_id=user_id, period="ALL", country="ALL", currency="ALL", asset_class="ALL", record=False)
    kpis = dash.get("kpis", {})
    conc = dash.get("concentration", {})
    dist = dash.get("distribution", {})
    fx_info = dash.get("fx", {})
    dq = dash.get("data_quality", {})
    holdings = dash.get("holdings", [])

    conn_fx = get_conn()
    est_tx_cnt = conn_fx.execute(
        "SELECT COUNT(*) FROM transactions WHERE user_id = ? AND fx_estimated = 1",
        (user_id,),
    ).fetchone()[0]
    conn_fx.close()

    warnings: List[str] = []
    if not holdings:
        warnings.append("A carteira não possui posições abertas no momento; a análise reflete patrimônio zerado.")
    if dq.get("stale_codes"):
        warnings.append(
            f"Cotações com mais de 24h sem atualização para: {', '.join(dq['stale_codes'][:6])}."
        )
    if est_tx_cnt > 0:
        warnings.append(
            f"{est_tx_cnt} operação(ões) em moeda estrangeira usam câmbio estimado."
        )
    if dash.get("dividends", {}).get("has_estimated_fx"):
        warnings.append(
            "Proventos em USD foram convertidos pelo câmbio atual (sem câmbio histórico informado)."
        )

    facts_observed = {
        "kind": "FATO_OBSERVADO",
        "generated_at": dash.get("generated_at"),
        "holdings_count": int(kpis.get("holdings_count") or 0),
        "total_invested_brl": round(float(kpis.get("total_invested_brl") or 0.0), 2),
        "total_current_brl": round(float(kpis.get("total_current_brl") or 0.0), 2),
        "dividends_received_brl": round(float(kpis.get("dividends_period_brl") or 0.0), 2),
        "usd_brl": float(fx_info.get("usd_brl") or 0.0),
        "usd_brl_updated_at": fx_info.get("updated_at") or "",
        "usd_brl_source": fx_info.get("source") or "",
        "top_holdings": [
            {
                "code": h["code"],
                "name": h["name"],
                "asset_class": h["asset_class"],
                "country": h["country"],
                "currency": h["currency"],
                "sector": h["sector"],
                "invested_brl": h["invested_brl"],
                "current_brl": h["current_brl"],
                "weight_pct": h["weight_pct"],
            }
            for h in holdings[:10]
        ],
    }

    sim_calculations = {
        "kind": "CALCULO_SIM",
        "profit_brl": round(float(kpis.get("profit_brl") or 0.0), 2),
        "profit_pct": round(float(kpis.get("profit_pct") or 0.0), 2),
        "unrealized_profit_brl": round(float(kpis.get("unrealized_profit_brl") or 0.0), 2),
        "realized_profit_brl": round(float(kpis.get("realized_profit_brl") or 0.0), 2),
        "top1_pct": round(float(conc.get("top1_pct") or 0.0), 2),
        "top5_pct": round(float(conc.get("top5_pct") or 0.0), 2),
        "top10_pct": round(float(conc.get("top10_pct") or 0.0), 2),
        "hhi": round(float(conc.get("hhi") or 0.0), 4),
        "effective_positions": round(float(conc.get("effective_positions") or 0.0), 2),
        "by_class": dist.get("by_class", []),
        "by_country": dist.get("by_country", []),
        "by_currency": dist.get("by_currency", []),
        "by_sector": dist.get("by_sector", [])[:8],
    }

    prev_record = _get_latest_saved_analysis(user_id=user_id, analysis_type="PORTFOLIO", target_key="CARTEIRA")
    flat_facts_for_delta = {
        "total_invested_brl": facts_observed["total_invested_brl"],
        "total_current_brl": facts_observed["total_current_brl"],
        "profit_brl": sim_calculations["profit_brl"],
        "profit_pct": sim_calculations["profit_pct"],
        "hhi": sim_calculations["hhi"],
        "top1_pct": sim_calculations["top1_pct"],
        "holdings_count": facts_observed["holdings_count"],
        "usd_brl": facts_observed["usd_brl"],
    }
    delta_since_last = _compute_facts_delta(prev_record, flat_facts_for_delta, sim_calculations)

    # Interpretação determinística base (usada como fallback ou complemento rastreável)
    strengths: List[str] = []
    risks_and_counterarguments: List[str] = []
    attention_points: List[str] = []

    if not holdings:
        summary_text = "Sua carteira ainda não possui ativos cadastrados. Cadastre operações ou importe sua planilha B3 para análise de diversificação e risco."
        attention_points.append("Nenhuma posição aberta encontrada no banco local.")
    else:
        top1 = holdings[0]
        hhi_val = sim_calculations["hhi"]
        eff_n = sim_calculations["effective_positions"]
        classes_cnt = len(sim_calculations["by_class"])
        countries_cnt = len(sim_calculations["by_country"])

        if classes_cnt >= 3:
            strengths.append(f"Diversificação entre {classes_cnt} classes de ativos distintas ({', '.join(c['label'] for c in sim_calculations['by_class'][:4])}).")
        if countries_cnt >= 2:
            strengths.append("Exposição internacional combinando ativos em BRL e USD, reduzindo risco puramente doméstico.")
        if sim_calculations["profit_brl"] > 0:
            strengths.append(f"Resultado acumulado positivo de R$ {sim_calculations['profit_brl']:,.2f} ({sim_calculations['profit_pct']:+.2f}%).")
        if facts_observed["dividends_received_brl"] > 0:
            strengths.append(f"Geração de proventos registrados totalizando R$ {facts_observed['dividends_received_brl']:,.2f}.")
        if not strengths:
            strengths.append(f"Carteira estruturada com {len(holdings)} posição(ões) rastreada(s) localmente.")

        if sim_calculations["top1_pct"] >= 25.0 or hhi_val >= 0.20:
            risks_and_counterarguments.append(
                f"Concentração elevada: a maior posição ({top1['code']}) representa {sim_calculations['top1_pct']:.1f}% da carteira (HHI {hhi_val:.3f}, equivalente a {eff_n:.1f} posições iguais)."
            )
            attention_points.append(
                f"Avaliar se o peso de {top1['code']} ({sim_calculations['top1_pct']:.1f}%) está alinhado à sua tolerância a risco idiossincrático."
            )
        else:
            risks_and_counterarguments.append(
                f"Mesmo com concentração moderada (Top 1 em {sim_calculations['top1_pct']:.1f}%, HHI {hhi_val:.3f}), correlações macroeconômicas (juros Selic e fiscal no Brasil) podem afetar múltiplas classes simultaneamente."
            )

        if countries_cnt == 1 and sim_calculations["by_country"][0]["key"] == "BR":
            risks_and_counterarguments.append(
                "100% do patrimônio monitorado está concentrado no Brasil (BRL), sujeito ao risco fiscal doméstico e desvalorização cambial."
            )
        elif any(c["key"] == "USD" for c in sim_calculations["by_currency"]):
            risks_and_counterarguments.append(
                f"Parcela dolarizada sujeita à volatilidade cambial (USD/BRL atual em R$ {facts_observed['usd_brl']:.4f}): valorização do Real reduz o saldo convertido em BRL."
            )

        if sim_calculations["by_sector"]:
            top_sec = sim_calculations["by_sector"][0]
            if top_sec["weight_pct"] >= 30.0:
                attention_points.append(
                    f"Setor '{top_sec['label']}' concentra {top_sec['weight_pct']:.1f}% do patrimônio."
                )

        losers = [h for h in holdings if h["profit_pct"] <= -10.0]
        if losers:
            attention_points.append(
                f"Posições com retração superior a -10% sobre o custo: {', '.join(f'{l['code']} ({l['profit_pct']:+.1f}%)' for l in losers[:4])} — investigar se os fundamentos permanecem intactos antes de qualquer novo aporte."
            )
        if not attention_points:
            attention_points.append("Acompanhar os comunicados trimestrais/mensais dos principais ativos e a evolução dos proventos.")

        summary_text = (
            f"Carteira com {len(holdings)} posição(ões), patrimônio atual de R$ {facts_observed['total_current_brl']:,.2f} "
            f"sobre R$ {facts_observed['total_invested_brl']:,.2f} investidos ({sim_calculations['profit_pct']:+.2f}%). "
            f"A maior posição é {top1['code']} ({sim_calculations['top1_pct']:.1f}%) e o índice HHI é {hhi_val:.3f} "
            f"({eff_n:.1f} posições equivalentes)."
        )

    ai_generated = False
    ai_provider_used = "Motor Analítico Quantitativo SIM (Determinístico)"
    ai_error = ""

    if settings.get("ai_api_key") and holdings:
        try:
            context_payload = {
                "investor_profile": investor_profile,
                "min_dy_target_pct": min_dy_target,
                "facts_observed": facts_observed,
                "sim_calculations": sim_calculations,
                "data_warnings": warnings,
                "delta_since_last": delta_since_last["summary"],
            }
            prompt = (
                "Você é um analista de investimentos criterioso. Analise EXCLUSIVAMENTE os dados estruturados da carteira abaixo. "
                "NÃO invente cotações, múltiplos, notícias ou ativos que não estejam no JSON fornecido. "
                "Toda afirmação factual deve citar os números fornecidos.\n\n"
                f"DADOS DA CARTEIRA (JSON):\n{json.dumps(context_payload, ensure_ascii=False)}\n\n"
                "Retorne estritamente um objeto JSON com as seguintes chaves:\n"
                '- "summary": string (síntese executiva de 3 a 4 frases distinguindo fatos da carteira e interpretação)\n'
                '- "strengths": lista de 2 a 4 strings com pontos fortes reais da carteira\n'
                '- "risks_and_counterarguments": lista de 2 a 4 strings com riscos concretos, concentrações e argumentos contrários\n'
                '- "attention_points": lista de 2 a 4 strings respondendo objetivamente "O que merece minha atenção agora?" sem emitir ordens de compra/venda.'
            )
            llm_resp = call_configured_llm(prompt, json_mode=True, user_id=user_id)
            if llm_resp:
                parsed = json.loads(_clean_json_markdown(llm_resp))
                if parsed.get("summary"):
                    summary_text = str(parsed["summary"])
                    if isinstance(parsed.get("strengths"), list) and parsed["strengths"]:
                        strengths = [str(x) for x in parsed["strengths"][:5]]
                    if isinstance(parsed.get("risks_and_counterarguments"), list) and parsed["risks_and_counterarguments"]:
                        risks_and_counterarguments = [str(x) for x in parsed["risks_and_counterarguments"][:5]]
                    if isinstance(parsed.get("attention_points"), list) and parsed["attention_points"]:
                        attention_points = [str(x) for x in parsed["attention_points"][:5]]
                    ai_generated = True
                    ai_provider_used = f"{settings.get('ai_provider')} · {settings.get('ai_model')}"
        except Exception as exc:
            ai_error = _sanitize_error_message(str(exc), settings.get("ai_api_key", ""))
            warnings.append(f"Falha ao consultar API de IA ({ai_error}); exibindo interpretação determinística do SIM.")
    elif not settings.get("ai_api_key"):
        warnings.append("Chave de API de IA não configurada; análise gerada pelo motor analítico local do SIM.")

    sources = [
        {
            "name": "Posições e Operações no Banco Local (SQLite)",
            "kind": "FATO_OBSERVADO",
            "updated_at": dash.get("generated_at", ""),
            "url": "",
            "ticker": "CARTEIRA",
        },
        {
            "name": f"Câmbio USD/BRL ({fx_info.get('source', 'Catálogo')})",
            "kind": "FATO_OBSERVADO",
            "updated_at": fx_info.get("updated_at") or "",
            "url": "",
            "ticker": "USDBRL",
        },
        {
            "name": "Consolidação de Alocação, Concentração HHI e Retorno (Dashboard SIM)",
            "kind": "CALCULO_SIM",
            "updated_at": dash.get("generated_at", ""),
            "url": "",
            "ticker": "CARTEIRA",
        },
    ]

    ai_interpretation = {
        "kind": "INTERPRETACAO_IA",
        "ai_generated": ai_generated,
        "provider_used": ai_provider_used,
        "prompt_version": PROMPT_VERSION,
        "summary": summary_text,
        "strengths": strengths,
        "risks_and_counterarguments": risks_and_counterarguments,
        "attention_points": attention_points,
    }

    result_payload = {
        "analysis_type": "PORTFOLIO",
        "target_key": "CARTEIRA",
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "prompt_version": PROMPT_VERSION,
        "ai_generated": ai_generated,
        "ai_provider_used": ai_provider_used,
        "ai_error": ai_error,
        "facts_observed": facts_observed,
        "sim_calculations": sim_calculations,
        "ai_interpretation": ai_interpretation,
        "delta_since_last": delta_since_last,
        "data_warnings": warnings,
        "sources": sources,
        "limitations": STANDARD_LIMITATIONS,
    }

    analysis_id = save_analysis_record(
        user_id=user_id,
        analysis_type="PORTFOLIO",
        target_key="CARTEIRA",
        provider=settings.get("ai_provider", "SIM_QUANT") if ai_generated else "SIM_QUANT",
        model=settings.get("ai_model", "sim-quant-v1") if ai_generated else "sim-quant-v1",
        parameters={"investor_profile": investor_profile, "min_dy_target": min_dy_target},
        facts=flat_facts_for_delta,
        sources=sources,
        warnings=warnings,
        result={
            "summary": summary_text,
            "strengths": strengths,
            "risks_and_counterarguments": risks_and_counterarguments,
            "attention_points": attention_points,
            "delta_since_last": delta_since_last,
        },
    )
    result_payload["analysis_id"] = analysis_id
    return result_payload


def analyze_asset_deep(ticker: str, period: str = "1Y", user_id: int = 1) -> Dict[str, Any]:
    """
    Ação do Analista de IA: 'Analisar este ativo: histórico, dados recentes, notícias e riscos' + 'O que mudou desde a última análise?'.
    Separa Fato Observado, Cálculo SIM e Interpretação IA, sem classificar como barato/caro apenas pela média histórica.
    """
    t_up = (ticker or "").upper().strip()
    if not t_up:
        raise ValueError("Ticker é obrigatório para análise do ativo.")

    chart_data = get_asset_chart_and_dividends(t_up, period_key=period, user_id=user_id)
    if not chart_data:
        raise ValueError(f"Ativo {t_up} não encontrado.")

    settings = get_raw_settings(user_id=user_id)
    investor_profile = settings.get("investor_profile", "RENDA_E_VALOR")
    macro = fetch_macro_indicators()

    asset = chart_data["asset"]
    quote_meta = chart_data.get("quote_meta", {})
    hist_meta = chart_data.get("history_meta", {})
    hist_stats = chart_data.get("historical_stats", {})
    bench_comp = chart_data.get("benchmark_comparison", {})
    user_pos = chart_data.get("user_position", {})
    prof = chart_data.get("class_profile") or get_asset_specialized_profile(asset)
    val_models = _build_valuation_and_viability_models(asset, prof)

    news_data = fetch_asset_news(t_up)
    reports_data = fetch_official_reports(t_up)
    news_items = news_data.get("items", []) if isinstance(news_data, dict) else []
    official_docs = reports_data.get("reports", []) if isinstance(reports_data, dict) else []

    warnings: List[str] = []
    if quote_meta.get("is_stale"):
        warnings.append(
            f"Cotação de {t_up} sem atualização recente (última atualização registrada: {quote_meta.get('updated_at') or 'catálogo inicial'})."
        )
    if hist_meta.get("data_state") == "UNAVAILABLE":
        warnings.append("Série histórica de preços indisponível no momento (sem conexão com o provedor e sem cache local).")
    elif hist_meta.get("data_state") == "CACHED" and hist_meta.get("warning"):
        warnings.append(hist_meta["warning"])
    if isinstance(news_data, dict) and news_data.get("data_state") in ("UNAVAILABLE", "EMPTY"):
        warnings.append("Nenhuma notícia recente disponível nas fontes públicas ou cache local para este ativo.")
    elif isinstance(news_data, dict) and news_data.get("warning"):
        warnings.append(news_data["warning"])
    if asset.get("asset_class") == "ACAO_BR" and float(asset.get("pl") or 0) <= 0:
        warnings.append("Múltiplo P/L ausente ou igual a zero no catálogo atual; avaliação de valuation por lucros limitada.")

    facts_observed = {
        "kind": "FATO_OBSERVADO",
        "ticker": t_up,
        "name": asset.get("name", t_up),
        "asset_class": asset.get("asset_class", "ACAO_BR"),
        "sector": asset.get("sector", ""),
        "currency": asset.get("currency", "BRL"),
        "market": quote_meta.get("market", "BR"),
        "last_price": float(asset.get("last_price") or 0.0),
        "change_pct_day": float(asset.get("change_pct") or 0.0),
        "dy_12m": float(asset.get("dy_12m") or 0.0),
        "pl": float(asset.get("pl") or 0.0),
        "pvp": float(asset.get("pvp") or 0.0),
        "quote_source": quote_meta.get("source") or "Catálogo local",
        "quote_updated_at": quote_meta.get("updated_at") or "",
        "macro_context": {
            "selic_pct": float(macro.get("selic") or 0.0),
            "cdi_pct": float(macro.get("cdi") or 0.0),
            "ipca_12m_pct": float(macro.get("ipca_12m") or 0.0),
            "usd_brl": float(macro.get("usd_brl") or 0.0),
        },
        "recent_news": [
            {
                "title": n.get("title", ""),
                "source": n.get("source", ""),
                "published": n.get("published", ""),
                "link": n.get("link", ""),
            }
            for n in news_items[:5]
        ],
        "official_documents": [
            {
                "title": d.get("title", ""),
                "date": d.get("date", ""),
                "source": d.get("source", ""),
                "url": d.get("url", ""),
            }
            for d in official_docs[:5]
        ],
    }

    sim_calculations = {
        "kind": "CALCULO_SIM",
        "period": period.upper(),
        "period_change_pct": float(chart_data.get("period_change_pct") or 0.0),
        "historical_stats": hist_stats,
        "benchmark_comparison": bench_comp,
        "valuation_models": {
            "bazin": val_models.get("bazin", {}),
            "graham": val_models.get("graham", {}),
        },
        "user_position": user_pos,
    }

    prev_record = _get_latest_saved_analysis(user_id=user_id, analysis_type="ASSET", target_key=t_up)
    flat_facts = {
        "last_price": facts_observed["last_price"],
        "dy_12m": facts_observed["dy_12m"],
        "pl": facts_observed["pl"],
        "pvp": facts_observed["pvp"],
        "news_count": len(news_items),
        "official_docs_count": len(official_docs),
    }
    delta_since_last = _compute_facts_delta(prev_record, flat_facts, sim_calculations)

    # Fatores positivos, riscos e argumentos contrários determinísticos baseados nos dados reais
    positive_factors: List[str] = []
    risks_and_counterarguments: List[str] = []
    attention_points: List[str] = []

    cls = facts_observed["asset_class"]
    dy = facts_observed["dy_12m"]
    pvp = facts_observed["pvp"]
    pl = facts_observed["pl"]
    selic = facts_observed["macro_context"]["selic_pct"]

    if dy >= 8.0:
        positive_factors.append(f"Dividend Yield de 12 meses observado em {dy:.2f}% a.a.")
    if cls == "FII" and 0 < pvp <= 0.98:
        positive_factors.append(f"Negociando a P/VP de {pvp:.2f}x (abaixo do valor patrimonial de referência).")
    elif cls == "ACAO_BR" and 0 < pl <= 10.0:
        positive_factors.append(f"Múltiplo P/L observado em {pl:.1f}x.")
    if bench_comp.get("available") and float(bench_comp.get("relative_diff_pp") or 0.0) > 0:
        positive_factors.append(
            f"No período ({period.upper()}), acumulou {bench_comp['asset_return_pct']:+.2f}% vs {bench_comp['benchmark_return_pct']:+.2f}% do {bench_comp['benchmark_name']} ({bench_comp['relative_diff_pp']:+.2f} p.p.)."
        )
    if official_docs:
        positive_factors.append(f"{len(official_docs)} documento(s) oficial(is) disponível(is) para auditoria direta ({official_docs[0]['title']}).")
    if not positive_factors:
        positive_factors.append(f"Ativo monitorado com cotação em {facts_observed['currency']} {facts_observed['last_price']:.2f} ({facts_observed['quote_source']}).")

    # Riscos e argumentos contrários obrigatórios (incluindo juros, inflação, câmbio e armadilha de média histórica)
    if hist_stats.get("available"):
        dist_avg = float(hist_stats.get("distance_from_avg_pct") or 0.0)
        if dist_avg < -3.0:
            risks_and_counterarguments.append(
                f"Cotação está {dist_avg:+.2f}% abaixo da média do período ({facts_observed['currency']} {hist_stats['avg_price']:.2f}), mas preço abaixo da média histórica não significa que o ativo esteja barato: pode refletir queda de lucro, vacância ou juros altos (Selic {selic:.2f}% a.a.)."
            )
        elif dist_avg > 3.0:
            risks_and_counterarguments.append(
                f"Cotação está {dist_avg:+.2f}% acima da média do período ({facts_observed['currency']} {hist_stats['avg_price']:.2f}), reduzindo a margem de segurança caso o crescimento de resultados desacelere."
            )

    if cls in ("ACAO_BR", "FII") and selic >= 10.0:
        risks_and_counterarguments.append(
            f"Custo de oportunidade elevado no Brasil: com Selic em {selic:.2f}% a.a. e CDI em {facts_observed['macro_context']['cdi_pct']:.2f}% a.a., ativos de renda variável exigem prêmio de risco consistente sobre a renda fixa."
        )
    if cls == "STOCK_US":
        risks_and_counterarguments.append(
            f"Exposição cambial USD/BRL (R$ {facts_observed['macro_context']['usd_brl']:.4f}) e retenção de 30% de imposto sobre dividendos pagos nos EUA para não residentes."
        )
    if bench_comp.get("available") and float(bench_comp.get("relative_diff_pp") or 0.0) < 0:
        risks_and_counterarguments.append(
            f"Desempenho inferior ao índice {bench_comp['benchmark_name']} no período ({bench_comp['relative_diff_pp']:+.2f} p.p.)."
        )
    if not risks_and_counterarguments:
        risks_and_counterarguments.append(
            "Risco de mercado e variação de resultados operacionais: múltiplos passados não garantem manutenção de margens ou proventos."
        )

    if user_pos.get("has_position"):
        attention_points.append(
            f"Você possui {user_pos['quantity']:g} unidades ao Preço Médio de {facts_observed['currency']} {user_pos['avg_price']:.2f} (cotação atual {facts_observed['currency']} {facts_observed['last_price']:.2f})."
        )
    if news_items:
        attention_points.append(f"Notícia mais recente ({news_items[0]['published']}): \"{news_items[0]['title']}\" ({news_items[0]['source']}).")
    if official_docs:
        attention_points.append(f"Verificar o documento oficial mais recente: {official_docs[0]['title']} ({official_docs[0]['date']}).")

    summary_text = (
        f"{t_up} ({facts_observed['name']}) negocia a {facts_observed['currency']} {facts_observed['last_price']:.2f} "
        f"(Fonte: {facts_observed['quote_source']}, atualizado em {facts_observed['quote_updated_at'] or 'catálogo'}). "
        + (
            f"No período {period.upper()}, variou {sim_calculations['period_change_pct']:+.2f}% "
            f"(faixa {facts_observed['currency']} {hist_stats['min_price']:.2f} – {hist_stats['max_price']:.2f}, média {hist_stats['avg_price']:.2f}). "
            if hist_stats.get("available")
            else "Série histórica não disponível no momento; análise baseada nos indicadores de catálogo e documentos locais. "
        )
        + f"DY 12m de {dy:.2f}% e P/VP de {pvp:.2f}x, em cenário de Selic a {selic:.2f}% a.a."
    )

    ai_generated = False
    ai_provider_used = "Motor Analítico Quantitativo SIM (Determinístico)"
    ai_error = ""

    if settings.get("ai_api_key"):
        try:
            context_payload = {
                "investor_profile": investor_profile,
                "facts_observed": facts_observed,
                "sim_calculations": sim_calculations,
                "data_warnings": warnings,
                "delta_since_last": delta_since_last["summary"],
            }
            prompt = (
                f"Analise o ativo {t_up} usando EXCLUSIVAMENTE os dados estruturados abaixo. "
                "NÃO invente cotações, fundamentos, notícias ou links. "
                "Não classifique o ativo como barato ou caro apenas pela média histórica: considere múltiplos, proventos, juros (Selic/CDI), inflação (IPCA) e câmbio.\n\n"
                f"DADOS DO ATIVO (JSON):\n{json.dumps(context_payload, ensure_ascii=False)}\n\n"
                "Retorne estritamente um objeto JSON com as chaves:\n"
                '- "summary": string (síntese analítica de 3 a 4 frases baseada nos dados fornecidos)\n'
                '- "positive_factors": lista de 2 a 4 strings com fatores positivos apoiados nos dados\n'
                '- "risks_and_counterarguments": lista de 2 a 4 strings com riscos concretos e argumentos contrários à tese\n'
                '- "attention_points": lista de 2 a 4 strings com pontos que merecem investigação adicional pelo investidor.'
            )
            llm_resp = call_configured_llm(prompt, json_mode=True, user_id=user_id)
            if llm_resp:
                parsed = json.loads(_clean_json_markdown(llm_resp))
                if parsed.get("summary"):
                    summary_text = str(parsed["summary"])
                    if isinstance(parsed.get("positive_factors"), list) and parsed["positive_factors"]:
                        positive_factors = [str(x) for x in parsed["positive_factors"][:5]]
                    if isinstance(parsed.get("risks_and_counterarguments"), list) and parsed["risks_and_counterarguments"]:
                        risks_and_counterarguments = [str(x) for x in parsed["risks_and_counterarguments"][:5]]
                    if isinstance(parsed.get("attention_points"), list) and parsed["attention_points"]:
                        attention_points = [str(x) for x in parsed["attention_points"][:5]]
                    ai_generated = True
                    ai_provider_used = f"{settings.get('ai_provider')} · {settings.get('ai_model')}"
        except Exception as exc:
            ai_error = _sanitize_error_message(str(exc), settings.get("ai_api_key", ""))
            warnings.append(f"Falha ao consultar API de IA ({ai_error}); exibindo interpretação determinística do SIM.")
    else:
        warnings.append("Chave de API de IA não configurada; análise gerada pelo motor analítico local do SIM.")

    sources: List[Dict[str, str]] = [
        {
            "name": f"Cotação e Indicadores ({facts_observed['quote_source']})",
            "kind": "FATO_OBSERVADO",
            "updated_at": facts_observed["quote_updated_at"],
            "url": "",
            "ticker": t_up,
        },
        {
            "name": f"Histórico de Preços ({hist_meta.get('source', 'Yahoo Finance')}) [{hist_meta.get('data_state', '')}]",
            "kind": "FATO_OBSERVADO",
            "updated_at": hist_meta.get("updated_at") or "",
            "url": "",
            "ticker": t_up,
        },
        {
            "name": "Estatísticas de Faixa, Média, Benchmark e Valuation (Bazin/Graham) — SIM",
            "kind": "CALCULO_SIM",
            "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "url": "",
            "ticker": t_up,
        },
    ]
    for d in official_docs[:3]:
        sources.append({
            "name": f"Documento Oficial: {d.get('title', '')}",
            "kind": "FATO_OBSERVADO",
            "updated_at": d.get("date", ""),
            "url": d.get("url", ""),
            "ticker": t_up,
        })
    for n in news_items[:3]:
        sources.append({
            "name": f"Notícia ({n.get('source', 'RSS')}): {n.get('title', '')[:70]}",
            "kind": "FATO_OBSERVADO",
            "updated_at": n.get("published", ""),
            "url": n.get("link", ""),
            "ticker": t_up,
        })

    ai_interpretation = {
        "kind": "INTERPRETACAO_IA",
        "ai_generated": ai_generated,
        "provider_used": ai_provider_used,
        "prompt_version": PROMPT_VERSION,
        "summary": summary_text,
        "positive_factors": positive_factors,
        "risks_and_counterarguments": risks_and_counterarguments,
        "attention_points": attention_points,
    }

    result_payload = {
        "analysis_type": "ASSET",
        "target_key": t_up,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "prompt_version": PROMPT_VERSION,
        "ai_generated": ai_generated,
        "ai_provider_used": ai_provider_used,
        "ai_error": ai_error,
        "facts_observed": facts_observed,
        "sim_calculations": sim_calculations,
        "ai_interpretation": ai_interpretation,
        "delta_since_last": delta_since_last,
        "data_warnings": warnings,
        "sources": sources,
        "limitations": STANDARD_LIMITATIONS,
    }

    analysis_id = save_analysis_record(
        user_id=user_id,
        analysis_type="ASSET",
        target_key=t_up,
        provider=settings.get("ai_provider", "SIM_QUANT") if ai_generated else "SIM_QUANT",
        model=settings.get("ai_model", "sim-quant-v1") if ai_generated else "sim-quant-v1",
        parameters={"ticker": t_up, "period": period.upper(), "investor_profile": investor_profile},
        facts=flat_facts,
        sources=sources,
        warnings=warnings,
        result={
            "summary": summary_text,
            "positive_factors": positive_factors,
            "risks_and_counterarguments": risks_and_counterarguments,
            "attention_points": attention_points,
            "delta_since_last": delta_since_last,
        },
    )
    result_payload["analysis_id"] = analysis_id
    return result_payload


def compare_similar_assets(tickers: List[str], period: str = "1Y", user_id: int = 1) -> Dict[str, Any]:
    """
    Ação do Analista de IA: 'Comparar ativos semelhantes com métricas comparáveis'.
    Se apenas 1 ticker for informado, seleciona automaticamente até 2 pares da mesma classe/setor do catálogo.
    """
    clean_tickers = []
    for t in tickers or []:
        tu = (t or "").upper().strip().replace(".SA", "")
        if tu and tu not in clean_tickers:
            clean_tickers.append(tu)

    if not clean_tickers:
        raise ValueError("Informe ao menos um ativo para comparação.")

    conn = get_conn()
    all_cat = [dict(r) for r in conn.execute("SELECT * FROM assets_catalog").fetchall()]
    conn.close()
    cat_map = {r["ticker"].upper(): r for r in all_cat}

    if len(clean_tickers) == 1:
        base_t = clean_tickers[0]
        base_row = cat_map.get(base_t)
        if base_row:
            base_cls = base_row.get("asset_class", "ACAO_BR")
            base_sec = (base_row.get("sector") or "").lower()
            same_sec = [
                r["ticker"] for r in all_cat
                if r["ticker"] != base_t and r.get("asset_class") == base_cls and (r.get("sector") or "").lower() == base_sec
            ]
            same_cls = [
                r["ticker"] for r in all_cat
                if r["ticker"] != base_t and r.get("asset_class") == base_cls and r["ticker"] not in same_sec
            ]
            peers = (same_sec + same_cls)[:2]
            clean_tickers.extend(peers)

    clean_tickers = clean_tickers[:4]
    if len(clean_tickers) < 2:
        raise ValueError("São necessários ao menos 2 ativos para realizar a comparação.")

    comparison_items: List[Dict[str, Any]] = []
    warnings: List[str] = []
    sources: List[Dict[str, str]] = []

    for t in clean_tickers:
        c_data = get_asset_chart_and_dividends(t, period_key=period, user_id=user_id)
        if not c_data:
            warnings.append(f"Ativo {t} não encontrado no catálogo.")
            continue
        a = c_data["asset"]
        qm = c_data.get("quote_meta", {})
        hs = c_data.get("historical_stats", {})
        prof = c_data.get("class_profile") or get_asset_specialized_profile(a)
        vm = _build_valuation_and_viability_models(a, prof)
        bazin = vm.get("bazin", {})
        graham = vm.get("graham", {})

        if qm.get("is_stale"):
            warnings.append(f"Cotação de {t} sem atualização recente ({qm.get('updated_at') or 'catálogo inicial'}).")

        comparison_items.append({
            "ticker": t,
            "name": a.get("name", t),
            "asset_class": a.get("asset_class", "ACAO_BR"),
            "sector": a.get("sector", ""),
            "currency": a.get("currency", "BRL"),
            "market": qm.get("market", "BR"),
            "last_price": float(a.get("last_price") or 0.0),
            "change_pct_day": float(a.get("change_pct") or 0.0),
            "period_change_pct": float(c_data.get("period_change_pct") or 0.0),
            "dy_12m": float(a.get("dy_12m") or 0.0),
            "pl": float(a.get("pl") or 0.0),
            "pvp": float(a.get("pvp") or 0.0),
            "bazin_ceiling": float(bazin.get("ceiling_price") or 0.0) if bazin.get("applicable") else None,
            "bazin_margin_pct": float(bazin.get("margin_pct") or 0.0) if bazin.get("applicable") else None,
            "graham_intrinsic": float(graham.get("intrinsic_value") or 0.0) if graham.get("applicable") else None,
            "graham_margin_pct": float(graham.get("margin_pct") or 0.0) if graham.get("applicable") else None,
            "hist_min": hs.get("min_price") if hs.get("available") else None,
            "hist_max": hs.get("max_price") if hs.get("available") else None,
            "hist_avg": hs.get("avg_price") if hs.get("available") else None,
            "distance_from_avg_pct": hs.get("distance_from_avg_pct") if hs.get("available") else None,
            "quote_source": qm.get("source") or "Catálogo local",
            "updated_at": qm.get("updated_at") or "",
        })
        sources.append({
            "name": f"{t}: {qm.get('source', 'Catálogo local')}",
            "kind": "FATO_OBSERVADO",
            "updated_at": qm.get("updated_at") or "",
            "url": "",
            "ticker": t,
        })

    if len(comparison_items) < 2:
        raise ValueError("Não foi possível carregar dados suficientes para comparar ao menos 2 ativos.")

    classes_set = {x["asset_class"] for x in comparison_items}
    currencies_set = {x["currency"] for x in comparison_items}
    if len(classes_set) > 1:
        warnings.append(
            f"Atenção metodológica: os ativos pertencem a classes distintas ({', '.join(sorted(classes_set))}); múltiplos como P/L e P/VP não são diretamente equivalentes entre classes."
        )
    if len(currencies_set) > 1:
        warnings.append(
            f"Os ativos são cotados em moedas diferentes ({', '.join(sorted(currencies_set))}); compare múltiplos relativos e considere o risco cambial."
        )

    best_dy = max(comparison_items, key=lambda x: x["dy_12m"])
    lowest_pvp = min([x for x in comparison_items if x["pvp"] > 0] or comparison_items, key=lambda x: x["pvp"])

    highlights_by_asset = [
        f"{x['ticker']} ({x['sector'] or x['asset_class']}): Cotação {x['currency']} {x['last_price']:.2f} | DY 12m {x['dy_12m']:.2f}% | P/VP {x['pvp']:.2f}x | P/L {x['pl']:.1f}x | Variação ({period.upper()}) {x['period_change_pct']:+.2f}%."
        for x in comparison_items
    ]
    risks_and_counterarguments = [
        f"Maior DY atual ({best_dy['ticker']} com {best_dy['dy_12m']:.2f}%) não garante sustentabilidade futura se decorrer de distribuições extraordinárias ou queda recente na cotação.",
        f"Menor P/VP ({lowest_pvp['ticker']} com {lowest_pvp['pvp']:.2f}x) exige verificar qualidade do portfólio/lucros e alavancagem para descartar desconto justificado por risco.",
    ]
    summary_text = (
        f"Comparação objetiva entre {', '.join(x['ticker'] for x in comparison_items)}: "
        f"{best_dy['ticker']} apresenta o maior Dividend Yield de 12 meses ({best_dy['dy_12m']:.2f}%), "
        f"enquanto {lowest_pvp['ticker']} negocia ao menor múltiplo P/VP ({lowest_pvp['pvp']:.2f}x)."
    )

    settings = get_raw_settings(user_id=user_id)
    ai_generated = False
    ai_provider_used = "Motor Analítico Quantitativo SIM (Determinístico)"
    ai_error = ""

    if settings.get("ai_api_key"):
        try:
            prompt = (
                "Compare objetivamente os ativos abaixo usando EXCLUSIVAMENTE as métricas fornecidas. "
                "NÃO invente indicadores nem emita ordens de compra ou venda.\n\n"
                f"ATIVOS COMPARADOS (JSON):\n{json.dumps(comparison_items, ensure_ascii=False)}\n\n"
                "Retorne estritamente um objeto JSON com as chaves:\n"
                '- "summary": string (síntese comparativa de 3 a 4 frases)\n'
                '- "highlights_by_asset": lista de strings (1 destaque factual por ativo comparado)\n'
                '- "risks_and_counterarguments": lista de 2 a 4 strings com riscos e limitações da comparação.'
            )
            llm_resp = call_configured_llm(prompt, json_mode=True, user_id=user_id)
            if llm_resp:
                parsed = json.loads(_clean_json_markdown(llm_resp))
                if parsed.get("summary"):
                    summary_text = str(parsed["summary"])
                    if isinstance(parsed.get("highlights_by_asset"), list) and parsed["highlights_by_asset"]:
                        highlights_by_asset = [str(x) for x in parsed["highlights_by_asset"][:5]]
                    if isinstance(parsed.get("risks_and_counterarguments"), list) and parsed["risks_and_counterarguments"]:
                        risks_and_counterarguments = [str(x) for x in parsed["risks_and_counterarguments"][:5]]
                    ai_generated = True
                    ai_provider_used = f"{settings.get('ai_provider')} · {settings.get('ai_model')}"
        except Exception as exc:
            ai_error = _sanitize_error_message(str(exc), settings.get("ai_api_key", ""))
            warnings.append(f"Falha ao consultar API de IA ({ai_error}); exibindo comparação determinística do SIM.")
    else:
        warnings.append("Chave de API de IA não configurada; comparação gerada pelo motor analítico local do SIM.")

    target_key = "_VS_".join(x["ticker"] for x in comparison_items)
    prev_record = _get_latest_saved_analysis(user_id=user_id, analysis_type="COMPARISON", target_key=target_key)
    flat_facts = {f"{x['ticker']}_price": x["last_price"] for x in comparison_items}
    delta_since_last = _compute_facts_delta(prev_record, flat_facts, {})

    result_payload = {
        "analysis_type": "COMPARISON",
        "target_key": target_key,
        "tickers": [x["ticker"] for x in comparison_items],
        "period": period.upper(),
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "prompt_version": PROMPT_VERSION,
        "ai_generated": ai_generated,
        "ai_provider_used": ai_provider_used,
        "ai_error": ai_error,
        "comparison_table": comparison_items,
        "ai_interpretation": {
            "kind": "INTERPRETACAO_IA",
            "ai_generated": ai_generated,
            "provider_used": ai_provider_used,
            "prompt_version": PROMPT_VERSION,
            "summary": summary_text,
            "highlights_by_asset": highlights_by_asset,
            "risks_and_counterarguments": risks_and_counterarguments,
        },
        "delta_since_last": delta_since_last,
        "data_warnings": warnings,
        "sources": sources,
        "limitations": STANDARD_LIMITATIONS,
    }

    analysis_id = save_analysis_record(
        user_id=user_id,
        analysis_type="COMPARISON",
        target_key=target_key,
        provider=settings.get("ai_provider", "SIM_QUANT") if ai_generated else "SIM_QUANT",
        model=settings.get("ai_model", "sim-quant-v1") if ai_generated else "sim-quant-v1",
        parameters={"tickers": [x["ticker"] for x in comparison_items], "period": period.upper()},
        facts=flat_facts,
        sources=sources,
        warnings=warnings,
        result={
            "summary": summary_text,
            "highlights_by_asset": highlights_by_asset,
            "risks_and_counterarguments": risks_and_counterarguments,
        },
    )
    result_payload["analysis_id"] = analysis_id
    return result_payload

