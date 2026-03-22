"""Арбитраж: двупосочен (1/k1+1/k2) и троен 1X2 (1/k1+1/kx+1/k2)."""


def is_arbitrage(odd1: float, odd2: float) -> bool:
    if odd1 <= 1.0 or odd2 <= 1.0:
        return False
    return (1.0 / odd1 + 1.0 / odd2) < 1.0


def implied_sum(odd1: float, odd2: float) -> float:
    """Сума на имплицитните вероятности (ако < 1, има арбитраж)."""
    return 1.0 / odd1 + 1.0 / odd2


def profit_margin_percent(odd1: float, odd2: float) -> float:
    """Приблизителна печалба при равномерно хеджиране, в % от оборота."""
    s = implied_sum(odd1, odd2)
    if s >= 1.0:
        return 0.0
    return (1.0 / s - 1.0) * 100.0


def implied_sum_1x2(odd1: float, odd_x: float, odd2: float) -> float:
    """Сума на имплицитните вероятности за 1, X, 2."""
    return 1.0 / odd1 + 1.0 / odd_x + 1.0 / odd2


def is_arbitrage_1x2(odd1: float, odd_x: float, odd2: float) -> bool:
    if odd1 <= 1.0 or odd_x <= 1.0 or odd2 <= 1.0:
        return False
    return implied_sum_1x2(odd1, odd_x, odd2) < 1.0


def profit_margin_percent_1x2(odd1: float, odd_x: float, odd2: float) -> float:
    """Приблизителна „възвръщаемост“ при оптимално разпределение (като 1/sum - 1)."""
    s = implied_sum_1x2(odd1, odd_x, odd2)
    if s >= 1.0:
        return 0.0
    return (1.0 / s - 1.0) * 100.0


def stakes_1x2_for_total(
    total_stake: float, odd1: float, odd_x: float, odd2: float
) -> tuple[float, float, float]:
    """
    Залози по трите крака при общ оборот total_stake, така че изплащането да е еднакво
    при печалба на 1, X или 2 (класически арбитраж).
    """
    s = implied_sum_1x2(odd1, odd_x, odd2)
    return (
        total_stake * (1.0 / odd1) / s,
        total_stake * (1.0 / odd_x) / s,
        total_stake * (1.0 / odd2) / s,
    )


def profit_tier_class(profit_percent: float) -> str:
    """За UI: high > 2%, mid 1–2%, low < 1%."""
    if profit_percent > 2.0:
        return "high"
    if profit_percent >= 1.0:
        return "mid"
    return "low"
