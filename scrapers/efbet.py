"""
Реални коефициенти 1X2 за футбол от efbet.com.

Статистиката в списъка се зарежда в браузъра (SPA). `requests` + BeautifulSoup
виждат само празни placeholder-и, затова основният път е Playwright.

Връща редове с:
  - label: име на мача („Домакин vs Гост“)
  - odd_1, odd_x, odd_2 — коефициенти 1, X, 2
  - odd_a, odd_b — същите като odd_1 и odd_2 (за съвместимост с main.py / двупосочен арбитраж)
"""

from __future__ import annotations

import re
from typing import Any

_ODDS_RE = re.compile(r"\d+[.,]\d{2,3}")

BOOK = "efbet"
FOOTBALL_URL = "https://www.efbet.com/bg/sport/football"


def _parse_three_odds(row_text: str, after_label: str) -> tuple[float, float, float] | None:
    """Изважда първите три десетични коефициента след името на мача."""
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


def _rows_from_playwright(page: Any) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set[str] = set()

    for link in page.locator("td a").all():
        try:
            label = link.inner_text().strip()
        except Exception:
            continue
        if " vs " not in label or len(label) < 5:
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


def _efbet_open_football_listing(page: Any, wait_ms: int = 10_000) -> None:
    """От начална страница отваря пълния футболен списък (hash navigation)."""
    page.wait_for_timeout(3000)
    for sel in (
        'nav a:has-text("Футбол")',
        '[class*="sidebar"] a:has-text("Футбол")',
        'aside a:has-text("Футбол")',
        'a:has-text("Футбол")',
    ):
        loc = page.locator(sel)
        if loc.count():
            try:
                loc.first.click(timeout=8000)
                page.wait_for_timeout(wait_ms)
                return
            except Exception:
                continue


def fetch_football_upcoming(
    start_url: str = "https://www.efbet.com/",
    timeout_ms: int = 90_000,
    wait_after_nav_ms: int = 10_000,
) -> list[dict[str, Any]]:
    """
    Разширен списък: начало → навигация „Футбол“ → дълбок скрол.
    По-дълъг хоризонт от предстоящи мачове, ако сайтът ги подава в същия изглед.
    """
    try:
        from playwright.sync_api import sync_playwright

        from scrapers._common_1x2 import scroll_to_bottom_stable
    except ImportError:
        return []

    rows: list[dict[str, Any]] = []
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(locale="bg-BG")
            page = context.new_page()
            page.goto(start_url, wait_until="domcontentloaded", timeout=timeout_ms)
            page.wait_for_timeout(5000)
            _efbet_open_football_listing(page, wait_after_nav_ms)
            scroll_to_bottom_stable(page, pause_ms=1000, max_rounds=35, stable_needed=2)
            for _ in range(5):
                page.evaluate("() => window.scrollTo(0, document.body.scrollHeight)")
                page.wait_for_timeout(2000)
            rows = _rows_from_playwright(page)
            context.close()
            browser.close()
    except Exception:
        return []

    return rows


def fetch_football_for_scan() -> list[dict[str, Any]]:
    """За main.py: стандартен URL + разширен изглед, без дубли (casefold)."""
    try:
        from scrapers._common_1x2 import merge_rows_by_label_casefold
    except ImportError:
        return fetch_football_two_way()

    return merge_rows_by_label_casefold(
        fetch_football_two_way(),
        fetch_football_upcoming(),
    )


def fetch_football_two_way(
    url: str = FOOTBALL_URL,
    timeout_ms: int = 90_000,
    wait_after_load_ms: int = 10_000,
) -> list[dict[str, Any]]:
    """
    Зарежда футболна секцията и връща мачове с 1X2.

    При грешка (няма браузър, timeout, променен DOM) връща празен списък.
    """
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
            page.wait_for_timeout(wait_after_load_ms)
            rows = _rows_from_playwright(page)
            context.close()
            browser.close()
    except Exception:
        return []

    return rows


# Явно име за 1X2 (същата функция)
fetch_football_1x2 = fetch_football_two_way


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "upcoming":
        data = fetch_football_upcoming()
        print(f"matches (upcoming extended): {len(data)}")
    elif len(sys.argv) > 1 and sys.argv[1] == "scan":
        data = fetch_football_for_scan()
        print(f"matches (for_scan merged): {len(data)}")
    else:
        data = fetch_football_1x2()
        print(f"matches: {len(data)}")
    for r in data[:12]:
        print(
            r["label"],
            "| 1:",
            r["odd_1"],
            "X:",
            r["odd_x"],
            "2:",
            r["odd_2"],
        )
