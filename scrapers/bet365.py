"""
1X2 от bet365 — Playwright с UA и дълго изчакване (често Cloudflare/ограничен достъп).
"""

from __future__ import annotations

from typing import Any

BOOK = "bet365"
FOOTBALL_URL = "https://www.bet365.com/#/AS/B1/"


def fetch_football_two_way(
    url: str = FOOTBALL_URL,
    timeout_ms: int = 120_000,
    wait_after_load_ms: int = 35_000,
) -> list[dict[str, Any]]:
    try:
        from playwright.sync_api import sync_playwright

        from scrapers._common_1x2 import (
            default_playwright_context,
            parse_body_lines_1x2,
            rows_td_vs_playwright,
        )
    except ImportError:
        return []

    try:
        with sync_playwright() as p:
            browser, context = default_playwright_context(p)
            page = context.new_page()
            page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
            page.wait_for_timeout(wait_after_load_ms)
            for _ in range(3):
                page.evaluate("window.scrollBy(0, 600)")
                page.wait_for_timeout(2000)

            rows = rows_td_vs_playwright(page, BOOK)
            if not rows:
                rows = parse_body_lines_1x2(page.inner_text("body"), BOOK)
            context.close()
            browser.close()
            return rows
    except Exception:
        return []


fetch_football_1x2 = fetch_football_two_way

if __name__ == "__main__":
    d = fetch_football_1x2()
    print("matches:", len(d))
