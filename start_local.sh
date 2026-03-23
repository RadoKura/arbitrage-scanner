#!/usr/bin/env bash
# Стартира локалния scraper API на :5001 и ngrok тунел (Mac).
# Първо: ngrok config add-authtoken <token> (от https://dashboard.ngrok.com )
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

if [[ -d .venv ]]; then
  # shellcheck source=/dev/null
  source .venv/bin/activate
fi

if ! command -v ngrok &>/dev/null; then
  echo "ngrok не е в PATH. Инсталация с Homebrew…"
  if command -v brew &>/dev/null; then
    brew install ngrok/ngrok/ngrok 2>/dev/null || brew install ngrok
  else
    echo "Инсталирай ngrok: https://ngrok.com/download или brew install ngrok/ngrok/ngrok"
    exit 1
  fi
fi

python3 local_scraper_api.py &
API_PID=$!

NGROK_PID=""

cleanup() {
  kill "$API_PID" 2>/dev/null || true
  if [[ -n "${NGROK_PID:-}" ]]; then
    kill "$NGROK_PID" 2>/dev/null || true
  fi
}
trap cleanup EXIT INT TERM

sleep 1

ngrok http 5001 --log=stdout >/tmp/ngrok-arbitrage-scanner.log 2>&1 &
NGROK_PID=$!

PUBLIC_URL=""
for _ in $(seq 1 60); do
  if PUBLIC_URL="$(
    curl -fsS http://127.0.0.1:4040/api/tunnels 2>/dev/null | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    for t in d.get('tunnels') or []:
        u = (t.get('public_url') or '')
        if u.startswith('https://'):
            print(u)
            break
    else:
        ts = d.get('tunnels') or []
        if ts:
            print(ts[0].get('public_url') or '')
except Exception:
    pass
" 2>/dev/null
  )" && [[ -n "$PUBLIC_URL" ]]; then
    break
  fi
  sleep 0.5
done

echo ""
echo "Local scraper API: http://127.0.0.1:5001/scrape"
if [[ -n "$PUBLIC_URL" ]]; then
  echo "ngrok public URL:  ${PUBLIC_URL}/scrape"
  echo "Задай на Railway:   SCRAPER_URL=${PUBLIC_URL}/scrape"
else
  echo "Не успях да прочета ngrok URL (4040). Провери authtoken: ngrok config add-authtoken …"
  echo "Лог: /tmp/ngrok-arbitrage-scanner.log"
fi
echo ""
echo "Ctrl+C спира API и ngrok."
echo ""

wait
