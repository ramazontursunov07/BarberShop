"""Dinamik narx: bo'sh vaqtlarga egasi belgilagan chegirma (PricingRule).

Narx hisoblash shu yerda bitta joyda: AI ham, REST API ham create_booking orqali shuni ishlatadi,
shuning uchun mijozga aytilgan narx bilan yozilgan narx har doim bir xil bo'ladi.
"""
from decimal import Decimal

from .models import PricingRule


def rule_matches(rule, weekday: int, hhmm) -> bool:
    if rule.weekday is not None and rule.weekday != weekday:
        return False
    return rule.start_time <= hhmm < rule.end_time


def discount_percent(shop_id: int, start_local) -> int:
    """start_local: sartaroshxona vaqt mintaqasidagi datetime. Mos qoidalarning eng kattasi (yoki 0)."""
    rules = PricingRule.objects.filter(shop_id=shop_id, is_active=True)
    best = 0
    for r in rules:
        if rule_matches(r, start_local.weekday(), start_local.time()):
            best = max(best, r.percent)
    return best


def apply_discount(price, percent: int) -> int:
    """Narxni so'm (1000 ga yaxlitlab) qaytaradi. Chegirma bo'lmasa narx o'zgarmaydi."""
    base = int(price)
    if percent <= 0:
        return base
    discounted = Decimal(base) * (100 - percent) / 100
    return max(int(round(discounted / 1000)) * 1000, 0) if base >= 1000 else int(discounted)
