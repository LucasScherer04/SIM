"""
Testes do Agendador Automático do Relatório Diário de WhatsApp,
Prevenção de Duplicidades e Calendário de Feriados B3.
"""
from datetime import datetime, date, timedelta
import pytest
from app import database
from app.ai_radar_service import ensure_settings_tables
from app.whatsapp_service import (
    check_and_run_whatsapp_daily_scheduler,
    trigger_daily_whatsapp_dispatch,
    get_whatsapp_scheduler_status,
    check_is_b3_trading_day,
    get_b3_holidays,
    parse_daily_time,
)


def _setup_test_db(tmp_path, monkeypatch):
    test_db = str(tmp_path / "test.db")
    monkeypatch.setattr(database, "DB_PATH", test_db)
    database.init_db()
    ensure_settings_tables()


def test_scheduler_disabled_returns_none(tmp_path, monkeypatch):
    _setup_test_db(tmp_path, monkeypatch)

    # WhatsApp desativado
    res = check_and_run_whatsapp_daily_scheduler(allow_weekends=True, allow_holidays=True)
    assert res is None


def test_scheduler_skips_when_time_not_reached(tmp_path, monkeypatch):
    _setup_test_db(tmp_path, monkeypatch)

    conn = database.get_conn()
    conn.execute("INSERT OR REPLACE INTO app_settings (key, value) VALUES ('whatsapp_enabled', '1')")
    conn.execute("INSERT OR REPLACE INTO app_settings (key, value) VALUES ('whatsapp_phone', '5547999998888')")
    # Agendado para 18:30, mas simulação às 10:00 da manhã
    conn.execute("INSERT OR REPLACE INTO app_settings (key, value) VALUES ('whatsapp_daily_time', '18:30')")
    conn.commit()
    conn.close()

    morning_dt = datetime(2026, 10, 29, 10, 0, 0)
    res = check_and_run_whatsapp_daily_scheduler(
        allow_weekends=True,
        allow_holidays=True,
        reference_dt=morning_dt,
    )
    assert res is None


def test_scheduler_skips_if_already_sent_today(tmp_path, monkeypatch):
    _setup_test_db(tmp_path, monkeypatch)

    sim_dt = datetime(2026, 10, 29, 19, 0, 0)
    today_str = sim_dt.strftime("%Y-%m-%d %H:%M:%S")

    conn = database.get_conn()
    conn.execute("INSERT OR REPLACE INTO app_settings (key, value) VALUES ('whatsapp_enabled', '1')")
    conn.execute("INSERT OR REPLACE INTO app_settings (key, value) VALUES ('whatsapp_phone', '5547999998888')")
    conn.execute("INSERT OR REPLACE INTO app_settings (key, value) VALUES ('whatsapp_daily_time', '18:30')")
    conn.execute("INSERT OR REPLACE INTO app_settings (key, value) VALUES ('whatsapp_last_daily_sent', ?)", (today_str,))
    conn.commit()
    conn.close()

    res = check_and_run_whatsapp_daily_scheduler(
        allow_weekends=True,
        allow_holidays=True,
        reference_dt=sim_dt,
    )
    assert res is None


def test_scheduler_skips_on_weekends(tmp_path, monkeypatch):
    _setup_test_db(tmp_path, monkeypatch)

    conn = database.get_conn()
    conn.execute("INSERT OR REPLACE INTO app_settings (key, value) VALUES ('whatsapp_enabled', '1')")
    conn.execute("INSERT OR REPLACE INTO app_settings (key, value) VALUES ('whatsapp_phone', '5547999998888')")
    conn.execute("INSERT OR REPLACE INTO app_settings (key, value) VALUES ('whatsapp_daily_time', '18:30')")
    conn.commit()
    conn.close()

    # 2026-10-31 é Sábado
    saturday_dt = datetime(2026, 10, 31, 18, 45, 0)
    res_sat = check_and_run_whatsapp_daily_scheduler(allow_weekends=False, reference_dt=saturday_dt)
    assert res_sat is None

    # 2026-11-01 é Domingo
    sunday_dt = datetime(2026, 11, 1, 18, 45, 0)
    res_sun = check_and_run_whatsapp_daily_scheduler(allow_weekends=False, reference_dt=sunday_dt)
    assert res_sun is None


def test_scheduler_skips_on_b3_holidays(tmp_path, monkeypatch):
    _setup_test_db(tmp_path, monkeypatch)

    conn = database.get_conn()
    conn.execute("INSERT OR REPLACE INTO app_settings (key, value) VALUES ('whatsapp_enabled', '1')")
    conn.execute("INSERT OR REPLACE INTO app_settings (key, value) VALUES ('whatsapp_phone', '5547999998888')")
    conn.execute("INSERT OR REPLACE INTO app_settings (key, value) VALUES ('whatsapp_daily_time', '18:30')")
    conn.commit()
    conn.close()

    # 2026-11-02 é Finados (Segunda-feira, feriado B3)
    finados_dt = datetime(2026, 11, 2, 19, 0, 0)
    res = check_and_run_whatsapp_daily_scheduler(
        allow_weekends=False,
        allow_holidays=False,
        reference_dt=finados_dt,
    )
    assert res is None


def test_scheduler_runs_when_time_arrived_on_trading_day(tmp_path, monkeypatch):
    _setup_test_db(tmp_path, monkeypatch)

    conn = database.get_conn()
    conn.execute("INSERT OR REPLACE INTO app_settings (key, value) VALUES ('whatsapp_enabled', '1')")
    conn.execute("INSERT OR REPLACE INTO app_settings (key, value) VALUES ('whatsapp_phone', '5547999998888')")
    conn.execute("INSERT OR REPLACE INTO app_settings (key, value) VALUES ('whatsapp_daily_time', '18:30')")
    conn.execute("INSERT OR REPLACE INTO app_settings (key, value) VALUES ('whatsapp_last_daily_sent', '')")
    conn.commit()
    conn.close()

    # Mock de envio do WhatsApp e Radar para não precisar de API externa
    from app import whatsapp_service
    sent_messages = []
    monkeypatch.setattr(
        whatsapp_service,
        "generate_portfolio_and_market_radar",
        lambda force_refresh=True: {"daily_evolution": {"total_patrimony_brl": 100000.0, "day_change_brl": 500.0}},
    )
    monkeypatch.setattr(
        whatsapp_service,
        "send_whatsapp_message",
        lambda msg, custom_phone="": sent_messages.append(msg) or {"status": "ok", "provider": "TEST"},
    )

    # 2026-10-29 é Quinta-feira (dia útil normal) às 18:35
    thursday_dt = datetime(2026, 10, 29, 18, 35, 0)
    res = check_and_run_whatsapp_daily_scheduler(
        allow_weekends=False,
        allow_holidays=False,
        reference_dt=thursday_dt,
    )

    assert res is not None
    assert res.get("status") == "ok"
    assert len(sent_messages) == 1

    # Verifica se gravou 'whatsapp_last_daily_sent' no banco de dados
    conn = database.get_conn()
    row = conn.execute("SELECT value FROM app_settings WHERE key = 'whatsapp_last_daily_sent'").fetchone()
    conn.close()
    assert row is not None
    assert row["value"].startswith(datetime.now().strftime("%Y-%m-%d"))


def test_trigger_daily_whatsapp_dispatch_duplicate_prevention(tmp_path, monkeypatch):
    _setup_test_db(tmp_path, monkeypatch)

    today_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = database.get_conn()
    conn.execute("INSERT OR REPLACE INTO app_settings (key, value) VALUES ('whatsapp_enabled', '1')")
    conn.execute("INSERT OR REPLACE INTO app_settings (key, value) VALUES ('whatsapp_phone', '5547999998888')")
    conn.execute("INSERT OR REPLACE INTO app_settings (key, value) VALUES ('whatsapp_last_daily_sent', ?)", (today_str,))
    conn.commit()
    conn.close()

    from app import whatsapp_service
    monkeypatch.setattr(whatsapp_service, "check_is_b3_trading_day", lambda d=None: (True, "Dia útil"))

    # force=False deve impedir envio duplicado no mesmo dia
    res = trigger_daily_whatsapp_dispatch(force=False)
    assert res.get("status") == "skipped"
    assert res.get("reason") == "already_sent_today"

    # force=True deve contornar o bloqueio de duplicidade
    sent_count = [0]
    monkeypatch.setattr(
        whatsapp_service,
        "generate_portfolio_and_market_radar",
        lambda force_refresh=True: {"daily_evolution": {}},
    )
    monkeypatch.setattr(
        whatsapp_service,
        "send_whatsapp_message",
        lambda msg, custom_phone="": sent_count.__setitem__(0, sent_count[0] + 1) or {"status": "ok"},
    )

    res_forced = trigger_daily_whatsapp_dispatch(force=True)
    assert res_forced.get("status") == "ok"
    assert sent_count[0] == 1


def test_trigger_daily_whatsapp_dispatch_skips_when_market_closed(tmp_path, monkeypatch):
    _setup_test_db(tmp_path, monkeypatch)

    conn = database.get_conn()
    conn.execute("INSERT OR REPLACE INTO app_settings (key, value) VALUES ('whatsapp_enabled', '1')")
    conn.execute("INSERT OR REPLACE INTO app_settings (key, value) VALUES ('whatsapp_phone', '5547999998888')")
    conn.execute("INSERT OR REPLACE INTO app_settings (key, value) VALUES ('whatsapp_last_daily_sent', '')")
    conn.commit()
    conn.close()

    from app import whatsapp_service
    # Simula mercado fechado (ex: feriado ou fim de semana)
    monkeypatch.setattr(whatsapp_service, "check_is_b3_trading_day", lambda d=None: (False, "Feriado: Natal"))

    res = trigger_daily_whatsapp_dispatch(force=False)
    assert res.get("status") == "skipped"
    assert res.get("reason") == "market_closed"
    assert "Natal" in res.get("detail", "")


def test_parse_daily_time():
    assert parse_daily_time("18:30") == (18, 30)
    assert parse_daily_time("18:30:00") == (18, 30)
    assert parse_daily_time("9:15") == (9, 15)
    assert parse_daily_time("09:15") == (9, 15)
    assert parse_daily_time(" 20:45 ") == (20, 45)
    assert parse_daily_time("") == (18, 30)
    assert parse_daily_time(None) == (18, 30)
    assert parse_daily_time("invalido") == (18, 30)


def test_b3_holidays_calendar():
    # 2026
    h2026 = get_b3_holidays(2026)
    assert date(2026, 1, 1) in h2026  # Ano Novo
    assert date(2026, 2, 16) in h2026  # Carnaval Seg
    assert date(2026, 2, 17) in h2026  # Carnaval Ter
    assert date(2026, 4, 3) in h2026  # Sexta-feira Santa
    assert date(2026, 4, 21) in h2026  # Tiradentes
    assert date(2026, 5, 1) in h2026  # Trabalho
    assert date(2026, 6, 4) in h2026  # Corpus Christi
    assert date(2026, 9, 7) in h2026  # Independência
    assert date(2026, 10, 12) in h2026  # N. Sra Aparecida
    assert date(2026, 11, 2) in h2026  # Finados
    assert date(2026, 11, 15) in h2026  # Proclamação da República
    assert date(2026, 11, 20) in h2026  # Consciência Negra
    assert date(2026, 12, 24) in h2026  # Véspera Natal
    assert date(2026, 12, 25) in h2026  # Natal
    assert date(2026, 12, 31) in h2026  # Véspera Ano Novo


def test_whatsapp_scheduler_status(tmp_path, monkeypatch):
    _setup_test_db(tmp_path, monkeypatch)

    conn = database.get_conn()
    conn.execute("INSERT OR REPLACE INTO app_settings (key, value) VALUES ('whatsapp_enabled', '1')")
    conn.execute("INSERT OR REPLACE INTO app_settings (key, value) VALUES ('whatsapp_daily_time', '18:30')")
    conn.commit()
    conn.close()

    # 1. Dia útil antes das 18:30
    st1 = get_whatsapp_scheduler_status(reference_dt=datetime(2026, 10, 29, 14, 0, 0))
    assert st1["state"] == "scheduled"
    assert "18:30" in st1["status_text"]

    # 2. Fim de semana
    st2 = get_whatsapp_scheduler_status(reference_dt=datetime(2026, 10, 31, 18, 30, 0))
    assert st2["state"] == "market_closed"

    # 3. Já enviado hoje
    conn = database.get_conn()
    conn.execute("INSERT OR REPLACE INTO app_settings (key, value) VALUES ('whatsapp_last_daily_sent', '2026-10-29 18:30:12')")
    conn.commit()
    conn.close()
    st3 = get_whatsapp_scheduler_status(reference_dt=datetime(2026, 10, 29, 19, 0, 0))
    assert st3["state"] == "sent_today"
    assert "18:30" in st3["status_text"]


def test_api_whatsapp_dispatch_endpoint(tmp_path, monkeypatch):
    _setup_test_db(tmp_path, monkeypatch)

    from fastapi.testclient import TestClient
    from app.main import app
    from app import whatsapp_service

    client = TestClient(app)

    # 1. Test status endpoint
    res_status = client.get("/api/whatsapp/status")
    assert res_status.status_code == 200
    assert "enabled" in res_status.json()

    # 2. Test dispatch when disabled
    res_dis_disabled = client.post("/api/whatsapp/dispatch-daily")
    assert res_dis_disabled.status_code == 200
    assert res_dis_disabled.json().get("status") == "skipped"

    # 3. Enable whatsapp, set already sent today
    today_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = database.get_conn()
    conn.execute("INSERT OR REPLACE INTO app_settings (key, value) VALUES ('whatsapp_enabled', '1')")
    conn.execute("INSERT OR REPLACE INTO app_settings (key, value) VALUES ('whatsapp_phone', '5547999998888')")
    conn.execute("INSERT OR REPLACE INTO app_settings (key, value) VALUES ('whatsapp_last_daily_sent', ?)", (today_str,))
    conn.commit()
    conn.close()

    # POST without force skips duplicate
    res_dis_skip = client.post("/api/whatsapp/dispatch-daily")
    assert res_dis_skip.status_code == 200
    assert res_dis_skip.json().get("status") == "skipped"
    assert res_dis_skip.json().get("reason") == "already_sent_today"

    # POST with force=true forces dispatch
    sent = []
    monkeypatch.setattr(
        whatsapp_service,
        "generate_portfolio_and_market_radar",
        lambda force_refresh=True: {"daily_evolution": {}},
    )
    monkeypatch.setattr(
        whatsapp_service,
        "send_whatsapp_message",
        lambda msg, custom_phone="": sent.append(msg) or {"status": "ok", "provider": "TEST"},
    )
    res_dis_force = client.post("/api/whatsapp/dispatch-daily?force=true")
    assert res_dis_force.status_code == 200
    assert res_dis_force.json().get("status") == "ok"
    assert len(sent) == 1
