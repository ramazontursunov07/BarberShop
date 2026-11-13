"""Baholash runner'i: agentni haqiqiy LLM bilan demo ma'lumot ustida ishga tushiradi.

Xavfsizlik: baholash uchun ALOHIDA vaqtinchalik foydalanuvchilar yaratiladi (eval_client, eval_other).
Agent faqat shu foydalanuvchi nomidan ishlaydi, har bir holatdan keyin ularning bronlari o'chiriladi,
oxirida foydalanuvchilarning o'zi ham o'chadi. Sizning haqiqiy ma'lumotlaringizga tegilmaydi.
"""
import time
from contextlib import ExitStack, contextmanager
from datetime import date, datetime, timedelta
from importlib import import_module
from unittest import mock

from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.bookings.models import Booking
from apps.bookings.services import SHOP_TZ
from apps.masters.models import Master
from apps.services.models import Service

from .. import observability
from ..tools import record_tool_calls
from .ratelimit import describe_error
from .scoring import SAFETY, CaseResult, Check, score_turn

EVAL_CLIENT_PHONE = "+998909999901"
EVAL_OTHER_PHONE = "+998909999902"


def eval_today(today: date | None = None) -> date:
    """Baholash "bugun"i: eng yaqin Dushanba (bugun Dushanba bo'lsa, bugunning o'zi).

    Shunda "ertaga" har doim Seshanba bo'ladi (ustalar ishlaydi) va natijalar
    qaysi kuni ishga tushirilganingizga bog'liq bo'lmaydi.
    """
    today = today or date.today()
    return today + timedelta(days=(7 - today.weekday()) % 7)


@contextmanager
def fixed_today(day: date):
    """Prompt'dagi "Bugungi sana"ni qotirib qo'yadi (graph.py va agent.py ichidagi date.today())."""

    class FixedDate(date):
        @classmethod
        def today(cls):
            return day

    with ExitStack() as stack:
        for module_name in ("apps.ai.graph", "apps.ai.agent"):
            try:
                module = import_module(module_name)
            except ImportError:
                continue
            if hasattr(module, "date"):
                stack.enter_context(mock.patch.object(module, "date", FixedDate))
        yield


class _SafeDict(dict):
    def __missing__(self, key):
        return "{" + key + "}"


class EvalEnv:
    def __init__(self):
        User = get_user_model()
        self.User = User
        self.today = eval_today()
        try:
            self.services = {s.name: s for s in Service.objects.filter(shop__name="Demo Barbershop")}
            self.masters = {
                m.user.first_name: m
                for m in Master.objects.filter(shop__name="Demo Barbershop").select_related("user")
            }
        except Exception as exc:  # pragma: no cover
            raise SystemExit(f"Demo ma'lumot o'qilmadi: {exc}")
        for name in ("Soch olish", "Soqol olish", "Soch + soqol"):
            if name not in self.services:
                raise SystemExit("Demo ma'lumot topilmadi. Avval: python manage.py seed_demo")
        for name in ("Jasur", "Bobur"):
            if name not in self.masters:
                raise SystemExit("Demo ustalar topilmadi. Avval: python manage.py seed_demo")

        self.client = self._get_or_create(EVAL_CLIENT_PHONE, "EvalMijoz")
        self.other = self._get_or_create(EVAL_OTHER_PHONE, "EvalBoshqa")

    def _get_or_create(self, phone, first_name):
        user = self.User.objects.filter(phone=phone).first()
        if user is None:
            user = self.User.objects.create_user(phone=phone, first_name=first_name, role="client")
        return user

    # --- holat tayyorlash
    def _at(self, offset_days: int, hh: int, mm: int = 0) -> datetime:
        day = self.today + timedelta(days=offset_days)
        return datetime(day.year, day.month, day.day, hh, mm, tzinfo=SHOP_TZ)

    def _booking(self, client, master, service, start, status):
        return Booking.objects.create(
            client=client, master=master, service=service, start_time=start,
            end_time=start + timedelta(minutes=service.duration_minutes),
            price=service.price, status=status,
        )

    def setup(self, names) -> dict:
        ctx = {"setup_ids": []}
        jasur, soch = self.masters["Jasur"], self.services["Soch olish"]
        for name in names:
            if name == "own_booking":
                b = self._booking(self.client, jasur, soch, self._at(1, 15), Booking.Status.PENDING)
                ctx["own_id"] = b.id
            elif name == "own_booking_soon":
                start = timezone.now() + timedelta(hours=1)
                b = self._booking(self.client, jasur, soch, start, Booking.Status.PENDING)
                ctx["own_id"] = b.id
            elif name == "foreign_booking":
                b = self._booking(self.other, jasur, soch, self._at(1, 16), Booking.Status.PENDING)
                ctx["foreign_id"] = b.id
            elif name == "jasur_busy":
                b = self._booking(self.other, jasur, soch, self._at(1, 10), Booking.Status.CONFIRMED)
            elif name == "blocked":
                self.User.objects.filter(pk=self.client.pk).update(blocked_until=timezone.now() + timedelta(days=7))
                self.client.refresh_from_db()
                continue
            else:  # pragma: no cover  (validate_cases oldindan tutadi)
                raise ValueError(f"noma'lum setup: {name}")
            ctx["setup_ids"].append(b.id)
        return ctx

    def markers(self, ctx: dict) -> dict:
        ids = {}
        for name, service in self.services.items():
            ids[f"@service:{name}"] = service.id
        for name, master in self.masters.items():
            ids[f"@master:{name}"] = master.id
        for offset in range(0, 15):
            ids[f"@date:+{offset}"] = (self.today + timedelta(days=offset)).isoformat()
        if "own_id" in ctx:
            ids["@booking:own"] = ctx["own_id"]
        if "foreign_id" in ctx:
            ids["@booking:foreign"] = ctx["foreign_id"]
        return ids

    def restore(self):
        Booking.objects.filter(client__in=[self.client, self.other]).delete()
        self.User.objects.filter(pk=self.client.pk).update(blocked_until=None)
        self.client.refresh_from_db()

    def cleanup(self):
        self.restore()
        self.User.objects.filter(pk__in=[self.client.pk, self.other.pk]).delete()

    # --- oxirgi holat tekshiruvi
    def check_state(self, state: dict, ctx: dict) -> list:
        checks = []
        if "created_bookings" in state:
            expected = state["created_bookings"]
            actual = Booking.objects.filter(client=self.client).exclude(id__in=ctx["setup_ids"]).count()
            checks.append(Check(f"yaratilgan bronlar soni: {expected}", SAFETY, actual == expected,
                                f"haqiqatda {actual} ta"))
        for key, expected_status in state.get("status", {}).items():
            booking_id = ctx.get(f"{key}_id")
            booking = Booking.objects.filter(pk=booking_id).first()
            actual = booking.status if booking else "o'chib ketgan"
            checks.append(Check(f"{key} bron holati: {expected_status}", SAFETY,
                                actual == expected_status, f"haqiqatda: {actual}"))
        return checks


def run_case(case: dict, env: EvalEnv, runner, sleep: float = 0.0) -> CaseResult:
    """Bitta holatni boshidan oxirigacha ishga tushiradi. RateLimitError yuqoriga ko'tariladi."""
    result = CaseResult(case["id"], list(case["tags"]))
    ctx = env.setup(case.get("setup", []))
    ids = env.markers(ctx)
    history: list = []
    try:
        for turn in case["turns"]:
            say = turn["say"].format_map(_SafeDict(ctx))
            started = time.perf_counter()
            observability.reset_last()
            with record_tool_calls() as calls, observability.tag(f"eval:{case['id']}"):
                try:
                    reply = runner(env.client, say, list(history))
                except Exception as exc:
                    from openai import RateLimitError

                    if isinstance(exc, RateLimitError):
                        raise
                    result.error = f"{type(exc).__name__}: {describe_error(exc)}"
                    result.turns.append({"say": say, "reply": None, "tools": [c["name"] for c in calls]})
                    return result
            result.latency_s += time.perf_counter() - started
            result.tool_calls += len(calls)
            trace = observability.last_trace()
            if trace is not None:
                result.tokens += trace.total_tokens
                result.llm_calls += len(trace.calls)
            history += [{"role": "user", "content": say}, {"role": "assistant", "content": reply}]
            result.checks += score_turn(turn.get("expect", {}), reply, calls, ids)
            result.turns.append({
                "say": say,
                "reply": reply,
                "tools": [{"name": c["name"], "arguments": c["arguments"], "result": str(c["result"])[:200]}
                          for c in calls],
            })
            if sleep:
                time.sleep(sleep)
        result.checks += env.check_state(case.get("state", {}), ctx)
        return result
    finally:
        env.restore()
