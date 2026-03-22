"""
Сравнява 1X2 коефициенти между активните букмейкъри (efbet, winbet, Betano, Palms Bet)
и търси арбитраж (за всеки изход — максималният коефициент сред наличните къщи за същия мач).

Inbet, Sesame и bet365 са изключени (Cloudflare/SPA).
"""

from __future__ import annotations

import re
import unicodedata
from concurrent.futures import ThreadPoolExecutor, as_completed
from difflib import SequenceMatcher
from typing import Any, Callable

from calculator import (
    implied_sum_1x2,
    is_arbitrage_1x2,
    profit_margin_percent_1x2,
    profit_tier_class,
    stakes_1x2_for_total,
)
from scrapers.betano import fetch_football_two_way as fetch_betano
from scrapers.efbet import fetch_football_for_scan as fetch_efbet
from scrapers.palmsbet import fetch_football_two_way as fetch_palmsbet
from scrapers.winbet import fetch_football_for_scan as fetch_winbet

# Минимално съотношение на SequenceMatcher за „същият отбор“ между сайтове.
FUZZY_TEAM_RATIO = 0.80

# Прагове за UI (и подсказка в API); филтрирането по минимум е в браузъра.
MIN_PROFIT_PERCENT = 1.5
HOT_PROFIT_PERCENT = 3.0

BOOK_ORDER: list[tuple[str, Callable[[], list[dict]]]] = [
    ("efbet", fetch_efbet),
    ("winbet", fetch_winbet),
    ("betano", fetch_betano),
    ("palmsbet", fetch_palmsbet),
]


def strip_diacritics(s: str) -> str:
    """Премахва комбиниращи знаци (латински акценти; частично помага и при кирилица)."""
    normalized = unicodedata.normalize("NFD", s)
    return "".join(c for c in normalized if unicodedata.category(c) != "Mn")


def normalize_team_for_fuzzy(name: str) -> str:
    """
    Нормализация за difflib: малки букви, без диакритика, тирета/дълги тирета → интервал.
    (ЦСКА-София → cska sofia при латинска транслитерация няма — остава кирилица без акценти.)
    """
    s = strip_diacritics(name.strip()).lower()
    s = re.sub(r"[\u2013\u2014\-_/]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def split_match_label(label: str) -> tuple[str, str] | None:
    """Домакин и гост: vs, v/s, единичен дефис (само ако няма „vs“)."""
    s = label.strip()
    if not s:
        return None
    marker = "\x00"
    t = re.sub(r"\s+vs\.?\s+", marker, s, flags=re.IGNORECASE)
    t = re.sub(r"\s+v/s\s+", marker, t, flags=re.IGNORECASE)
    if marker in t:
        parts = t.split(marker, 1)
        if len(parts) == 2 and parts[0].strip() and parts[1].strip():
            return parts[0].strip(), parts[1].strip()
    low = s.lower()
    if " vs " in low:
        i = low.index(" vs ")
        a, b = s[:i].strip(), s[i + 5 :].strip()
        if a and b:
            return a, b
    if "|" in s:
        parts = [p.strip() for p in s.split("|", 1)]
        if len(parts) == 2 and parts[0] and parts[1]:
            return parts[0], parts[1]
    if "vs" not in low and s.count("-") == 1:
        a, b = s.split("-", 1)
        if a.strip() and b.strip():
            return a.strip(), b.strip()
    return None


def teams_fuzzy_equal(a: str, b: str, threshold: float = FUZZY_TEAM_RATIO) -> bool:
    if a == b:
        return True
    if not a or not b:
        return False
    return SequenceMatcher(None, a, b).ratio() >= threshold


def same_fixture_ordered(
    h1: str,
    a1: str,
    h2: str,
    a2: str,
    threshold: float = FUZZY_TEAM_RATIO,
) -> bool:
    """Същият мач със същия ред домакин/гост (без размяна — коефициентите 1/2 са по сайт)."""
    return teams_fuzzy_equal(h1, h2, threshold) and teams_fuzzy_equal(a1, a2, threshold)


def _canonical_cluster_key(hf: str, af: str) -> str:
    return f"{hf}\x1f{af}"


def _index_by_fuzzy_match(
    rows_by_book: dict[str, list[dict]],
) -> tuple[dict[str, dict[str, dict]], list[dict[str, Any]]]:
    """
    Обединява редове от различни сайтове в един мач чрез fuzzy съвпадение на двата отбора.
    Връща (match_key -> {book -> row}, списък за отчет с ≥2 къщи).
    """
    entries: list[tuple[str, dict, str, str, str, str]] = []
    for book_id, rows in rows_by_book.items():
        for r in rows:
            lab = r.get("label", "")
            sp = split_match_label(str(lab))
            if not sp:
                continue
            h_raw, a_raw = sp
            hf = normalize_team_for_fuzzy(h_raw)
            af = normalize_team_for_fuzzy(a_raw)
            if not hf or not af:
                continue
            entries.append((book_id, r, h_raw, a_raw, hf, af))

    n = len(entries)
    parent = list(range(n))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(i: int, j: int) -> None:
        ri, rj = find(i), find(j)
        if ri != rj:
            parent[rj] = ri

    for i in range(n):
        for j in range(i + 1, n):
            hi, ai = entries[i][4], entries[i][5]
            hj, aj = entries[j][4], entries[j][5]
            if same_fixture_ordered(hi, ai, hj, aj):
                union(i, j)

    clusters: dict[int, list[int]] = {}
    for i in range(n):
        root = find(i)
        clusters.setdefault(root, []).append(i)

    by_key: dict[str, dict[str, dict]] = {}
    pairing_report: list[dict[str, Any]] = []

    for _root, indices in clusters.items():
        hi_ai = min((entries[i][4], entries[i][5]) for i in indices)
        hf, af = hi_ai
        key = _canonical_cluster_key(hf, af)
        book_to_row: dict[str, dict] = {}
        labels_by_book: dict[str, str] = {}
        for i in indices:
            bid, row, h_raw, a_raw, _, _ = entries[i]
            book_to_row[bid] = row
            labels_by_book[bid] = row.get("label", f"{h_raw} vs {a_raw}")

        by_key[key] = book_to_row

        books_distinct = set(labels_by_book.keys())
        if len(books_distinct) >= 2:
            pairing_report.append(
                {
                    "canonical_home_away": f"{hf} | {af}",
                    "labels_by_book": dict(sorted(labels_by_book.items())),
                    "books_count": len(books_distinct),
                }
            )

    pairing_report.sort(key=lambda x: x["canonical_home_away"])
    return by_key, pairing_report


def _best_among(pairs: list[tuple[float, str]]) -> tuple[float, str]:
    return max(pairs, key=lambda t: t[0])


def _display_book(book_id: str) -> str:
    return {
        "efbet": "efbet",
        "winbet": "winbet",
        "betano": "Betano",
        "palmsbet": "Palms Bet",
    }.get(book_id, book_id)


def _fmt_betting_plan(
    book1: str,
    book_x: str,
    book2: str,
    s1: float,
    sx: float,
    s2: float,
    total: float = 100.0,
) -> tuple[str, float, float, float]:
    r1 = round(s1, 2)
    rx = round(sx, 2)
    r2 = round(total - r1 - rx, 2)
    b1, bx, b2 = _display_book(book1), _display_book(book_x), _display_book(book2)
    text = (
        f"{b1}: €{r1:.2f} на 1 · {bx}: €{rx:.2f} на X · "
        f"{b2}: €{r2:.2f} на 2 · общо €{total:.0f}"
    )
    return text, r1, rx, r2


def _fetch_all_books() -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {bid: [] for bid, _ in BOOK_ORDER}
    with ThreadPoolExecutor(max_workers=len(BOOK_ORDER)) as pool:
        futures = {pool.submit(fn): bid for bid, fn in BOOK_ORDER}
        for fut in as_completed(futures):
            bid = futures[fut]
            try:
                rows = fut.result()
            except Exception:
                rows = []
            out[bid] = rows if isinstance(rows, list) else []
    return out


def _display_label_for_key(key: str, books_map: dict[str, dict]) -> str:
    for bid, _ in BOOK_ORDER:
        if bid in books_map:
            return str(books_map[bid].get("label", key))
    return key


def _all_matches_payload(
    by_key: dict[str, dict[str, dict]],
) -> list[dict[str, Any]]:
    """Всеки fuzzy-клъстер с покритие по букмейкъри и коефициенти (за UI)."""
    book_ids = [bid for bid, _ in BOOK_ORDER]
    rows_out: list[dict[str, Any]] = []

    def sort_key(k: str) -> str:
        bm = by_key[k]
        return _display_label_for_key(k, bm).lower()

    for key in sorted(by_key.keys(), key=sort_key):
        bm = by_key[key]
        label = _display_label_for_key(key, bm)
        books: dict[str, Any] = {}
        for bid in book_ids:
            if bid in bm:
                r = bm[bid]
                books[bid] = {
                    "site_label": r.get("label", ""),
                    "odd_1": r.get("odd_1"),
                    "odd_x": r.get("odd_x"),
                    "odd_2": r.get("odd_2"),
                }
            else:
                books[bid] = None
        rows_out.append(
            {
                "label": label,
                "books": books,
                "coverage_count": len(bm),
            }
        )
    return rows_out


def run_scan() -> dict[str, Any]:
    rows_by_book = _fetch_all_books()
    book_match_counts = {bid: len(rows_by_book.get(bid, [])) for bid, _ in BOOK_ORDER}

    by_key, pairing_report = _index_by_fuzzy_match(rows_by_book)
    multi_book_keys = [k for k, m in by_key.items() if len(m) >= 2]

    opportunities: list[dict[str, Any]] = []
    for key in sorted(multi_book_keys):
        bm = by_key[key]
        c1 = [(bm[b]["odd_1"], b) for b in bm if "odd_1" in bm[b]]
        cx = [(bm[b]["odd_x"], b) for b in bm if "odd_x" in bm[b]]
        c2 = [(bm[b]["odd_2"], b) for b in bm if "odd_2" in bm[b]]
        if len(c1) < 2 or len(cx) < 2 or len(c2) < 2:
            continue

        b1, book1 = _best_among(c1)
        bx, book_x = _best_among(cx)
        b2, book2 = _best_among(c2)

        if not is_arbitrage_1x2(b1, bx, b2):
            continue

        margin = implied_sum_1x2(b1, bx, b2)
        profit = profit_margin_percent_1x2(b1, bx, b2)
        s1, sx, s2 = stakes_1x2_for_total(100.0, b1, bx, b2)
        plan, r1, rx, r2 = _fmt_betting_plan(book1, book_x, book2, s1, sx, s2, 100.0)
        tier = profit_tier_class(profit)
        match_label = _display_label_for_key(key, bm)

        opportunities.append(
            {
                "match": match_label,
                "book_1": _display_book(book1),
                "book_1_id": book1,
                "odd_1": round(b1, 4),
                "book_x": _display_book(book_x),
                "book_x_id": book_x,
                "odd_x": round(bx, 4),
                "book_2": _display_book(book2),
                "book_2_id": book2,
                "odd_2": round(b2, 4),
                "profit_percent": round(profit, 2),
                "profit_tier": tier,
                "implied_sum": round(margin, 4),
                "betting_plan": plan,
                "stake_1_eur": r1,
                "stake_x_eur": rx,
                "stake_2_eur": r2,
                "books_matched_count": len(bm),
            }
        )

    return {
        "book_match_counts": book_match_counts,
        "unique_matches_indexed": len(by_key),
        "cross_book_matches": len(multi_book_keys),
        "pairing_report": pairing_report,
        "all_matches": _all_matches_payload(by_key),
        "opportunities": opportunities,
        "opportunities_count": len(opportunities),
        "min_profit_percent_default": MIN_PROFIT_PERCENT,
        "hot_profit_percent_default": HOT_PROFIT_PERCENT,
    }


def main() -> None:
    print("Сканиране (efbet, winbet, Betano, Palms Bet)…")
    data = run_scan()
    bc = data["book_match_counts"]
    print(
        "\nМачове по сайт: "
        + ", ".join(f"{k}={bc[k]}" for k, _ in BOOK_ORDER)
    )
    print(
        f"Уникални мачове (след fuzzy клъстер): {data['unique_matches_indexed']}, "
        f"сдвоени между ≥2 къщи: {data['cross_book_matches']}"
    )
    report = data.get("pairing_report") or []
    print(f"\nСдвоени мачове (fuzzy ≥{int(FUZZY_TEAM_RATIO * 100)}% по отбор) — {len(report)} бр.:")
    print("—" * 72)
    for item in report:
        print(f"  Канон: {item['canonical_home_away']}")
        for bid, lab in item["labels_by_book"].items():
            print(f"    {_display_book(bid)}: {lab}")
        print()
    print("—" * 72)
    print(
        f"\nАрбитраж 1X2 (показани ≥ {MIN_PROFIT_PERCENT}%, „горещи“ ≥ {HOT_PROFIT_PERCENT}%):\n"
    )

    vis = [o for o in data["opportunities"] if o["profit_percent"] >= MIN_PROFIT_PERCENT]
    vis.sort(
        key=lambda o: (
            0 if o["profit_percent"] >= HOT_PROFIT_PERCENT else 1,
            -o["profit_percent"],
        )
    )

    for op in vis:
        hot = op["profit_percent"] >= HOT_PROFIT_PERCENT
        mark = "🔥 " if hot else "   "
        print(f"  {mark}{op['match']}")
        print(
            f"    1: {op['book_1']} ({op['odd_1']:.2f})  |  X: {op['book_x']} ({op['odd_x']:.2f})  |  "
            f"2: {op['book_2']} ({op['odd_2']:.2f})"
        )
        print(f"    ~{op['profit_percent']:.2f}%  |  {op['betting_plan']}\n")

    if not data["opportunities"]:
        print("  (няма 1X2 арбитраж при текущите коефициенти и сдвоявания)")
    elif not vis:
        print(f"  (няма арбитражи над минималния праг {MIN_PROFIT_PERCENT}%)")
    hidden = len(data["opportunities"]) - len(vis)
    if hidden > 0:
        print(f"  [Скрити {hidden} възможности под {MIN_PROFIT_PERCENT}%]\n")


if __name__ == "__main__":
    main()
