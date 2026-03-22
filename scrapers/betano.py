"""1X2 от Betano.bg — Playwright, скрол до края, DOM от предстоящи мачове + текст/td."""

# Браузърът се пуска през scrapers._common_1x2.default_playwright_context с
# CHROMIUM_LAUNCH_ARGS (--no-sandbox, --disable-setuid-sandbox, …) за Railway/Docker.

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any

# При `python3 scrapers/betano.py` Python слага папката на скрипта в path — добавяме корена на проекта.
_root = Path(__file__).resolve().parent.parent
for p in (_root, _root / ".deps"):
    s = str(p)
    if p.is_dir() and s not in sys.path:
        sys.path.insert(0, s)

BOOK = "betano"
FOOTBALL_URL = "https://www.betano.bg/sport/futbol/"
# Списъкът с 1X2 на главната е силно орязан; предстоящи мачове има редове pre-event + коефициенти.
UPCOMING_MATCHES_URL = "https://www.betano.bg/sport/futbol/predstoyashti-machove/"

_SEL_LINE_RE = re.compile(r"^([12xX])\s+(\d+[.,]\d{2,3})$")


def _dismiss_landing_modal(page: Any) -> None:
    """Betano показва welcome модал (регистрация/вход), който блокира кликове по табове и списъци."""
    try:
        modal = page.locator('[data-testid="landing-modal"]')
        if not modal.count():
            return
        if not modal.first.is_visible(timeout=2500):
            return
        btns = page.locator('[data-testid="landing-modal"] button')
        for i in range(min(btns.count(), 6)):
            try:
                txt = (btns.nth(i).inner_text(timeout=1000) or "").strip()
                if not txt or txt in ("×", "✕", "X"):
                    btns.nth(i).click(timeout=3000)
                    page.wait_for_timeout(600)
                    break
            except Exception:
                continue
        if modal.first.is_visible(timeout=400):
            page.keyboard.press("Escape")
            page.wait_for_timeout(400)
    except Exception:
        try:
            page.keyboard.press("Escape")
            page.wait_for_timeout(400)
        except Exception:
            pass


def _dismiss_cookies(page: Any) -> None:
    for t in ("Приеми всички", "Приеми", "Съгласен", "OK", "Разреши всички"):
        loc = page.locator(f"button:has-text('{t}')")
        if loc.count():
            try:
                loc.first.click(timeout=2500)
                return
            except Exception:
                continue


def _parse_three_event_selections(texts: list[str]) -> tuple[float, float, float] | None:
    by_label: dict[str, float] = {}
    for raw in texts:
        t = re.sub(r"\s+", " ", (raw or "").strip())
        m = _SEL_LINE_RE.match(t)
        if not m:
            return None
        lab = m.group(1).upper()
        if lab not in ("1", "2", "X"):
            return None
        v = float(m.group(2).replace(",", "."))
        if not (1.01 <= v <= 500.0):
            return None
        by_label[lab] = v
    if set(by_label.keys()) != {"1", "2", "X"}:
        return None
    return by_label["1"], by_label["X"], by_label["2"]


def rows_betano_pre_event_playwright(page: Any, book: str) -> list[dict[str, Any]]:
    """
    Редове от [data-qa=pre-event]: имена в participants .tw-truncate, 1X2 в родител с точно 3 event-selection.
    """
    try:
        from scrapers._common_1x2 import normalize_match_label
    except ImportError:
        return []

    raw = page.evaluate(
        """() => {
      const pes = Array.from(document.querySelectorAll('[data-qa="pre-event"]'));
      const junkTeam = (s) => /неутрален|neutral/i.test(s);
      const out = [];
      for (const pe of pes) {
        const teams = Array.from(pe.querySelectorAll('[data-qa="participants"] .tw-truncate'))
          .map(e => (e.textContent || '').trim())
          .filter(t => t && !junkTeam(t));
        if (teams.length < 2) continue;
        const t1 = teams[0], t2 = teams[1];
        let el = pe.parentElement;
        let row = null;
        while (el && el !== document.body) {
          if (el.querySelectorAll('[data-qa="event-selection"]').length === 3) {
            row = el;
            break;
          }
          el = el.parentElement;
        }
        if (!row) continue;
        const texts = Array.from(row.querySelectorAll('[data-qa="event-selection"]'))
          .map(e => (e.innerText || '').replace(/\\s+/g, ' ').trim());
        if (texts.length !== 3) continue;
        out.push({ t1, t2, texts });
      }
      return out;
    }"""
    )
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in raw or []:
        t1, t2 = item.get("t1"), item.get("t2")
        texts = item.get("texts") or []
        if not t1 or not t2 or len(texts) != 3:
            continue
        parsed = _parse_three_event_selections(texts)
        if not parsed:
            continue
        o1, ox, o2 = parsed
        label = normalize_match_label(t1, t2)
        if label in seen:
            continue
        seen.add(label)
        out.append(
            {
                "book": book,
                "label": label,
                "odd_1": o1,
                "odd_x": ox,
                "odd_2": o2,
                "odd_a": o1,
                "odd_b": o2,
            }
        )
    return out


def fetch_football_two_way(
    url: str = UPCOMING_MATCHES_URL,
    timeout_ms: int = 90_000,
    wait_after_load_ms: int = 24_000,
) -> list[dict[str, Any]]:
    try:
        from playwright.sync_api import sync_playwright

        from scrapers._common_1x2 import (
            default_playwright_context,
            merge_rows_by_label,
            parse_body_lines_1x2,
            parse_body_lines_1x2_backward,
            rows_td_vs_playwright,
            scroll_to_bottom_stable,
        )
    except ImportError:
        return []

    try:
        with sync_playwright() as p:
            browser, context = default_playwright_context(p)
            page = context.new_page()
            page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
            page.wait_for_timeout(5000)
            _dismiss_landing_modal(page)
            _dismiss_cookies(page)
            page.wait_for_timeout(wait_after_load_ms)
            scroll_to_bottom_stable(page, pause_ms=1000, max_rounds=45, stable_needed=3)
            for _ in range(5):
                page.evaluate("() => window.scrollTo(0, document.body.scrollHeight)")
                page.wait_for_timeout(2000)

            body_text = page.inner_text("body")
            rows_dom = rows_betano_pre_event_playwright(page, BOOK)
            rows_td = rows_td_vs_playwright(page, BOOK)
            rows_strict = parse_body_lines_1x2(body_text, BOOK)
            rows_back = parse_body_lines_1x2_backward(body_text, BOOK)
            # DOM редовете последни — приоритет над шум от плосък body текст.
            rows = merge_rows_by_label(rows_td, rows_strict, rows_back, rows_dom)

            context.close()
            browser.close()
            return rows
    except Exception:
        return []


fetch_football_1x2 = fetch_football_two_way

if __name__ == "__main__":
    d = fetch_football_1x2()
    print("matches:", len(d))
    for r in d[:20]:
        print(r["label"], r["odd_1"], r["odd_x"], r["odd_2"])
