"""Общи помощни функции за 1X2 редове (етикет + три коефициента)."""

from __future__ import annotations

import random
import re
from typing import Any

PLAYWRIGHT_USER_AGENTS: list[str] = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
]


def playwright_context_options(locale: str = "bg-BG") -> dict[str, Any]:
    """User-agent + viewport за по-малко headless-отпечатък (Railway/CDN)."""
    return {
        "user_agent": random.choice(PLAYWRIGHT_USER_AGENTS),
        "viewport": {"width": 1920, "height": 1080},
        "locale": locale,
    }


def page_soft_wait_selector(page: Any, selector: str, timeout_ms: int = 30_000) -> None:
    try:
        page.wait_for_selector(selector, timeout=timeout_ms)
    except Exception:
        pass

_ODDS_RE = re.compile(r"\d+[.,]\d{2,3}")

# Chromium в Docker / Railway (няма setuid sandbox, ограничен /dev/shm).
CHROMIUM_LAUNCH_ARGS: list[str] = [
    "--no-sandbox",
    "--disable-setuid-sandbox",
    "--disable-dev-shm-usage",
    "--disable-blink-features=AutomationControlled",
    "--ignore-certificate-errors",
    "--host-resolver-rules=MAP www.efbet.com 172.64.154.130, MAP efbet.com 172.64.154.130, MAP www.winbet.bg 172.64.146.5, MAP winbet.bg 172.64.146.5, MAP www.betano.bg 172.64.154.136, MAP betano.bg 172.64.154.136, MAP www.palmsbet.com 104.20.25.63, MAP palmsbet.com 104.20.25.63, MAP www.inbet.bg 193.107.37.51, MAP inbet.bg 193.107.37.51",
]


def normalize_match_label(home: str, away: str) -> str:
    h = re.sub(r"\s+", " ", home.strip()).lower()
    a = re.sub(r"\s+", " ", away.strip()).lower()
    return f"{h} vs {a}"


def is_junk_line_before_match(s: str) -> bool:
    """Редове между отборите и маркера „1“ (дата, час, лига, …)."""
    sl = s.lower()
    if s in ("Днес", "НА ЖИВО", "Резултат", "ПАЗАРИ", "ФУТБОЛ", "Акценти", "Турнири", "Предстоящи"):
        return True
    if re.match(r"^\d{1,2}/\d{1,2}", s):
        return True
    if re.match(r"^\d{1,2}:\d{2}", s):
        return True
    if re.fullmatch(r"\d+", s) and len(s) <= 2:
        return True
    if " - " in s and any(x in sl for x in ("лига", "купа", "шампион", "premier", "liga")):
        if len(s) > 12:
            return True
    return False


def is_probable_team_name(s: str) -> bool:
    if len(s) < 2 or len(s) > 80:
        return False
    sl = s.lower()
    if "неутрален" in sl:
        return False
    if "neutral" in sl and ("ground" in sl or "venue" in sl):
        return False
    if s in (
        "1",
        "2",
        "x",
        "X",
        "футбол",
        "днес",
        "на живо",
        "резултат",
        "резултат",
        "пазари",
    ):
        return False
    if re.fullmatch(r"\d+", s):
        return False
    if re.match(r"^\d{1,2}:\d{2}$", s):
        return False
    if re.match(r"^\d{1,2}/\d{1,2}/\d{2,4}$", s):
        return False
    if re.match(r"^\d+[.,]\d+$", s):  # само коефициент
        return False
    return True


def parse_body_lines_1x2(body_text: str, book: str) -> list[dict[str, Any]]:
    """
    Парсира плосък текст (редове): отбор1, отбор2, 1, odd, X, odd, 2, odd.
    Работи за част от Betano / други SPA, където няма стабилни td.
    """
    lines = [l.strip() for l in body_text.splitlines() if l.strip()]
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    i = 0
    while i < len(lines) - 7:
        t1, t2 = lines[i], lines[i + 1]
        if (
            lines[i + 2] == "1"
            and lines[i + 4].upper() == "X"
            and lines[i + 6] == "2"
            and is_probable_team_name(t1)
            and is_probable_team_name(t2)
        ):
            try:
                o1 = float(lines[i + 3].replace(",", "."))
                ox = float(lines[i + 5].replace(",", "."))
                o2 = float(lines[i + 7].replace(",", "."))
            except ValueError:
                i += 1
                continue
            if not (1.01 <= o1 <= 500.0 and 1.01 <= ox <= 500.0 and 1.01 <= o2 <= 500.0):
                i += 1
                continue
            label = normalize_match_label(t1, t2)
            key = label
            if key in seen:
                i += 1
                continue
            seen.add(key)
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
            i += 8
            continue
        i += 1
    return out


def parse_body_lines_1x2_backward(body_text: str, book: str) -> list[dict[str, Any]]:
    """
    Намира блокове … отбор1, отбор2, [junk], 1, odd, X, odd, 2, odd като търси „1“/„X“/„2“
    и върви нагоре за имената на отборите (прескача дата/час/лига).
    """
    lines = [l.strip() for l in body_text.splitlines() if l.strip()]
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
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
        j = i - 1
        names: list[str] = []
        while j >= 0 and len(names) < 2:
            s = lines[j]
            if is_probable_team_name(s):
                names.insert(0, s)
                j -= 1
            elif is_junk_line_before_match(s):
                j -= 1
            else:
                break
        if len(names) != 2:
            continue
        t1, t2 = names[0], names[1]
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


def merge_rows_by_label(
    *row_lists: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Обединява редове по label; при дубли последният списък има приоритет."""
    by_label: dict[str, dict[str, Any]] = {}
    for lst in row_lists:
        for r in lst:
            lab = r.get("label")
            if not lab:
                continue
            by_label[lab] = r
    return list(by_label.values())


def merge_rows_by_label_casefold(
    *row_lists: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Като merge_rows_by_label, но ключът е casefold — „Арсенал vs X“ = „арсенал vs x“."""
    by_label: dict[str, dict[str, Any]] = {}
    for lst in row_lists:
        for r in lst:
            lab = r.get("label")
            if not lab:
                continue
            k = str(lab).strip().casefold()
            if not k:
                continue
            by_label[k] = r
    return list(by_label.values())


def scroll_to_bottom_stable(
    page: Any,
    pause_ms: int = 1000,
    max_rounds: int = 45,
    stable_needed: int = 3,
) -> None:
    """scrollTo(0, scrollHeight) в цикъл с пауза, докато височината спре да расте."""
    last_h = 0
    stable = 0
    for _ in range(max_rounds):
        page.evaluate("() => window.scrollTo(0, document.body.scrollHeight)")
        page.wait_for_timeout(pause_ms)
        h = page.evaluate("() => document.body.scrollHeight")
        if h == last_h:
            stable += 1
            if stable >= stable_needed:
                break
        else:
            stable = 0
        last_h = h


def rows_td_vs_playwright(page: Any, book: str) -> list[dict[str, Any]]:
    """Модел efbet: td > a с текст „... vs ...“ и три коефициента в същия tr."""
    out: list[dict[str, Any]] = []
    seen: set[str] = set()

    for link in page.locator("td a").all():
        try:
            raw_label = link.inner_text().strip()
        except Exception:
            continue
        if " vs " not in raw_label.lower() or len(raw_label) < 5:
            continue

        row = link.locator("xpath=ancestor::tr[1]")
        try:
            row_text = row.inner_text()
        except Exception:
            continue

        idx = row_text.find(raw_label)
        if idx == -1:
            idx = row_text.lower().find(raw_label.lower())
        if idx == -1:
            continue
        tail = row_text[idx + len(raw_label) :]
        raw = _ODDS_RE.findall(tail)
        vals: list[float] = []
        for s in raw:
            v = float(s.replace(",", "."))
            if 1.01 <= v <= 500.0:
                vals.append(v)
            if len(vals) >= 3:
                break
        if len(vals) < 3:
            continue
        o1, ox, o2 = vals[0], vals[1], vals[2]
        parts = re.split(r"\s+vs\s+", raw_label, maxsplit=1, flags=re.I)
        if len(parts) != 2:
            continue
        label = normalize_match_label(parts[0], parts[1])
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


def default_playwright_context(p: Any, locale: str = "bg-BG", headless: bool = True):
    browser = p.chromium.launch(
        headless=headless,
        args=CHROMIUM_LAUNCH_ARGS,
    )
    context = browser.new_context(**playwright_context_options(locale=locale))
    return browser, context
