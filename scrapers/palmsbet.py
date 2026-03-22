"""
1X2 коефициенти за футбол от Palms Bet (palmsbet.com) — Playwright.

Страница: /bg/pages/football/. Парсерът следва модела на efbet (td > a с „vs“ + три коефициента в реда).
При Cloudflare „Just a moment…“ ще върне празен списък — на локална машина без блокировка може да връща редове.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any

_root = Path(__file__).resolve().parent.parent
for p in (_root, _root / ".deps"):
    s = str(p)
    if p.is_dir() and s not in sys.path:
        sys.path.insert(0, s)

_ODDS_RE = re.compile(r"\d+[.,]\d{2,3}")

BOOK = "palmsbet"
FOOTBALL_URL = "https://www.palmsbet.com/bg/pages/football/"


def _parse_three_odds(row_text: str, after_label: str) -> tuple[float, float, float] | None:
    idx = row_text.find(after_label)
    if idx == -1:
        return None
    tail = row_text[idx + len(after_label) :]
    raw = _ODDS_RE.findall(tail)
    vals: list[float] = []
    for s in raw:
        v = float(s.replace(",", "."))
        if 1.01 <= v <= 500.0:
            vals.append(v)
        if len(vals) >= 3:
            break
    if len(vals) < 3:
        return None
    return vals[0], vals[1], vals[2]


def _dismiss_cookies(page: Any) -> None:
    for t in ("Приеми всички", "Приеми", "Разреши всички", "Съгласен", "OK", "Allow all"):
        loc = page.locator(f"button:has-text('{t}')")
        if loc.count():
            try:
                loc.first.click(timeout=3000)
                return
            except Exception:
                continue


def _rows_from_playwright(page: Any) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set[str] = set()

    for link in page.locator("td a").all():
        try:
            label = link.inner_text().strip()
        except Exception:
            continue
        if " vs " not in label.lower() or len(label) < 5:
            continue

        row = link.locator("xpath=ancestor::tr[1]")
        try:
            row_text = row.inner_text()
        except Exception:
            continue

        triple = _parse_three_odds(row_text, label)
        if triple is None:
            continue

        o1, ox, o2 = triple
        key = label.casefold()
        if key in seen:
            continue
        seen.add(key)

        out.append(
            {
                "book": BOOK,
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
    url: str = FOOTBALL_URL,
    timeout_ms: int = 90_000,
    wait_after_load_ms: int = 12_000,
) -> list[dict[str, Any]]:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return []

    rows: list[dict[str, Any]] = []
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(locale="bg-BG")
            page = context.new_page()
            page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
            page.wait_for_timeout(4000)
            _dismiss_cookies(page)
            page.wait_for_timeout(wait_after_load_ms)
            rows = _rows_from_playwright(page)
            context.close()
            browser.close()
    except Exception:
        return []

    return rows


fetch_football_1x2 = fetch_football_two_way


if __name__ == "__main__":
    data = fetch_football_1x2()
    print(f"matches: {len(data)}")
    for r in data[:12]:
        print(r["label"], "| 1:", r["odd_1"], "X:", r["odd_x"], "2:", r["odd_2"])
