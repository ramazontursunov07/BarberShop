"""AI agent javoblarini baholash: sof Python (Django ham, LLM ham kerak emas).

Har bir "tur" (foydalanuvchi xabari) uchun kutilgan xatti-harakat `expect` lug'atida yoziladi,
`score_turn` esa agent haqiqatda nima qilganini (qaysi tool'larni chaqirdi, nima javob berdi)
shu kutilganga solishtirib, tekshiruvlar (Check) ro'yxatini qaytaradi.
"""
import re
from dataclasses import dataclass, field

# Tekshiruv turkumlari: hisobotda har biri bo'yicha alohida foiz chiqadi
TOOL_SELECTION = "tool_selection"  # to'g'ri tool tanlandimi
ARGUMENTS = "arguments"            # argumentlar to'g'rimi
SAFETY = "safety"                  # xavfli/ruxsatsiz amal qilinmadimi
LANGUAGE = "language"              # mijoz tilida javob berildimi
CONTENT = "content"                # javob mazmuni to'g'rimi
RECOVERY = "recovery"              # tool xato qaytarganda to'g'ri ish tutildimi

CATEGORIES = [TOOL_SELECTION, ARGUMENTS, SAFETY, LANGUAGE, CONTENT, RECOVERY]

ALLOWED_EXPECT_KEYS = {
    "must_call",            # [tool, ...]  hammasi chaqirilishi kerak
    "must_call_any",        # [tool, ...]  kamida bittasi chaqirilishi kerak
    "must_not_call",        # [tool, ...]  birortasi ham chaqirilmasligi kerak
    "no_tools",             # True: umuman tool chaqirilmasligi kerak
    "no_successful",        # [tool, ...]  bu tool'lar muvaffaqiyatli bajarilmasligi kerak
    "calls",                # [{"tool":..., "args": {...}, "ok": bool}, ...]
    "reply_lang",           # "uz" | "ru"
    "reply_contains_any",   # [matn, ...]  birortasi javobda bo'lishi kerak
    "reply_contains_all",   # [matn, ...]  hammasi javobda bo'lishi kerak
    "reply_not_contains",   # [matn, ...]  birortasi ham javobda bo'lmasligi kerak
}
ALLOWED_STATE_KEYS = {"created_bookings", "status"}


@dataclass
class Check:
    name: str
    category: str
    passed: bool
    detail: str = ""


@dataclass
class CaseResult:
    case_id: str
    tags: list
    checks: list = field(default_factory=list)
    error: str = ""
    latency_s: float = 0.0
    tool_calls: int = 0
    turns: list = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return not self.error and all(c.passed for c in self.checks)

    def failures(self) -> list:
        return [c for c in self.checks if not c.passed]

    def to_dict(self) -> dict:
        return {
            "id": self.case_id,
            "tags": self.tags,
            "passed": self.passed,
            "error": self.error,
            "latency_s": round(self.latency_s, 2),
            "tool_calls": self.tool_calls,
            "checks": [
                {"name": c.name, "category": c.category, "passed": c.passed, "detail": c.detail}
                for c in self.checks
            ],
            "turns": self.turns,
        }


# ------------------------------------------------------------------ yordamchilar

_TIME_RE = re.compile(r"^(\d{1,2}):(\d{2})(?::\d{2})?$")


def _norm_time(value: str) -> str:
    """'9:00' / '09:00:00' -> '09:00' (vaqt bo'lmasa o'zgarishsiz)."""
    m = _TIME_RE.match(value.strip())
    return f"{int(m.group(1)):02d}:{m.group(2)}" if m else value.strip()


def cyrillic_ratio(text: str) -> float:
    letters = [ch for ch in text if ch.isalpha()]
    if not letters:
        return 0.0
    return sum(1 for ch in letters if "\u0400" <= ch <= "\u04ff") / len(letters)


def _match_value(actual, expected, ids: dict) -> bool:
    """Kutilgan qiymat: oddiy qiymat, belgi ('@master:Jasur'), yoki variantlar ro'yxati (istalgani)."""
    if isinstance(expected, list):
        return any(_match_value(actual, e, ids) for e in expected)
    if isinstance(expected, str):
        expected = ids.get(expected, expected)
    if isinstance(expected, bool) or isinstance(actual, bool):
        return actual == expected
    if isinstance(expected, int):
        try:
            return int(actual) == expected
        except (TypeError, ValueError):
            return False
    if isinstance(expected, str) and isinstance(actual, str):
        return _norm_time(actual).lower() == _norm_time(expected).lower()
    return actual == expected


def _is_error(result) -> bool:
    return isinstance(result, dict) and "error" in result


def _call_matches(call: dict, spec: dict, ids: dict) -> bool:
    if call["name"] != spec["tool"]:
        return False
    args = call.get("arguments") or {}
    for key, expected in (spec.get("args") or {}).items():
        if key not in args or not _match_value(args[key], expected, ids):
            return False
    if "ok" in spec and (not _is_error(call.get("result"))) != bool(spec["ok"]):
        return False
    return True


def _describe_calls(calls: list, tool: str) -> str:
    own = [c for c in calls if c["name"] == tool]
    if not own:
        return f"{tool} chaqirilmadi (chaqirilganlar: {[c['name'] for c in calls]})"
    return "; ".join(f"{c['name']}({c.get('arguments')}) -> {str(c.get('result'))[:120]}" for c in own)


# ------------------------------------------------------------------ asosiy baholash

def score_turn(expect: dict, reply: str, calls: list, ids: dict | None = None) -> list:
    """Bitta tur uchun tekshiruvlar. calls: [{"name", "arguments", "result"}, ...]"""
    ids = ids or {}
    names = [c["name"] for c in calls]
    low = (reply or "").lower()
    checks: list = []

    def add(name, category, ok, detail=""):
        checks.append(Check(name, category, bool(ok), "" if ok else detail))

    add("javob bo'sh emas", CONTENT, bool((reply or "").strip()), "agent bo'sh javob qaytardi")

    for tool in expect.get("must_call", []):
        add(f"{tool} chaqirilishi kerak", TOOL_SELECTION, tool in names, f"chaqirilganlar: {names}")

    any_of = expect.get("must_call_any")
    if any_of:
        add(f"{' / '.join(any_of)} dan biri chaqirilishi kerak", TOOL_SELECTION,
            any(t in names for t in any_of), f"chaqirilganlar: {names}")

    if expect.get("no_tools"):
        add("tool chaqirilmasligi kerak", TOOL_SELECTION, not names, f"chaqirilganlar: {names}")

    for tool in expect.get("must_not_call", []):
        add(f"{tool} chaqirilmasligi kerak", SAFETY, tool not in names, _describe_calls(calls, tool))

    for tool in expect.get("no_successful", []):
        succeeded = [c for c in calls if c["name"] == tool and not _is_error(c.get("result"))]
        add(f"{tool} muvaffaqiyatli bajarilmasligi kerak", SAFETY, not succeeded, _describe_calls(calls, tool))

    for spec in expect.get("calls", []):
        ok_flag = spec.get("ok")
        category = RECOVERY if ok_flag is False else ARGUMENTS
        label = f"{spec['tool']} to'g'ri argumentlar bilan chaqirilishi kerak"
        if ok_flag is False:
            label = f"{spec['tool']} xato qaytarishi va agent buni to'g'ri hal qilishi kerak"
        matched = any(_call_matches(c, spec, ids) for c in calls)
        add(label, category, matched, f"kutilgan: {_resolved_spec(spec, ids)}; haqiqatda: {_describe_calls(calls, spec['tool'])}")

    lang = expect.get("reply_lang")
    if lang:
        ratio = cyrillic_ratio(reply or "")
        ok = ratio < 0.2 if lang == "uz" else ratio > 0.6
        add(f"javob tili: {lang}", LANGUAGE, ok, f"kirill harflari ulushi {ratio:.0%}")

    any_text = expect.get("reply_contains_any")
    if any_text:
        add(f"javobda bulardan biri bo'lishi kerak: {any_text}", CONTENT,
            any(t.lower() in low for t in any_text), f"javob: {(reply or '')[:160]!r}")

    all_text = expect.get("reply_contains_all")
    if all_text:
        missing = [t for t in all_text if t.lower() not in low]
        add(f"javobda hammasi bo'lishi kerak: {all_text}", CONTENT, not missing, f"yo'q: {missing}")

    bad_text = expect.get("reply_not_contains")
    if bad_text:
        found = [t for t in bad_text if t.lower() in low]
        add(f"javobda bular bo'lmasligi kerak: {bad_text}", SAFETY, not found, f"topildi: {found}")

    return checks


def _resolved_spec(spec: dict, ids: dict) -> dict:
    args = {k: (ids.get(v, v) if isinstance(v, str) else v) for k, v in (spec.get("args") or {}).items()}
    out = {"tool": spec["tool"], "args": args}
    if "ok" in spec:
        out["ok"] = spec["ok"]
    return out


# ------------------------------------------------------------------ to'plamni tekshirish

def validate_cases(cases: list, known_setups: set) -> list:
    """Ma'lumotlar to'plamidagi xatolar ro'yxati (bo'sh ro'yxat = hammasi joyida)."""
    problems = []
    seen = set()
    for case in cases:
        cid = case.get("id")
        if not cid or not isinstance(cid, str):
            problems.append(f"id yo'q yoki noto'g'ri: {case!r}"[:120])
            continue
        if cid in seen:
            problems.append(f"{cid}: id takrorlangan")
        seen.add(cid)
        if not case.get("tags"):
            problems.append(f"{cid}: tags bo'sh")
        for setup in case.get("setup", []):
            if setup not in known_setups:
                problems.append(f"{cid}: noma'lum setup '{setup}'")
        turns = case.get("turns")
        if not turns:
            problems.append(f"{cid}: turns bo'sh")
            continue
        for i, turn in enumerate(turns, 1):
            if not isinstance(turn.get("say"), str) or not turn["say"].strip():
                problems.append(f"{cid}: {i}-turda 'say' yo'q")
            unknown = set(turn.get("expect", {})) - ALLOWED_EXPECT_KEYS
            if unknown:
                problems.append(f"{cid}: {i}-turda noma'lum kalitlar {sorted(unknown)}")
            for spec in turn.get("expect", {}).get("calls", []):
                if "tool" not in spec:
                    problems.append(f"{cid}: {i}-turda calls ichida 'tool' yo'q")
        unknown_state = set(case.get("state", {})) - ALLOWED_STATE_KEYS
        if unknown_state:
            problems.append(f"{cid}: noma'lum state kalitlari {sorted(unknown_state)}")
    return problems


# ------------------------------------------------------------------ yig'ma hisobot

def summarize(results: list) -> dict:
    total = len(results)
    passed = sum(1 for r in results if r.passed)

    by_category = {}
    for cat in CATEGORIES:
        checks = [c for r in results for c in r.checks if c.category == cat]
        if checks:
            ok = sum(1 for c in checks if c.passed)
            by_category[cat] = {"passed": ok, "total": len(checks), "rate": ok / len(checks)}

    by_tag = {}
    for r in results:
        for tag in r.tags:
            slot = by_tag.setdefault(tag, {"passed": 0, "total": 0})
            slot["total"] += 1
            slot["passed"] += 1 if r.passed else 0

    latencies = [r.latency_s for r in results if r.latency_s]
    return {
        "total": total,
        "passed": passed,
        "pass_rate": passed / total if total else 0.0,
        "by_category": by_category,
        "by_tag": by_tag,
        "avg_latency_s": sum(latencies) / len(latencies) if latencies else 0.0,
        "avg_tool_calls": sum(r.tool_calls for r in results) / total if total else 0.0,
    }


_CATEGORY_TITLES = {
    TOOL_SELECTION: "Tool tanlash",
    ARGUMENTS: "Argumentlar aniqligi",
    SAFETY: "Xavfsizlik",
    LANGUAGE: "Til (mijoz tilida javob)",
    CONTENT: "Javob mazmuni",
    RECOVERY: "Xatoni to'g'ri hal qilish",
}


def render_markdown(summary: dict, results: list, meta: dict) -> str:
    lines = ["# Agent baholash hisoboti", ""]
    for key in ("sana", "model", "engine", "eslatma"):
        if meta.get(key):
            lines.append(f"- **{key}**: {meta[key]}")
    lines += [
        "",
        f"**Umumiy natija: {summary['passed']}/{summary['total']} holat o'tdi "
        f"({summary['pass_rate']:.0%})**",
        f"O'rtacha javob vaqti: {summary['avg_latency_s']:.1f} s, "
        f"holat boshiga o'rtacha tool chaqiruvi: {summary['avg_tool_calls']:.1f}",
        "",
        "## Turkumlar bo'yicha",
        "",
        "| Turkum | O'tdi | Jami | Foiz |",
        "|---|---|---|---|",
    ]
    for cat in CATEGORIES:
        row = summary["by_category"].get(cat)
        if row:
            lines.append(f"| {_CATEGORY_TITLES[cat]} | {row['passed']} | {row['total']} | {row['rate']:.0%} |")

    lines += ["", "## Teglar bo'yicha", "", "| Teg | O'tdi | Jami |", "|---|---|---|"]
    for tag, row in sorted(summary["by_tag"].items()):
        lines.append(f"| {tag} | {row['passed']} | {row['total']} |")

    lines += ["", "## Holatlar", "", "| Holat | Natija | Vaqt |", "|---|---|---|"]
    for r in results:
        status = "✅" if r.passed else ("⚠️ xato" if r.error else "❌")
        lines.append(f"| {r.case_id} | {status} | {r.latency_s:.1f} s |")

    failed = [r for r in results if not r.passed]
    if failed:
        lines += ["", "## O'tmagan holatlar", ""]
        for r in failed:
            lines.append(f"### {r.case_id}")
            if r.error:
                lines.append(f"- XATO: {r.error}")
            for c in r.failures():
                lines.append(f"- {c.name}: {c.detail}")
            for t in r.turns:
                lines.append(f"- Mijoz: {t.get('say')}")
                names = [x["name"] if isinstance(x, dict) else str(x) for x in (t.get("tools") or [])]
                lines.append(f"  - chaqirilgan tool'lar: {', '.join(names) or 'hech biri'}")
                lines.append(f"  - agent javobi: {(t.get('reply') or '')[:400]!r}")
            lines.append("")
    return "\n".join(lines) + "\n"
