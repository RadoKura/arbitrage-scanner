from __future__ import annotations

import os
from typing import Any

import requests


def _fmt_money(amount: Any) -> str:
    try:
        return f"{float(amount):.2f}"
    except (TypeError, ValueError):
        return "0.00"


def send_arb_alert(
    opportunity: dict[str, Any],
    bot_token: str | None = None,
    chat_id: str | None = None,
) -> bool:
    """Send a single arbitrage alert to Telegram."""
    token = (bot_token or os.environ.get("TELEGRAM_BOT_TOKEN", "")).strip()
    chat = (chat_id or os.environ.get("TELEGRAM_CHAT_ID", "")).strip()
    print(
        "[telegram] config loaded: "
        f"TELEGRAM_BOT_TOKEN={'yes' if bool(token) else 'no'}, "
        f"TELEGRAM_CHAT_ID={'yes' if bool(chat) else 'no'}",
        flush=True,
    )
    if not token or not chat:
        print("[telegram] skip send: missing token or chat_id", flush=True)
        return False

    match_name = opportunity.get("match") or "N/A"
    profit = float(opportunity.get("profit_percent") or 0.0)

    line_1 = (
        f"1️⃣ {opportunity.get('book_1', 'N/A')} — "
        f"{opportunity.get('odd_1', 'N/A')} (€{_fmt_money(opportunity.get('stake_1_eur'))})"
    )
    line_x = (
        f"❌ {opportunity.get('book_x', 'N/A')} — "
        f"{opportunity.get('odd_x', 'N/A')} (€{_fmt_money(opportunity.get('stake_x_eur'))})"
    )
    line_2 = (
        f"2️⃣ {opportunity.get('book_2', 'N/A')} — "
        f"{opportunity.get('odd_2', 'N/A')} (€{_fmt_money(opportunity.get('stake_2_eur'))})"
    )

    text = (
        "🔥 Арбитраж намерен!\n"
        f"Мач: {match_name}\n"
        f"Печалба: {profit:.2f}%\n\n"
        f"{line_1}\n"
        f"{line_x}\n"
        f"{line_2}\n"
        "Общо: €100"
    )

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat, "text": text}
    try:
        resp = requests.post(url, json=payload, timeout=20)
        print(
            f"[telegram] API response: status={resp.status_code}, body={resp.text[:1000]}",
            flush=True,
        )
        return resp.ok
    except requests.RequestException as exc:
        print(f"[telegram] request exception: {exc}", flush=True)
        return False
