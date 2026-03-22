"""
1X2 от Inbet — Playwright.

При директно пускане на файла (`python3 scrapers/inbet.py`) браузърът е видим
(headful), за да се вижда какво зарежда сайтът. От `main.run_scan()` по подразбиране
е headless (задай INBET_HEADLESS=0 за видим прозорец и от там).

Селектори: първо td>a с „vs“ (като efbet), после плосък текст (редове 1/X/2).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

_root = Path(__file__).resolve().parent.parent
for p in (_root, _root / ".deps"):
    s = str(p)
    if p.is_dir() and s not in sys.path:
        sys.path.insert(0, s)

BOOK = "inbet"
URLS = [
    "https://inbet.bg/sports/football",
    "https://www.inbet.bg/sports/football",
]


def _dismiss_cookies(page: Any) -> None:
    for t in (
        "Разреши всички",
        "Приеми всички",
        "Приеми",
        "Съгласен",
        "OK",
        "Allow all",
    ):
        loc = page.locator(f"button:has-text('{t}')")
        if loc.count():
            try:
                loc.first.click(timeout=4000, force=True)
                page.wait_for_timeout(1500)
                return
            except Exception:
                continue


def _try_inbet_dom_rows(page: Any) -> list[dict[str, Any]]:
    """
    Опит за редове с 1X2: контейнери с два отбора + три коефициента.
    Селекторите са общи — при промяна на Inbet UI може да се коригират тук.
    """
    from scrapers._common_1x2 import normalize_match_label

    out: list[dict[str, Any]] = []
    seen: set[str] = set()

    # Често срещани шаблони за спортни списъци (React/Vue)
    container_selectors = [
        "[class*='event-row']",
        "[class*='EventRow']",
        "[class*='match-row']",
        "[class*='MatchRow']",
        "[data-testid*='event']",
        "article",
    ]

    for sel in container_selectors:
        try:
            for el in page.locator(sel).all()[:200]:
                try:
                    t = el.inner_text()
                except Exception:
                    continue
                lines = [x.strip() for x in t.splitlines() if x.strip()]
                if len(lines) < 8:
                    continue
                # търси подредба 1 / odd / X / odd / 2 / odd в текста на контейнера
                for i in range(len(lines) - 6):
                    if lines[i] != "1":
                        continue
                    if lines[i + 2].upper() != "X" or lines[i + 4] != "2":
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
                    h, a = lines[i - 2], lines[i - 1]
                    if len(h) < 2 or len(a) < 2 or h in ("1", "X", "2"):
                        continue
                    label = normalize_match_label(h, a)
                    if label in seen:
                        continue
                    seen.add(label)
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
                    break
        except Exception:
            continue

    return out


def fetch_football_two_way(
    urls: list[str] | None = None,
    timeout_ms: int = 90_000,
    wait_after_load_ms: int = 20_000,
    headless: bool | None = None,
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

    if headless is None:
        headless = os.environ.get("INBET_HEADLESS", "1").lower() in (
            "1",
            "true",
            "yes",
            "",
        )

    targets = urls or URLS
    for url in targets:
        try:
            with sync_playwright() as p:
                browser, context = default_playwright_context(p, headless=headless)
                page = context.new_page()
                page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
                page.wait_for_timeout(5000)
                _dismiss_cookies(page)
                page.wait_for_timeout(wait_after_load_ms)
                scroll_to_bottom_stable(page, pause_ms=1000, max_rounds=40, stable_needed=3)

                body_text = page.inner_text("body")
                rows_td = rows_td_vs_playwright(page, BOOK)
                rows_dom = _try_inbet_dom_rows(page)
                rows_s = parse_body_lines_1x2(body_text, BOOK)
                rows_b = parse_body_lines_1x2_backward(body_text, BOOK)
                rows = merge_rows_by_label(rows_td, rows_dom, rows_s, rows_b)

                context.close()
                browser.close()
                if rows:
                    return rows
        except Exception:
            continue
    return []


fetch_football_1x2 = fetch_football_two_way

if __name__ == "__main__":
    # По подразбиране headful; headless: INBET_HEADLESS=1 python3 scrapers/inbet.py
    os.environ.setdefault("INBET_HEADLESS", "0")
    _headless = os.environ.get("INBET_HEADLESS", "0").lower() in ("1", "true", "yes")
    d = fetch_football_1x2(headless=_headless)
    print("matches:", len(d))
    for r in d[:20]:
        print(r["label"], r["odd_1"], r["odd_x"], r["odd_2"])
