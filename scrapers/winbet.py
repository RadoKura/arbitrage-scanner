"""
Реални коефициенти 1X2 за футбол от winbet.bg чрез Playwright.

Събитията в слайдера/списъка са в `div.egtd-event-slide-l-3` с редове:
отбор 1, отбор 2, 1, коеф., X, коеф., 2, коеф. (само футбол с X).
"""

from __future__ import annotations

import re
from typing import Any

BOOK = "winbet"
FOOTBALL_URL = "https://www.winbet.bg/sport/football"

_BLOCK_SELECTOR = "div.egtd-event-slide-l-3"
_LIVE_ROW_SELECTOR = ".egtd-erow-l1"


def _lines(text: str) -> list[str]:
    return [ln.strip() for ln in text.splitlines() if ln.strip()]


def _parse_event_block(lines: list[str]) -> dict[str, Any] | None:
    """Търси подредба 1 / odd / X / odd / 2 / odd и двата отбора преди тях."""
    for i in range(len(lines) - 5):
        if lines[i] != "1":
            continue
        if lines[i + 2].upper() != "X":
            continue
        if lines[i + 4] != "2":
            continue
        try:
            o1 = float(lines[i + 1].replace(",", "."))
            ox = float(lines[i + 3].replace(",", "."))
            o2 = float(lines[i + 5].replace(",", "."))
        except ValueError:
            continue
        if not (1.01 <= o1 <= 500.0 and 1.01 <= ox <= 500.0 and 1.01 <= o2 <= 500.0):
            continue
        if i < 2:
            continue
        home, away = lines[i - 2], lines[i - 1]
        if home in ("1", "2", "X", "BB") or away in ("1", "2", "X"):
            continue
        if re.fullmatch(r"\d+", home) or re.fullmatch(r"\d+", away):
            continue
        label = f"{home} vs {away}"
        return {
            "book": BOOK,
            "label": label,
            "odd_1": o1,
            "odd_x": ox,
            "odd_2": o2,
            "odd_a": o1,
            "odd_b": o2,
        }
    return None


def _dismiss_cookie_banner(page: Any) -> None:
    for name in ("Разреши всички", "Позволи избора", "Отказ"):
        loc = page.locator(f"button:has-text('{name}')")
        if loc.count() > 0:
            try:
                loc.first.click(timeout=3000)
                return
            except Exception:
                continue


def _rows_from_playwright(page: Any) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for el in page.locator(_BLOCK_SELECTOR).all():
        try:
            raw = el.inner_text()
        except Exception:
            continue
        parsed = _parse_event_block(_lines(raw))
        if parsed is None:
            continue
        key = parsed["label"].casefold()
        if key in seen:
            continue
        seen.add(key)
        out.append(parsed)
    return out


def _parse_live_event_row(text: str) -> dict[str, Any] | None:
    """
    Ред „На живо“: отбори + резултат/време + BB + три коефициента 1/X/2 в края на текста.
    """
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    odds: list[float] = []
    for ln in lines:
        if re.fullmatch(r"\d+[.,]\d{2,3}", ln.replace(",", ".")):
            try:
                v = float(ln.replace(",", "."))
                if 1.01 <= v <= 500.0:
                    odds.append(v)
            except ValueError:
                continue
    if len(odds) < 3:
        return None
    o1, ox, o2 = odds[-3], odds[-2], odds[-1]

    teams: list[str] = []
    for ln in lines:
        if not re.search(r"[a-zA-Zа-яА-ЯёЁ]", ln):
            continue
        if ln == "BB" or ln.upper() == "X":
            continue
        if re.match(r"^\d{1,2}:\d{2}", ln):
            continue
        if re.fullmatch(r"\d{1,2}", ln):
            continue
        if re.match(r"^[+-]\d{3,}$", ln):
            continue
        teams.append(ln)
        if len(teams) >= 2:
            break
    if len(teams) < 2:
        return None
    label = f"{teams[0]} vs {teams[1]}"
    return {
        "book": BOOK,
        "label": label,
        "odd_1": o1,
        "odd_x": ox,
        "odd_2": o2,
        "odd_a": o1,
        "odd_b": o2,
    }


def _rows_winbet_live_from_page(page: Any) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for el in page.locator(_LIVE_ROW_SELECTOR).all()[:250]:
        try:
            raw = el.inner_text()
        except Exception:
            continue
        parsed = _parse_live_event_row(raw)
        if parsed is None:
            continue
        k = parsed["label"].casefold()
        if k in seen:
            continue
        seen.add(k)
        out.append(parsed)
    return out


def fetch_football_upcoming(
    timeout_ms: int = 90_000,
    wait_after_load_ms: int = 8_000,
) -> list[dict[str, Any]]:
    """
    Предматч (карусел) + На живо (футбол) в една сесия.
    Допълва fetch_football_two_way с live срещи и същите прематч редове.
    """
    try:
        from playwright.sync_api import sync_playwright

        from scrapers._common_1x2 import merge_rows_by_label_casefold
    except ImportError:
        return []

    rows: list[dict[str, Any]] = []
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(locale="bg-BG")
            page = context.new_page()
            page.goto(FOOTBALL_URL, wait_until="domcontentloaded", timeout=timeout_ms)
            page.wait_for_timeout(2000)
            _dismiss_cookie_banner(page)
            page.wait_for_timeout(wait_after_load_ms)
            prematch = _rows_from_playwright(page)
            try:
                page.locator("a:has-text('На живо')").first.click(timeout=6000)
                page.wait_for_timeout(5000)
                try:
                    page.locator("text=Футбол").first.click(timeout=3000)
                    page.wait_for_timeout(2500)
                except Exception:
                    pass
                live = _rows_winbet_live_from_page(page)
            except Exception:
                live = []
            rows = merge_rows_by_label_casefold(prematch, live)
            context.close()
            browser.close()
    except Exception:
        return []

    return rows


def fetch_football_for_scan() -> list[dict[str, Any]]:
    """
    За main.py: една сесия с прематч + „На живо“ (fetch_football_upcoming).
    fetch_football_two_way остава за бърз единичен crawl без live.
    """
    return fetch_football_upcoming()


def fetch_football_two_way(
    url: str = FOOTBALL_URL,
    timeout_ms: int = 90_000,
    wait_after_load_ms: int = 10_000,
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
            page.wait_for_timeout(2000)
            _dismiss_cookie_banner(page)
            page.wait_for_timeout(wait_after_load_ms)
            rows = _rows_from_playwright(page)
            context.close()
            browser.close()
    except Exception:
        return []

    return rows


fetch_football_1x2 = fetch_football_two_way


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "upcoming":
        data = fetch_football_upcoming()
        print(f"matches (upcoming+live): {len(data)}")
    elif len(sys.argv) > 1 and sys.argv[1] == "scan":
        data = fetch_football_for_scan()
        print(f"matches (for_scan merged): {len(data)}")
    else:
        data = fetch_football_1x2()
        print(f"matches: {len(data)}")
    for r in data[:15]:
        print(
            r["label"],
            "| 1:",
            r["odd_1"],
            "X:",
            r["odd_x"],
            "2:",
            r["odd_2"],
        )
