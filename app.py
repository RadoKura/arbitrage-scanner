"""
Уеб интерфейс за 1X2 арбитражен скенер (efbet, Winbet, Betano, Palms Bet).
"""

from __future__ import annotations

import os

import requests
from dotenv import load_dotenv
from flask import Flask, Response, jsonify

load_dotenv()

app = Flask(__name__)


def _scraper_scan_url() -> str:
    return os.environ.get("SCRAPER_URL", "http://127.0.0.1:5001/scrape")


def _scraper_history_url() -> str:
    scan_url = _scraper_scan_url().rstrip("/")
    if scan_url.endswith("/scrape"):
        return scan_url[: -len("/scrape")] + "/history"
    return scan_url + "/history"


def _scraper_history_clear_url() -> str:
    return _scraper_history_url().rstrip("/") + "/clear"


def _do_scan():
    scraper_url = _scraper_scan_url()
    try:
        response = requests.get(scraper_url, timeout=120)
        data = response.json()
    except requests.RequestException as exc:
        return (
            jsonify(
                {
                    "ok": False,
                    "error": f"SCRAPER_URL request failed: {exc}",
                    "opportunities": [],
                }
            ),
            502,
        )
    except ValueError:
        return (
            jsonify(
                {
                    "ok": False,
                    "error": "SCRAPER_URL returned invalid JSON",
                    "opportunities": [],
                }
            ),
            502,
        )

    if response.status_code != 200:
        if isinstance(data, dict):
            return jsonify(data), 502
        err = response.text[:500]
        return (
            jsonify(
                {
                    "ok": False,
                    "error": f"scraper HTTP {response.status_code}: {err}",
                    "opportunities": [],
                }
            ),
            502,
        )

    if not isinstance(data, dict):
        return (
            jsonify(
                {
                    "ok": False,
                    "error": "scraper returned non-object JSON",
                    "opportunities": [],
                }
            ),
            502,
        )

    for bid, n in sorted((data.get("book_match_counts") or {}).items()):
        print(f"[scan] scraper {bid}: {n} matches", flush=True)

    status = 200 if data.get("ok") else 500
    return jsonify(data), status


def _do_history():
    history_url = _scraper_history_url()
    try:
        response = requests.get(history_url, timeout=30)
        data = response.json()
    except requests.RequestException as exc:
        return jsonify({"ok": False, "error": f"HISTORY request failed: {exc}", "history": []}), 502
    except ValueError:
        return jsonify({"ok": False, "error": "HISTORY returned invalid JSON", "history": []}), 502
    if response.status_code != 200:
        if isinstance(data, dict):
            return jsonify(data), 502
        return jsonify({"ok": False, "error": "HISTORY upstream error", "history": []}), 502
    return jsonify(data), 200


def _do_history_clear():
    clear_url = _scraper_history_clear_url()
    try:
        response = requests.post(clear_url, timeout=20)
        data = response.json()
    except requests.RequestException as exc:
        return jsonify({"ok": False, "error": f"HISTORY clear failed: {exc}"}), 502
    except ValueError:
        return jsonify({"ok": False, "error": "HISTORY clear returned invalid JSON"}), 502
    if response.status_code != 200:
        if isinstance(data, dict):
            return jsonify(data), 502
        return jsonify({"ok": False, "error": "HISTORY clear upstream error"}), 502
    return jsonify(data), 200


@app.route("/")
def index():
    html = """<!DOCTYPE html>
<html lang="bg">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Арбитражен скенер</title>
  <style>
    :root {
      --bg: #0f1117;
      --surface: #161b26;
      --border: #2a3142;
      --text: #e6e9ef;
      --muted: #8b93a7;
      --accent: #3b82f6;
      --green: #22c55e;
      --yellow: #eab308;
      --dim: #64748b;
    }
    * { box-sizing: border-box; }
    body {
      font-family: ui-sans-serif, system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
      margin: 0;
      padding: 1.25rem 1rem 2rem;
      background: var(--bg);
      color: var(--text);
      line-height: 1.5;
    }
    main { max-width: 1200px; margin: 0 auto; }
    h1.app-title-link {
      font-size: 1.35rem;
      font-weight: 600;
      margin: 0 0 0.35rem;
      letter-spacing: -0.02em;
      cursor: pointer;
      width: fit-content;
      color: var(--text);
      border-bottom: 1px solid transparent;
      transition: color 0.15s, border-color 0.15s;
    }
    h1.app-title-link:hover {
      color: var(--accent);
      border-bottom-color: var(--accent);
    }
    p.meta { margin: 0 0 1rem; color: var(--muted); font-size: 0.9rem; max-width: 52rem; }
    .toolbar { display: flex; flex-wrap: wrap; gap: 0.65rem 0.75rem; align-items: center; margin-bottom: 0.75rem; }
    .thresh {
      display: inline-flex;
      align-items: center;
      gap: 0.35rem;
      font-size: 0.78rem;
      color: var(--muted);
    }
    .thresh input {
      width: 3.25rem;
      padding: 0.28rem 0.35rem;
      border-radius: 6px;
      border: 1px solid var(--border);
      background: var(--surface);
      color: var(--text);
      font: inherit;
    }
    button {
      font: inherit;
      padding: 0.5rem 1rem;
      background: linear-gradient(180deg, #2563eb, #1d4ed8);
      color: #fff;
      border: 1px solid #1e40af;
      border-radius: 8px;
      cursor: pointer;
      font-weight: 500;
    }
    button:hover { filter: brightness(1.06); }
    button:disabled { opacity: 0.45; cursor: not-allowed; filter: none; }
    button.btn-secondary {
      background: #374151;
      border-color: #4b5563;
      padding: 0.45rem 0.75rem;
      font-size: 0.82rem;
    }
    button.btn-secondary:hover { filter: brightness(1.08); }
    button.btn-csv {
      background: linear-gradient(180deg, #15803d, #166534);
      border-color: #14532d;
    }
    button.btn-csv:hover { filter: brightness(1.06); }
    .badge {
      font-size: 0.75rem;
      color: var(--muted);
      padding: 0.25rem 0.5rem;
      background: var(--surface);
      border-radius: 6px;
      border: 1px solid var(--border);
    }
    .status { margin: 0.75rem 0; min-height: 1.25rem; font-size: 0.88rem; color: var(--muted); }
    .status.err { color: #f87171; }
    .wrap { overflow-x: auto; border-radius: 10px; border: 1px solid var(--border); background: var(--surface); }
    table {
      width: 100%;
      border-collapse: collapse;
      font-size: 0.82rem;
    }
    th, td {
      text-align: left;
      padding: 0.6rem 0.65rem;
      border-bottom: 1px solid var(--border);
      vertical-align: top;
    }
    th {
      background: #1a1f2e;
      color: var(--muted);
      font-weight: 600;
      text-transform: uppercase;
      font-size: 0.7rem;
      letter-spacing: 0.04em;
    }
    tr:last-child td { border-bottom: none; }
    td.num { text-align: right; white-space: nowrap; font-variant-numeric: tabular-nums; }
    td.plan { max-width: 22rem; font-size: 0.78rem; color: #cbd5e1; line-height: 1.4; }
    tr.tier-hot td:first-child { box-shadow: inset 3px 0 0 0 #f97316; }
    tr.tier-warm td:first-child { box-shadow: inset 3px 0 0 0 var(--yellow); }
    tr.tier-high td:first-child { box-shadow: inset 3px 0 0 0 var(--green); }
    tr.tier-mid td:first-child { box-shadow: inset 3px 0 0 0 var(--yellow); }
    tr.tier-low td:first-child { box-shadow: inset 3px 0 0 0 var(--dim); }
    tr.tier-hot .pct { color: #fb923c; font-weight: 700; }
    tr.tier-warm .pct { color: var(--yellow); font-weight: 600; }
    tr.tier-high .pct { color: var(--green); font-weight: 600; }
    tr.tier-mid .pct { color: var(--yellow); font-weight: 600; }
    tr.tier-low .pct { color: var(--dim); font-weight: 500; }
    .table-foot {
      margin: 0.65rem 0 0;
      font-size: 0.78rem;
      color: var(--dim);
    }
    .empty {
      padding: 1.25rem;
      color: var(--muted);
      text-align: center;
    }
    .matches-covered-section {
      margin-top: 1.35rem;
      border: 1px solid var(--border);
      border-radius: 10px;
      padding: 0.75rem 0.9rem;
      background: var(--surface);
    }
    .matches-covered-head {
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      gap: 0.5rem 0.75rem;
      margin-bottom: 0;
    }
    .matches-covered-head h2 {
      margin: 0;
      font-size: 1rem;
      font-weight: 600;
      color: var(--text);
    }
    .matches-covered-panel[hidden] { display: none !important; }
    .matches-covered-panel { margin-top: 0.75rem; }
    td.odds-cell { font-variant-numeric: tabular-nums; font-size: 0.78rem; line-height: 1.35; }
    td.odds-cell .sub { font-size: 0.68rem; color: var(--muted); margin-bottom: 0.2rem; max-width: 12rem; }
    td.muted-cell { color: var(--dim); }
    .calc-section {
      margin-top: 1.35rem;
      border: 1px solid var(--border);
      border-radius: 10px;
      padding: 0.85rem 0.9rem;
      background: var(--surface);
    }
    .calc-head {
      display: flex;
      flex-wrap: wrap;
      gap: 0.5rem 0.75rem;
      align-items: center;
      margin-bottom: 0.75rem;
    }
    .calc-head h2 {
      margin: 0;
      font-size: 1rem;
      font-weight: 600;
      color: var(--text);
    }
    .calc-total {
      display: inline-flex;
      align-items: center;
      gap: 0.35rem;
      font-size: 0.82rem;
      color: var(--muted);
    }
    .calc-total input {
      width: 6rem;
      padding: 0.35rem 0.45rem;
      border-radius: 6px;
      border: 1px solid var(--border);
      background: var(--bg);
      color: var(--text);
      font: inherit;
    }
    .calc-sub {
      margin: 0 0 0.7rem;
      font-size: 0.78rem;
      color: var(--muted);
    }
    .history-section {
      margin-top: 1.35rem;
      border: 1px solid var(--border);
      border-radius: 10px;
      padding: 0.85rem 0.9rem;
      background: var(--surface);
    }
    .history-head {
      display: flex;
      flex-wrap: wrap;
      gap: 0.5rem 0.75rem;
      align-items: center;
      justify-content: space-between;
      margin-bottom: 0.75rem;
    }
    .history-head h2 {
      margin: 0;
      font-size: 1rem;
      font-weight: 600;
      color: var(--text);
    }
    .history-actions {
      display: inline-flex;
      gap: 0.5rem;
    }
    @media (max-width: 768px) {
      body {
        padding: 1rem 0.7rem 1.5rem;
      }
      .toolbar {
        gap: 0.55rem;
      }
      .toolbar > button,
      .toolbar > .badge {
        width: 100%;
      }
      .toolbar > button {
        padding: 0.65rem 0.8rem;
      }
      .toolbar > .thresh {
        width: calc(50% - 0.3rem);
        justify-content: space-between;
      }
      .toolbar > .thresh input {
        width: 4rem;
      }
      .wrap {
        overflow-x: auto;
        -webkit-overflow-scrolling: touch;
      }
      table {
        min-width: 760px;
      }
      .matches-covered-section .wrap table {
        min-width: 860px;
      }
      .calc-head {
        flex-direction: column;
        align-items: stretch;
      }
      .calc-total {
        justify-content: space-between;
        width: 100%;
      }
      .calc-total input {
        width: 7rem;
      }
      .calc-head .btn-secondary {
        width: 100%;
      }
      .calc-section .wrap table {
        min-width: 880px;
      }
      .history-head {
        flex-direction: column;
        align-items: stretch;
      }
      .history-actions {
        width: 100%;
      }
      .history-actions button {
        width: 100%;
      }
      .history-section .wrap table {
        min-width: 760px;
      }
    }
    @media (max-width: 480px) {
      .toolbar > .thresh {
        width: 100%;
      }
    }
  </style>
</head>
<body>
  <main>
    <h1 class="app-title-link" id="appTitle" tabindex="0" title="Обнови страницата" role="link">Арбитражен скенер (1X2)</h1>
    <p class="meta">
      Четири букмейкъра (efbet, Winbet, Betano, Palms Bet). Сканирането стартира автоматично на всеки <strong>5 минути</strong>.
      Едно пълно сканиране може да отнеме няколко минути.
    </p>
    <div class="toolbar">
      <button type="button" id="btn">Сканирай сега</button>
      <label class="thresh" title="Минимален процент печалба за показване в таблицата">
        <span>Мин. праг %:</span>
        <input type="number" id="minPct" step="0.1" min="0" value="1.5" />
      </label>
      <label class="thresh" title="Над този праг редът е „горещ“ и се показва най-отгоре">
        <span>Горещ праг %:</span>
        <input type="number" id="hotPct" step="0.1" min="0" value="3" />
      </label>
      <button type="button" id="applyBtn" class="btn-secondary">Приложи</button>
      <button type="button" id="csvBtn" class="btn-csv" title="Експорт на видимите арбитражи (според мин. праг)">📥 Свали CSV</button>
      <span class="badge" id="next">Следващо авто: —</span>
    </div>
    <div class="status" id="status" aria-live="polite"></div>
    <div id="out"></div>
    <section class="calc-section">
      <div class="calc-head">
        <h2>🧮 Калкулатор</h2>
        <label class="calc-total">
          <span>Обща сума (€):</span>
          <input type="number" id="calcTotal" min="1" step="1" value="500" />
        </label>
        <button type="button" id="calcBtn" class="btn-secondary">Изчисли</button>
      </div>
      <p class="calc-sub">Използва последните заредени данни от сканиране (без ново сканиране).</p>
      <div id="calcOut"></div>
    </section>
    <section class="history-section">
      <div class="history-head">
        <h2>📈 История</h2>
        <div class="history-actions">
          <button type="button" id="historyRefreshBtn" class="btn-secondary">Обнови историята</button>
          <button type="button" id="historyClearBtn" class="btn-secondary">Изчисти историята</button>
        </div>
      </div>
      <div id="historyOut"></div>
    </section>
  </main>
  <script>
    const SCAN_MS = 5 * 60 * 1000;
    const btn = document.getElementById("btn");
    const status = document.getElementById("status");
    const out = document.getElementById("out");
    const nextEl = document.getElementById("next");
    const minPctInput = document.getElementById("minPct");
    const hotPctInput = document.getElementById("hotPct");
    const applyBtn = document.getElementById("applyBtn");
    const csvBtn = document.getElementById("csvBtn");
    const appTitle = document.getElementById("appTitle");
    const calcTotalInput = document.getElementById("calcTotal");
    const calcBtn = document.getElementById("calcBtn");
    const calcOut = document.getElementById("calcOut");
    const historyOut = document.getElementById("historyOut");
    const historyRefreshBtn = document.getElementById("historyRefreshBtn");
    const historyClearBtn = document.getElementById("historyClearBtn");
    const BOOK_IDS = ["efbet", "winbet", "betano", "palmsbet"];
    const BOOK_LABELS = { efbet: "efbet", winbet: "winbet", betano: "Betano", palmsbet: "Palms Bet" };
    let scanBusy = false;
    let nextAt = Date.now() + SCAN_MS;
    let autoTimer = null;
    /** Пълен отговор от последното сканиране (всички арбитражи). */
    let lastScanData = null;
    /** Активни прагове — запазват се между сканиранията. */
    let minProfitPct = 1.5;
    let hotProfitPct = 3.0;
    let lastStatusBase = "";
    let lastScanTimeDisplay = "";
    let allMatchesPanelVisible = false;

    function fmtBook(b, o) {
      return b + " — " + Number(o).toFixed(2);
    }

    function parsePctInput(el, fallback) {
      const v = parseFloat(String(el.value).replace(",", "."));
      return Number.isFinite(v) ? v : fallback;
    }

    function applyThresholdsFromInputs() {
      let minV = parsePctInput(minPctInput, minProfitPct);
      let hotV = parsePctInput(hotPctInput, hotProfitPct);
      if (minV < 0) minV = 0;
      if (!Number.isFinite(hotV)) hotV = hotProfitPct;
      if (hotV <= minV) hotV = minV + 0.1;
      minProfitPct = Math.round(minV * 100) / 100;
      hotProfitPct = Math.round(hotV * 100) / 100;
      minPctInput.value = String(minProfitPct);
      hotPctInput.value = String(hotProfitPct);
    }

    function rowTierClass(profit) {
      const p = Number(profit);
      if (p >= hotProfitPct) return "tier-hot";
      return "tier-warm";
    }

    function updateStatusLine() {
      if (!lastStatusBase || status.classList.contains("err")) return;
      const raw = lastScanData && lastScanData.opportunities ? lastScanData.opportunities.length : 0;
      const shown =
        lastScanData && lastScanData.opportunities
          ? lastScanData.opportunities.filter((o) => Number(o.profit_percent) >= minProfitPct).length
          : 0;
      const timePart = lastScanTimeDisplay
        ? " · Последно сканиране: " + lastScanTimeDisplay
        : "";
      status.textContent = lastStatusBase + timePart + " · показани: " + shown + " от " + raw;
    }

    function parseCalcTotal() {
      const v = parseFloat(String(calcTotalInput.value || "").replace(",", "."));
      if (!Number.isFinite(v) || v <= 0) return 100;
      return v;
    }

    function formatEur(v) {
      const n = Number(v);
      if (!Number.isFinite(n)) return "0.00";
      return n.toFixed(2);
    }

    function calcCell(book, odd, stake) {
      return escapeHtml(String(book || "—")) +
        " — " +
        escapeHtml(Number(odd).toFixed(2)) +
        " (€" +
        escapeHtml(formatEur(stake)) +
        ")";
    }

    function renderCalculatorTable() {
      if (!lastScanData || !Array.isArray(lastScanData.opportunities)) {
        calcOut.innerHTML = '<p class="empty">Няма сканиране. Натисни „Сканирай сега“.</p>';
        return;
      }
      const opportunities = lastScanData.opportunities || [];
      if (!opportunities.length) {
        calcOut.innerHTML = '<p class="empty">Няма намерени арбитражи в последното сканиране.</p>';
        return;
      }

      const total = parseCalcTotal();
      let h = '<div class="wrap"><table><thead><tr>';
      h += "<th>Мач</th><th>1</th><th>X</th><th>2</th><th class='num'>Очаквана печалба (€)</th>";
      h += "</tr></thead><tbody>";
      for (const o of opportunities) {
        const scale = total / 100;
        const s1 = Number(o.stake_1_eur || 0) * scale;
        const sx = Number(o.stake_x_eur || 0) * scale;
        const s2 = Number(o.stake_2_eur || 0) * scale;
        const profitEur = total * (Number(o.profit_percent || 0) / 100);
        h += "<tr>";
        h += "<td>" + escapeHtml(String(o.match || "—")) + "</td>";
        h += "<td>" + calcCell(o.book_1, o.odd_1, s1) + "</td>";
        h += "<td>" + calcCell(o.book_x, o.odd_x, sx) + "</td>";
        h += "<td>" + calcCell(o.book_2, o.odd_2, s2) + "</td>";
        h += "<td class='num pct'>€" + escapeHtml(formatEur(profitEur)) + "</td>";
        h += "</tr>";
      }
      h += "</tbody></table></div>";
      calcOut.innerHTML = h;
    }

    function renderHistoryTable(rows) {
      const historyRows = Array.isArray(rows) ? rows.slice(0, 50) : [];
      if (!historyRows.length) {
        historyOut.innerHTML = '<p class="empty">Историята е празна.</p>';
        return;
      }
      let h = '<div class="wrap"><table><thead><tr>';
      h += "<th>Дата/час</th><th>Мач</th><th>Букмейкъри</th><th class='num'>Печалба %</th>";
      h += "</tr></thead><tbody>";
      for (const row of historyRows) {
        const books = [
          String(row.book_1 || "—"),
          String(row.book_x || "—"),
          String(row.book_2 || "—"),
        ].join(" / ");
        const when = row.timestamp
          ? new Date(row.timestamp).toLocaleString("bg-BG", { hour12: false })
          : "—";
        h += "<tr>";
        h += "<td>" + escapeHtml(when) + "</td>";
        h += "<td>" + escapeHtml(String(row.match || "—")) + "</td>";
        h += "<td>" + escapeHtml(books) + "</td>";
        h += "<td class='num pct'>" + escapeHtml(String(row.profit_percent ?? "—")) + "</td>";
        h += "</tr>";
      }
      h += "</tbody></table></div>";
      historyOut.innerHTML = h;
    }

    async function loadHistory() {
      historyOut.innerHTML = '<p class="empty">Зареждане на история…</p>';
      try {
        const res = await fetch("/history", { headers: { "Accept": "application/json" } });
        const data = await res.json();
        if (!res.ok || !data.ok) {
          historyOut.innerHTML =
            '<p class="empty">Грешка при зареждане на история: ' +
            escapeHtml(data.error || res.statusText) +
            "</p>";
          return;
        }
        renderHistoryTable(data.history || []);
      } catch (e) {
        historyOut.innerHTML = '<p class="empty">Грешка при заявката за история.</p>';
      }
    }

    async function clearHistory() {
      historyClearBtn.disabled = true;
      try {
        const res = await fetch("/history/clear", { method: "POST", headers: { "Accept": "application/json" } });
        const data = await res.json();
        if (!res.ok || !data.ok) {
          historyOut.innerHTML =
            '<p class="empty">Неуспешно изчистване: ' +
            escapeHtml(data.error || res.statusText) +
            "</p>";
          return;
        }
        historyOut.innerHTML = '<p class="empty">Историята е изчистена.</p>';
      } catch (e) {
        historyOut.innerHTML = '<p class="empty">Грешка при изчистване на историята.</p>';
      } finally {
        historyClearBtn.disabled = false;
      }
    }

    function renderFromCache() {
      if (!lastScanData) return;
      const raw = lastScanData.opportunities || [];
      const filtered = raw.filter((o) => Number(o.profit_percent) >= minProfitPct);
      filtered.sort((a, b) => {
        const ah = Number(a.profit_percent) >= hotProfitPct;
        const bh = Number(b.profit_percent) >= hotProfitPct;
        if (ah !== bh) return ah ? -1 : 1;
        return Number(b.profit_percent) - Number(a.profit_percent);
      });

      const foot =
        '<p class="table-foot">Възможности под ' +
        escapeHtml(String(minProfitPct)) +
        "% са скрити</p>";

      allMatchesPanelVisible = false;
      const allBlock = renderAllMatchesBlock(lastScanData.all_matches);

      if (!raw.length) {
        out.innerHTML =
          '<p class="empty">Няма намерени 1X2 арбитражи при текущите коефициенти.</p>' +
          allBlock +
          foot;
        wireAllMatchesToggle();
        updateStatusLine();
        return;
      }
      if (!filtered.length) {
        out.innerHTML =
          '<p class="empty">Няма арбитражи над избрания минимален праг (' +
          escapeHtml(String(minProfitPct)) +
          "%).</p>" +
          allBlock +
          foot;
        wireAllMatchesToggle();
        updateStatusLine();
        return;
      }

      let h = '<div class="wrap"><table><thead><tr>';
      h += "<th>Мач</th><th>Букмейкър 1</th><th>Букмейкър X</th><th>Букмейкър 2</th>";
      h += '<th class="num">Печалба %</th><th>Как да залагам (€100)</th></tr></thead><tbody>';
      for (const r of filtered) {
        const p = Number(r.profit_percent);
        const hot = p >= hotProfitPct;
        const trc = rowTierClass(p);
        const liveMark = r.is_live ? "🔴 LIVE " : "";
        const matchShow = liveMark + (hot ? "🔥 " : "") + r.match;
        h += '<tr class="' + trc + '">';
        h += "<td>" + escapeHtml(matchShow) + "</td>";
        h += "<td>" + escapeHtml(fmtBook(r.book_1, r.odd_1)) + "</td>";
        h += "<td>" + escapeHtml(fmtBook(r.book_x, r.odd_x)) + "</td>";
        h += "<td>" + escapeHtml(fmtBook(r.book_2, r.odd_2)) + "</td>";
        h += '<td class="num pct">' + escapeHtml(String(r.profit_percent)) + "</td>";
        h += '<td class="plan">' + escapeHtml(r.betting_plan || "—") + "</td>";
        h += "</tr>";
      }
      h += "</tbody></table></div>" + foot + allBlock;
      out.innerHTML = h;
      wireAllMatchesToggle();
      updateStatusLine();
      renderCalculatorTable();
    }

    function escapeHtml(s) {
      const d = document.createElement("div");
      d.textContent = s == null ? "" : String(s);
      return d.innerHTML;
    }

    function renderAllMatchesBlock(allMatches) {
      const am = allMatches || [];
      const countLabel = am.length ? String(am.length) : "0";
      let h =
        '<section class="matches-covered-section">' +
        '<div class="matches-covered-head">' +
        "<h2>📊 Всички покрити мачове</h2>" +
        '<button type="button" class="btn-secondary" id="toggleAllMatchesBtn">Покажи</button>' +
        '<span style="font-size:0.78rem;color:var(--muted)">(' +
        countLabel +
        " уникални)</span></div>" +
        '<div class="matches-covered-panel" id="allMatchesPanel" hidden>' +
        '<div class="wrap all-matches-inner"><table><thead><tr><th>Мач</th>';
      for (const id of BOOK_IDS) {
        h += "<th>" + escapeHtml(BOOK_LABELS[id]) + "</th>";
      }
      h += "</tr></thead><tbody>";
      if (!am.length) {
        h += '<tr><td colspan="5" class="empty">Няма заредени мачове.</td></tr>';
      } else {
        for (const row of am) {
          h += "<tr><td>" + escapeHtml(row.label || "—") + "</td>";
          for (const id of BOOK_IDS) {
            const cell = row.books && row.books[id];
            if (cell && cell.odd_1 != null && cell.odd_x != null && cell.odd_2 != null) {
              const line =
                Number(cell.odd_1).toFixed(2) +
                " / " +
                Number(cell.odd_x).toFixed(2) +
                " / " +
                Number(cell.odd_2).toFixed(2);
              const sl = cell.site_label && String(cell.site_label) !== String(row.label);
              const sub = sl
                ? '<div class="sub">' + escapeHtml(String(cell.site_label)) + "</div>"
                : "";
              h += '<td class="odds-cell">' + sub + escapeHtml(line) + "</td>";
            } else {
              h += '<td class="muted-cell">—</td>';
            }
          }
          h += "</tr>";
        }
      }
      h += "</tbody></table></div></div></section>";
      return h;
    }

    function wireAllMatchesToggle() {
      const btn = document.getElementById("toggleAllMatchesBtn");
      const panel = document.getElementById("allMatchesPanel");
      if (!btn || !panel) return;
      allMatchesPanelVisible = false;
      panel.hidden = true;
      btn.textContent = "Покажи";
      btn.onclick = function () {
        allMatchesPanelVisible = !allMatchesPanelVisible;
        panel.hidden = !allMatchesPanelVisible;
        btn.textContent = allMatchesPanelVisible ? "Скрий" : "Покажи";
      };
    }

    function csvEscapeCell(val) {
      if (val == null) return "";
      const s = String(val);
      if (/[",\\n\\r]/.test(s)) return '"' + s.replace(/"/g, '""') + '"';
      return s;
    }

    function downloadArbitrageCsv() {
      if (!lastScanData || !Array.isArray(lastScanData.opportunities)) {
        return;
      }
      const filtered = lastScanData.opportunities.filter(
        (o) => Number(o.profit_percent) >= minProfitPct
      );
      const headers = [
        "match",
        "book_1",
        "odd_1",
        "book_x",
        "odd_x",
        "book_2",
        "odd_2",
        "profit_percent",
        "betting_plan",
      ];
      const lines = [headers.join(",")];
      for (const o of filtered) {
        lines.push(
          headers
            .map(function (key) {
              return csvEscapeCell(o[key]);
            })
            .join(",")
        );
      }
      const blob = new Blob(["\\uFEFF" + lines.join("\\n")], {
        type: "text/csv;charset=utf-8",
      });
      const a = document.createElement("a");
      const stamp = new Date().toISOString().slice(0, 19).replace(/[:T]/g, "-");
      a.href = URL.createObjectURL(blob);
      a.download = "arbitrage-1x2-" + stamp + ".csv";
      a.click();
      URL.revokeObjectURL(a.href);
    }

    function tickNext() {
      const left = Math.max(0, nextAt - Date.now());
      const m = Math.floor(left / 60000);
      const s = Math.floor((left % 60000) / 1000);
      nextEl.textContent = "Следващо авто: " + m + "м " + s + "с";
    }
    setInterval(tickNext, 1000);
    tickNext();

    function armAutoScan() {
      clearTimeout(autoTimer);
      nextAt = Date.now() + SCAN_MS;
      autoTimer = setTimeout(() => runScan(false), SCAN_MS);
    }

    async function runScan(isManual) {
      if (scanBusy) return;
      scanBusy = true;
      btn.disabled = true;
      clearTimeout(autoTimer);
      status.textContent = (isManual ? "Ръчно сканиране" : "Автоматично сканиране") + "… моля изчакайте.";
      status.classList.remove("err");
      out.innerHTML = '<p class="empty">Зареждане…</p>';
      try {
        const res = await fetch("/scan", { method: "POST", headers: { "Accept": "application/json" } });
        const data = await res.json();
        if (!data.ok) {
          status.textContent = "Грешка: " + (data.error || res.statusText);
          status.classList.add("err");
          out.innerHTML = "";
          return;
        }
        lastScanData = data;
        lastScanTimeDisplay = new Date().toLocaleTimeString("bg-BG", {
          hour: "2-digit",
          minute: "2-digit",
          second: "2-digit",
          hour12: false,
        });
        lastStatusBase = (function () {
          const bc = data.book_match_counts || {};
          const parts = ["efbet", "winbet", "betano", "palmsbet"].map(function (id) {
            return id + ": " + (bc[id] != null ? bc[id] : "—");
          });
          return (
            parts.join(" · ") +
            " · уникални мачове: " +
            (data.unique_matches_indexed ?? "—") +
            " · с ≥2 къщи: " +
            (data.cross_book_matches ?? "—") +
            " · арбитражи: " +
            data.opportunities_count
          );
        })();
        renderFromCache();
        renderCalculatorTable();
        loadHistory();
      } catch (e) {
        status.textContent = "Грешка при заявката.";
        status.classList.add("err");
        out.innerHTML = "";
        calcOut.innerHTML = '<p class="empty">Калкулаторът чака успешно сканиране.</p>';
      } finally {
        scanBusy = false;
        btn.disabled = false;
        armAutoScan();
      }
    }

    btn.addEventListener("click", () => runScan(true));
    applyBtn.addEventListener("click", () => {
      applyThresholdsFromInputs();
      renderFromCache();
    });
    csvBtn.addEventListener("click", () => {
      applyThresholdsFromInputs();
      downloadArbitrageCsv();
    });
    calcBtn.addEventListener("click", () => {
      renderCalculatorTable();
    });
    historyRefreshBtn.addEventListener("click", () => {
      loadHistory();
    });
    historyClearBtn.addEventListener("click", () => {
      clearHistory();
    });
    appTitle.addEventListener("click", () => location.reload());
    appTitle.addEventListener("keydown", (e) => {
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        location.reload();
      }
    });
    runScan(false);
    loadHistory();
  </script>
</body>
</html>"""
    return Response(html, mimetype="text/html; charset=utf-8")


@app.route("/scan", methods=["GET", "POST"])
@app.route("/api/scan", methods=["GET", "POST"])
def scan():
    return _do_scan()


@app.route("/history", methods=["GET"])
def history():
    return _do_history()


@app.route("/history/clear", methods=["POST"])
def history_clear():
    return _do_history_clear()


if __name__ == "__main__":
    print(f" * http://127.0.0.1:{int(os.environ.get('PORT', 8765))}/  (0.0.0.0)")
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8765)))
