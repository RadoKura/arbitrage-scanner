"""
Локален API за скрейпъри: слуша само на 127.0.0.1 (достъп от Mac + ngrok тунел).

Старт: python local_scraper_api.py
Или: ./start_local.sh (с ngrok).
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, jsonify

from main import run_scan
from notifications.telegram import send_arb_alert

load_dotenv()

app = Flask(__name__)
DATA_DIR = Path(__file__).resolve().parent / "data"
HISTORY_PATH = DATA_DIR / "history.json"


def _load_history_rows() -> list[dict]:
    try:
        if not HISTORY_PATH.exists():
            return []
        raw = json.loads(HISTORY_PATH.read_text(encoding="utf-8"))
        return raw if isinstance(raw, list) else []
    except Exception:
        return []


def _save_history_rows(rows: list[dict]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    HISTORY_PATH.write_text(
        json.dumps(rows, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _append_opportunities_to_history(opportunities: list[dict]) -> int:
    timestamp = datetime.now(timezone.utc).isoformat()
    history_rows = _load_history_rows()
    for opp in opportunities:
        row = {"timestamp": timestamp, **opp}
        history_rows.append(row)
    _save_history_rows(history_rows)
    return len(opportunities)


@app.route("/scrape")
def scrape():
    try:
        data = run_scan()
        added = _append_opportunities_to_history(data.get("opportunities") or [])
        print(f"[local-scrape] history appended: {added}", flush=True)
        for bid, n in sorted((data.get("book_match_counts") or {}).items()):
            print(f"[local-scrape] scraper {bid}: {n} matches", flush=True)
        bot_token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
        chat_id = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
        print(
            "[local-scrape] telegram configured: "
            f"token={'yes' if bool(bot_token) else 'no'}, "
            f"chat_id={'yes' if bool(chat_id) else 'no'}",
            flush=True,
        )
        if bot_token and chat_id:
            alerts_total = 0
            alerts_sent = 0
            for opp in data.get("opportunities") or []:
                try:
                    profit = float(opp.get("profit_percent") or 0.0)
                except (TypeError, ValueError):
                    profit = 0.0
                if profit < 2.0:
                    continue
                alerts_total += 1
                sent = send_arb_alert(opp, bot_token, chat_id)
                if sent:
                    alerts_sent += 1
                print(
                    f"[local-scrape] telegram alert ({opp.get('match', 'N/A')}): {'ok' if sent else 'failed'}",
                    flush=True,
                )
            print(
                f"[local-scrape] telegram summary: sent {alerts_sent}/{alerts_total} alerts (profit >= 2.0%)",
                flush=True,
            )
        else:
            print(
                "[local-scrape] telegram skipped: missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID",
                flush=True,
            )
        return jsonify({"ok": True, **data}), 200
    except Exception as exc:  # noqa: BLE001
        return (
            jsonify(
                {
                    "ok": False,
                    "error": str(exc),
                    "opportunities": [],
                }
            ),
            500,
        )


@app.route("/history", methods=["GET"])
def history():
    rows = _load_history_rows()
    latest = rows[-100:]
    latest.reverse()
    return jsonify({"ok": True, "history": latest, "count": len(latest)}), 200


@app.route("/history/clear", methods=["POST"])
def history_clear():
    _save_history_rows([])
    return jsonify({"ok": True}), 200


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5001, debug=False, threaded=True)
