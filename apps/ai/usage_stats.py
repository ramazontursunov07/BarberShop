"""AI sarfi va sifati statistikasi (ChatTrace / LLMCall asosida). Narx faqat .env da narxlar berilsa hisoblanadi.

    LLM_PRICE_INPUT_PER_M=0.10     # 1 million kirish tokeni narxi (USD)
    LLM_PRICE_OUTPUT_PER_M=0.40    # 1 million chiqish tokeni narxi (USD)

Narxlarni provayderning joriy narxlar sahifasidan oling: ular tez-tez o'zgaradi, shuning uchun kodda yozilmagan.
"""
import math
from collections import Counter, defaultdict
from datetime import timedelta

from django.db.models import Q
from django.utils import timezone

from .llm import conf
from .models import ChatTrace, LLMCall

MAX_ROWS = 20000
PRICED_KINDS = {"chat", "insights", "vision"}  # matn/rasm modeli chaqiruvlari (embedding va ovoz alohida tarif)


def percentile(values, q: float):
    """Eng yaqin o'rin (nearest-rank) usulida foiz qiymati; bo'sh ro'yxatda None."""
    if not values:
        return None
    ordered = sorted(values)
    rank = max(1, math.ceil(round(q * len(ordered), 9)))
    return ordered[min(rank, len(ordered)) - 1]


def _price(name: str) -> float:
    try:
        return float(conf(name, "0") or 0)
    except ValueError:
        return 0.0


def cost_usd(prompt_tokens: int, completion_tokens: int):
    pin, pout = _price("LLM_PRICE_INPUT_PER_M"), _price("LLM_PRICE_OUTPUT_PER_M")
    if not pin and not pout:
        return None
    return round((prompt_tokens * pin + completion_tokens * pout) / 1_000_000, 6)


def _latency_summary(values):
    if not values:
        return {"avg": None, "p50": None, "p95": None}
    return {"avg": round(sum(values) / len(values)), "p50": percentile(values, 0.50), "p95": percentile(values, 0.95)}


def usage_stats(days: int = 7, include_eval: bool = False) -> dict:
    since = timezone.now() - timedelta(days=days)
    traces = ChatTrace.objects.filter(created_at__gte=since)
    calls = LLMCall.objects.filter(created_at__gte=since)
    if not include_eval:  # baholash (eval:...) izlari haqiqiy statistikani buzmasin
        traces = traces.filter(tag="")
        calls = calls.filter(Q(trace__isnull=True) | Q(trace__tag=""))

    trace_rows = list(traces.values("outcome", "route", "latency_ms", "llm_calls", "prompt_tokens",
                                    "completion_tokens", "tool_names", "guard_rejections", "created_at")[:MAX_ROWS])
    call_rows = list(calls.values("kind", "node", "model", "latency_ms", "prompt_tokens", "completion_tokens",
                                  "status", "created_at")[:MAX_ROWS])

    n = len(trace_rows)
    tools = Counter(name for row in trace_rows for name in row["tool_names"])
    chat = {
        "requests": n,
        "outcomes": dict(Counter(r["outcome"] for r in trace_rows)),
        "routes": dict(Counter(r["route"] or "-" for r in trace_rows)),
        "latency_ms": _latency_summary([r["latency_ms"] for r in trace_rows]),
        "avg_llm_calls": round(sum(r["llm_calls"] for r in trace_rows) / n, 2) if n else None,
        "avg_tokens": round(sum(r["prompt_tokens"] + r["completion_tokens"] for r in trace_rows) / n) if n else None,
        "guard_rejections": sum(r["guard_rejections"] for r in trace_rows),
        "tools": dict(tools.most_common()),
    }

    by_node: dict = defaultdict(lambda: {"calls": 0, "latencies": [], "prompt_tokens": 0, "completion_tokens": 0})
    by_kind = Counter()
    errors = rate_limited = 0
    for r in call_rows:
        slot = by_node[f"{r['kind']}:{r['node']}" if r["node"] else r["kind"]]
        slot["calls"] += 1
        slot["latencies"].append(r["latency_ms"])
        slot["prompt_tokens"] += r["prompt_tokens"]
        slot["completion_tokens"] += r["completion_tokens"]
        by_kind[r["kind"]] += 1
        errors += r["status"] == "error"
        rate_limited += r["status"] == "rate_limited"

    priced = [r for r in call_rows if r["kind"] in PRICED_KINDS]
    prompt = sum(r["prompt_tokens"] for r in call_rows)
    completion = sum(r["completion_tokens"] for r in call_rows)
    llm = {
        "calls": len(call_rows),
        "errors": errors,
        "rate_limited": rate_limited,
        "prompt_tokens": prompt,
        "completion_tokens": completion,
        "by_kind": dict(by_kind),
        "by_node": {
            name: {"calls": s["calls"], "latency_ms": _latency_summary(s["latencies"]),
                   "prompt_tokens": s["prompt_tokens"], "completion_tokens": s["completion_tokens"]}
            for name, s in sorted(by_node.items(), key=lambda kv: -kv[1]["calls"])
        },
        "cost_usd": cost_usd(sum(r["prompt_tokens"] for r in priced), sum(r["completion_tokens"] for r in priced)),
    }

    daily: dict = defaultdict(lambda: {"requests": 0, "tokens": 0})
    for r in trace_rows:
        day = timezone.localtime(r["created_at"]).date().isoformat()
        daily[day]["requests"] += 1
        daily[day]["tokens"] += r["prompt_tokens"] + r["completion_tokens"]

    return {
        "days": days,
        "since": since.isoformat(),
        "include_eval": include_eval,
        "chat": chat,
        "llm": llm,
        "daily": [{"date": d, **v} for d, v in sorted(daily.items())],
    }
