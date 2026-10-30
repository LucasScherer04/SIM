import os
import re
import json
import time
import urllib.parse
import threading
import logging
from datetime import datetime, date, time as dt_time, timedelta
from typing import Dict, Any, Optional
import requests

from .database import get_conn
from .ai_radar_service import get_raw_settings, generate_portfolio_and_market_radar

logger = logging.getLogger("sim.whatsapp")
_scheduler_running = False
_scheduler_lock = threading.Lock()
_dispatch_lock = threading.Lock()
_last_scheduler_error_ts: float = 0.0


def _clean_phone_number(raw_phone: str) -> str:
    """Cleans phone numbers into international format without '+', spaces, or hyphens (e.g., 5547999998888)."""
    digits = re.sub(r"\D", "", raw_phone or "")
    if len(digits) in (10, 11) and not digits.startswith("55"):
        digits = "55" + digits
    return digits


def get_easter_date(year: int) -> date:
    """Calculates Easter Sunday using the Meeus/Jones/Butcher Gregorian algorithm."""
    a = year % 19
    b = year // 100
    c = year % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = ((h + l - 7 * m + 114) % 31) + 1
    return date(year, month, day)


def get_b3_holidays(year: int) -> Dict[date, str]:
    """
    Returns the dictionary of national and B3 market holidays for the given year.
    Market does not operate on these dates.
    """
    easter = get_easter_date(year)
    holidays: Dict[date, str] = {
        date(year, 1, 1): "Ano Novo (Confraternização Universal)",
        easter - timedelta(days=48): "Carnaval (Segunda-feira)",
        easter - timedelta(days=47): "Carnaval (Terça-feira)",
        easter - timedelta(days=2): "Sexta-feira Santa (Paixão de Cristo)",
        date(year, 4, 21): "Tiradentes",
        date(year, 5, 1): "Dia do Trabalho",
        easter + timedelta(days=60): "Corpus Christi",
        date(year, 9, 7): "Independência do Brasil",
        date(year, 10, 12): "Nossa Senhora Aparecida",
        date(year, 11, 2): "Finados",
        date(year, 11, 15): "Proclamação da República",
        date(year, 11, 20): "Dia Nacional de Zumbi e da Consciência Negra",
        date(year, 12, 24): "Véspera de Natal (sem pregão B3)",
        date(year, 12, 25): "Natal",
        date(year, 12, 31): "Véspera de Ano Novo (sem pregão B3)",
    }
    return holidays


def check_is_b3_trading_day(d: Optional[date] = None) -> tuple[bool, str]:
    """
    Checks if a given date is a B3 trading day.
    Returns (is_trading_day, description_or_reason).
    """
    if d is None:
        d = date.today()
    if d.weekday() == 5:
        return False, "Sábado (fim de semana)"
    if d.weekday() == 6:
        return False, "Domingo (fim de semana)"
    holidays = get_b3_holidays(d.year)
    if d in holidays:
        return False, f"Feriado: {holidays[d]}"
    return True, "Dia útil de negociação B3"


def parse_daily_time(time_str: Optional[str]) -> tuple[int, int]:
    """
    Parses a time string (HH:MM or HH:MM:SS) into (hour, minute).
    Defaults to (18, 30) if invalid or empty.
    """
    if not time_str:
        return 18, 30
    m = re.match(r"^\s*(\d{1,2}):(\d{2})", str(time_str).strip())
    if m:
        h, mn = int(m.group(1)), int(m.group(2))
        if 0 <= h < 24 and 0 <= mn < 60:
            return h, mn
    return 18, 30


def format_daily_whatsapp_message(radar_data: Dict[str, Any]) -> str:
    """
    Formats the daily closing portfolio report and top market opportunities
    into a clean, professional, readable WhatsApp message with emojis and tabular formatting.
    """
    evo = radar_data.get("daily_evolution", {})
    total_brl = evo.get("total_patrimony_brl", 0.0)
    day_brl = evo.get("day_change_brl", 0.0)
    day_pct = evo.get("day_change_pct", 0.0)
    total_prof = evo.get("total_profit_brl", 0.0)
    total_pct = evo.get("total_profit_pct", 0.0)
    monthly_div = evo.get("estimated_monthly_divs_brl", 0.0)
    pos_count = evo.get("positions_count", 0)
    top_g = evo.get("top_gainer")
    top_l = evo.get("top_loser")

    today_str = datetime.now().strftime("%d/%m/%Y")
    day_emoji = "🟢" if day_brl >= 0 else "🔴"
    tot_emoji = "📈" if total_prof >= 0 else "📉"

    lines = [
        "📊 *SIM — RELATÓRIO DIÁRIO DE FECHAMENTO*",
        f"🗓️ _{today_str}_",
        "",
        f"💼 *Patrimônio Total:* R$ {total_brl:,.2f}",
        f"{day_emoji} *Hoje:* {day_pct:+.2f}% (R$ {day_brl:+,.2f})",
        f"{tot_emoji} *Lucro Acumulado:* {total_pct:+.2f}% (R$ {total_prof:+,.2f})",
        f"💰 *Renda Passiva Estimada:* R$ {monthly_div:,.2f}/mês",
        f"📦 *Ativos em Custódia:* {pos_count}",
    ]

    if top_g and top_l and top_g.get("ticker") != top_l.get("ticker"):
        lines.append("")
        lines.append(f"🚀 *Maior Alta:* {top_g['ticker']} ({top_g['change_pct']:+.2f}%)")
        lines.append(f"🔻 *Maior Baixa:* {top_l['ticker']} ({top_l['change_pct']:+.2f}%)")

    briefing = (radar_data.get("executive_briefing") or "").strip()
    if briefing:
        lines.append("")
        lines.append("🤖 *Diagnóstico do Analista IA:*")
        lines.append(briefing)

    # Top Opportunities
    opps = radar_data.get("opportunities", [])
    if opps:
        lines.append("")
        lines.append("🎯 *Top Oportunidades do Radar B3:*")
        for idx, o in enumerate(opps[:3]):
            first_reason = o["reasons"][0] if o.get("reasons") else o.get("opportunity_tag", "")
            lines.append(
                f"{idx + 1}. *{o['ticker']}* (Score {o['score']}/100) — R$ {o['last_price']:.2f} (DY {o['dy_12m']:.1f}%)\n   ↳ _{first_reason}_"
            )

    # Portfolio Alerts if any
    alerts = radar_data.get("portfolio_alerts", [])
    if alerts:
        lines.append("")
        lines.append("⚠️ *Alertas da Carteira:*")
        for a in alerts[:2]:
            lines.append(f"• *{a['ticker']}:* {a['title']}")

    lines.append("")
    lines.append("💡 _Acesse seu painel completo no SIM para ver o Raio-X detalhado._")
    return "\n".join(lines)


def send_whatsapp_message(message_text: str, custom_phone: str = "", user_id: int = 1) -> Dict[str, Any]:
    """
    Sends a WhatsApp message using the configured provider:
      1. CALLMEBOT (100% free, popular for personal alerts: https://www.callmebot.com/blog/free-api-whatsapp-messages/)
      2. EVOLUTION API / Z-API / Generic Webhook
    """
    settings = get_raw_settings(user_id=user_id)
    provider = (settings.get("whatsapp_provider") or "CALLMEBOT").upper().strip()
    phone = _clean_phone_number(custom_phone or settings.get("whatsapp_phone") or "")
    apikey = (settings.get("whatsapp_apikey") or "").strip()
    instance_url = (settings.get("whatsapp_instance_url") or "").strip().rstrip("/")
    instance_id = (settings.get("whatsapp_instance_id") or "").strip()

    if not phone:
        raise ValueError("Número de telefone não informado. Preencha o número com DDD nas configurações.")

    if provider == "CALLMEBOT":
        if not apikey:
            raise ValueError(
                "API Key do CallMeBot não informada. "
                "Para obter gratuitamente: envie 'I allow callmebot to send me messages' no WhatsApp para o número +34 644 65 67 43."
            )
        encoded_text = urllib.parse.quote(message_text)
        url = f"https://api.callmebot.com/whatsapp.php?phone={phone}&text={encoded_text}&apikey={apikey}"
        r = requests.get(url, timeout=12)
        if r.status_code == 200 and ("Message queued" in r.text or "ok" in r.text.lower()):
            return {"status": "ok", "provider": "CALLMEBOT", "phone": phone, "response": r.text[:120]}
        else:
            raise ValueError(f"Falha CallMeBot: {r.text[:180]}")

    elif provider == "EVOLUTION":
        if not instance_url or not apikey:
            raise ValueError("URL da Evolution API ou ApiKey não configuradas.")
        endpoint = f"{instance_url}/message/sendText/{instance_id}"
        headers = {"apikey": apikey, "Content-Type": "application/json"}
        payload = {"number": phone, "text": message_text}
        r = requests.post(endpoint, json=payload, headers=headers, timeout=12)
        if r.status_code in (200, 201):
            return {"status": "ok", "provider": "EVOLUTION", "phone": phone, "response": r.json()}
        else:
            raise ValueError(f"Falha Evolution API ({r.status_code}): {r.text[:180]}")

    elif provider == "ZAPI":
        if not instance_url or not apikey:
            raise ValueError("URL do endpoint ou Token da Z-API não configurados.")
        headers = {"Client-Token": apikey, "Content-Type": "application/json"}
        payload = {"phone": phone, "message": message_text}
        r = requests.post(instance_url, json=payload, headers=headers, timeout=12)
        if r.status_code in (200, 201):
            return {"status": "ok", "provider": "ZAPI", "phone": phone, "response": r.json()}
        else:
            raise ValueError(f"Falha Z-API ({r.status_code}): {r.text[:180]}")

    elif provider == "WEBHOOK":
        if not instance_url:
            raise ValueError("URL do Webhook não configurada.")
        headers = {"Content-Type": "application/json"}
        if apikey:
            headers["Authorization"] = f"Bearer {apikey}"
        payload = {"phone": phone, "message": message_text, "timestamp": datetime.now().isoformat()}
        r = requests.post(instance_url, json=payload, headers=headers, timeout=12)
        if r.status_code in (200, 201, 202):
            return {"status": "ok", "provider": "WEBHOOK", "phone": phone}
        else:
            raise ValueError(f"Falha Webhook ({r.status_code}): {r.text[:180]}")

    raise ValueError(f"Provedor {provider} não suportado.")


def trigger_daily_whatsapp_dispatch(force: bool = False, user_id: int = 1) -> Dict[str, Any]:
    """
    Generates the current AI Portfolio Radar and sends the daily summary to the user's WhatsApp.

    Guards (when force is False):
      - Verifies WhatsApp is enabled in app_settings.
      - Prevents duplicate sending if already sent today (whatsapp_last_daily_sent).
      - Skips weekends (Saturdays and Sundays).
      - Skips national and B3 holidays.

    When force is True:
      - Bypasses duplicate, weekend, and holiday checks (for explicit manual override/testing).

    Updates 'whatsapp_last_daily_sent' in app_settings on successful send.
    """
    with _dispatch_lock:
        settings = get_raw_settings(user_id=user_id)
        now = datetime.now()
        today_str = now.strftime("%Y-%m-%d")

        if not force:
            enabled_val = str(settings.get("whatsapp_enabled", "")).strip().lower()
            if enabled_val not in ("1", "true"):
                logger.info("Envio diário cancelado: WhatsApp está desativado nas configurações.")
                return {
                    "status": "skipped",
                    "reason": "disabled",
                    "detail": "O envio de relatórios via WhatsApp está desativado nas configurações.",
                }

            last_sent = (settings.get("whatsapp_last_daily_sent") or "").strip()
            if last_sent.startswith(today_str):
                logger.info("Envio diário cancelado: relatório já disparado hoje (%s).", last_sent)
                return {
                    "status": "skipped",
                    "reason": "already_sent_today",
                    "last_sent": last_sent,
                    "detail": f"O relatório diário já foi enviado hoje ({last_sent}).",
                }

            is_trading, reason = check_is_b3_trading_day(now.date())
            if not is_trading:
                logger.info("Envio diário cancelado: pregão B3 fechado hoje (%s).", reason)
                return {
                    "status": "skipped",
                    "reason": "market_closed",
                    "detail": f"O mercado B3 está fechado hoje: {reason}.",
                }

        try:
            radar_data = generate_portfolio_and_market_radar(force_refresh=True, user_id=user_id)
        except TypeError:
            radar_data = generate_portfolio_and_market_radar(force_refresh=True)

        msg = format_daily_whatsapp_message(radar_data)

        try:
            result = send_whatsapp_message(msg, user_id=user_id)
        except TypeError:
            result = send_whatsapp_message(msg)

        # Save last daily sent timestamp
        conn = get_conn()
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn.execute(
            """
            INSERT INTO app_settings (user_id, key, value, updated_at) VALUES (?, 'whatsapp_last_daily_sent', ?, ?)
            ON CONFLICT(user_id, key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at
            """,
            (user_id, now_str, now_str),
        )
        conn.commit()
        conn.close()

        return {
            **result,
            "sent_at": now_str,
            "message_preview": msg[:320] + "...",
        }


def check_and_run_whatsapp_daily_scheduler(
    allow_weekends: bool = False,
    allow_holidays: bool = False,
    reference_dt: Optional[datetime] = None,
    user_id: int = 1,
) -> Optional[Dict[str, Any]]:
    """
    Verifica se o horário atual atingiu ou ultrapassou o horário programado de fechamento
    (whatsapp_daily_time, padrão '18:30') e despacha o relatório diário caso ainda
    não tenha sido enviado hoje. Pula finais de semana e feriados B3.
    """
    global _last_scheduler_error_ts
    now = reference_dt or datetime.now()

    # Backoff de 5 minutos caso tenha havido erro de conexão ou API recente
    if reference_dt is None and time.time() - _last_scheduler_error_ts < 300:
        return None

    settings = get_raw_settings(user_id=user_id)
    enabled_val = str(settings.get("whatsapp_enabled", "")).strip().lower()
    if enabled_val not in ("1", "true"):
        return None

    phone = (settings.get("whatsapp_phone") or "").strip()
    if not phone:
        return None

    today_str = now.strftime("%Y-%m-%d")
    last_sent = (settings.get("whatsapp_last_daily_sent") or "").strip()
    if last_sent.startswith(today_str):
        # Já enviado hoje
        return None

    # Mercado B3 fechado aos sábados (5) e domingos (6)
    if not allow_weekends and now.weekday() >= 5:
        return None

    # Mercado B3 fechado em feriados nacionais e B3
    if not allow_holidays:
        is_trading, _ = check_is_b3_trading_day(now.date())
        if not is_trading:
            return None

    target_h, target_m = parse_daily_time(settings.get("whatsapp_daily_time"))
    target_time_obj = dt_time(target_h, target_m)

    if now.time() < target_time_obj:
        return None

    try:
        logger.info(
            "Disparando envio agendado de fechamento via WhatsApp (%02d:%02d, horário atual: %s)...",
            target_h,
            target_m,
            now.strftime("%H:%M:%S"),
        )
        return trigger_daily_whatsapp_dispatch(force=False, user_id=user_id)
    except Exception as exc:
        _last_scheduler_error_ts = time.time()
        logger.error("Falha ao disparar envio diário agendado do WhatsApp: %s", exc, exc_info=True)
        return {"status": "error", "detail": str(exc)}


def get_whatsapp_scheduler_status(reference_dt: Optional[datetime] = None, user_id: int = 1) -> Dict[str, Any]:
    """
    Retorna o status descritivo atual do agendador automático para exibição na UI.
    """
    now = reference_dt or datetime.now()
    settings = get_raw_settings(user_id=user_id)
    enabled = str(settings.get("whatsapp_enabled", "")).strip().lower() in ("1", "true")
    target_h, target_m = parse_daily_time(settings.get("whatsapp_daily_time"))
    target_str = f"{target_h:02d}:{target_m:02d}"
    last_sent = (settings.get("whatsapp_last_daily_sent") or "").strip()
    today_str = now.strftime("%Y-%m-%d")
    already_sent_today = last_sent.startswith(today_str)

    is_trading, market_reason = check_is_b3_trading_day(now.date())

    if not enabled:
        status_text = "Desativado nas configurações"
        state = "disabled"
    elif already_sent_today:
        sent_time = last_sent[11:16] if len(last_sent) >= 16 else last_sent
        status_text = f"Relatório de hoje já enviado às {sent_time}"
        state = "sent_today"
    elif not is_trading:
        status_text = f"Mercado B3 fechado hoje ({market_reason})"
        state = "market_closed"
    elif now.time() >= dt_time(target_h, target_m):
        status_text = f"Horário de disparo atingido ({target_str}) — pronto para envio"
        state = "ready"
    else:
        status_text = f"Agendado para hoje às {target_str} (dia útil B3)"
        state = "scheduled"

    return {
        "enabled": enabled,
        "target_time": target_str,
        "already_sent_today": already_sent_today,
        "last_sent": last_sent,
        "is_trading_day": is_trading,
        "market_reason": market_reason,
        "status_text": status_text,
        "state": state,
    }


def start_whatsapp_scheduler_thread():
    """Inicia a thread em segundo plano do agendador diário do WhatsApp."""
    global _scheduler_running
    with _scheduler_lock:
        if _scheduler_running:
            return
        _scheduler_running = True

    def _loop():
        logger.info(
            "[WhatsApp Scheduler] Agendador diário ativo em segundo plano (verificação a cada 30s; fins de semana e feriados B3 são ignorados)."
        )
        while True:
            try:
                conn = get_conn()
                u_rows = conn.execute("SELECT DISTINCT user_id FROM app_settings WHERE key = 'whatsapp_enabled' AND value IN ('1', 'true')").fetchall()
                conn.close()
                uids = [r["user_id"] for r in u_rows] if u_rows else [1]
                for uid in uids:
                    check_and_run_whatsapp_daily_scheduler(user_id=uid)
            except Exception as e:
                logger.error("[WhatsApp Scheduler] Exceção no ciclo de verificação: %s", e, exc_info=True)
            time.sleep(30)

    t = threading.Thread(target=_loop, name="WhatsAppDailyScheduler", daemon=True)
    t.start()
