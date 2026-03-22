"""1X2 от Sesame.bg — Playwright."""

from __future__ import annotations

from typing import Any

BOOK = "sesame"
URLS = (
    "https://www.sesame.bg/sport/football",
    "https://sesame.bg/sport/football",
)


def _dismiss_cookies(page: Any) -> None:
    for t in ("Разреши всички", "Приеми всички", "Съгласен", "OK"):
        loc = page.locator(f"button:has-text('{t}')")
        if loc.count():
            try:
                loc.first.click(timeout=4000, force=True)
                page.wait_for_timeout(2000)
                return
            except Exception:
                continue


def fetch_football_two_way(
    urls: tuple[str, ...] | None = None,
    timeout_ms: int = 90_000,
    wait_after_load_ms: int = 22_000,
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

    targets = urls if urls is not None else URLS
    for url in targets:
        try:
            with sync_playwright() as p:
                browser, context = default_playwright_context(p)
                page = context.new_page()
                page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
                page.wait_for_timeout(4000)
                _dismiss_cookies(page)
                page.wait_for_timeout(wait_after_load_ms)
                for _ in range(5):
                    page.evaluate("window.scrollBy(0, 800)")
                    page.wait_for_timeout(1200)

                rows = rows_td_vs_playwright(page, BOOK)
                if not rows:
                    rows = parse_body_lines_1x2(page.inner_text("body"), BOOK)
                context.close()
                browser.close()
                if rows:
                    return rows
        except Exception:
            continue
    return []


fetch_football_1x2 = fetch_football_two_way

if __name__ == "__main__":
    d = fetch_football_1x2()
    print("matches:", len(d))
