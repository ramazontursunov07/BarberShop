"""AI kuzatuvi (observability): har bir chat so'rovi va LLM chaqiruvi uchun kechikish, token va natija yozuvi.

Maqsad: "AI qancha turadi, qanchalik tez va qayerda xato qiladi?" savollariga raqam bilan javob berish.
SHAXSIY MA'LUMOT SAQLANMAYDI: prompt, javob va mijoz xabari yozilmaydi, faqat o'lchovlar (token, vaqt, tool nomlari).

Ishlatilishi:
    @traced("graph")                 # run_graph/run_agent atrofida: bitta ChatTrace + ichidagi LLMCall'lar
    with track("insights", "review_insights", model) as call:   # LangChain'siz chaqiruvlar uchun
        resp = client.chat.completions.create(...)
        call.usage(resp)
    config={"callbacks": [usage_callback()]}                    # LangGraph/LangChain chaqiruvlari uchun

Kuzatuvdagi xato asosiy ishni hech qachon buzmaydi (hammasi try/except ichida).
"""
import functools
import logging
import time
import uuid
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field

from django.db import transaction

logger = logging.getLogger(__name__)


@dataclass
class CallRecord:
    kind: str                    # chat | insights | vision | stt | embedding
    node: str = ""               # router | answer_info | booking_agent | agent | ...
    model: str = ""
    latency_ms: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    status: str = "ok"           # ok | rate_limited | error
    error_type: str = ""
    tool_calls: list = field(default_factory=list)  # model so'ragan tool nomlari


@dataclass
class Trace:
    engine: str
    user_id: int | None = None
    tag: str = ""
    trace_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    started: float = field(default_factory=time.perf_counter)
    calls: list = field(default_factory=list)
    tools: list = field(default_factory=list)       # haqiqatda bajarilgan tool'lar
    guard_rejections: int = 0
    outcome: str = "ok"                              # ok | empty_reply | recursion_limit | rate_limited | error

    @property
    def prompt_tokens(self) -> int:
        return sum(c.prompt_tokens for c in self.calls)

    @property
    def completion_tokens(self) -> int:
        return sum(c.completion_tokens for c in self.calls)

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens

    @property
    def latency_ms(self) -> int:
        return int((time.perf_counter() - self.started) * 1000)


_current: ContextVar = ContextVar("ai_trace", default=None)
_last: ContextVar = ContextVar("ai_last_trace", default=None)
_tag: ContextVar = ContextVar("ai_trace_tag", default="")


def _is_rate_limit(exc: BaseException) -> bool:
    try:
        from openai import RateLimitError
    except ImportError:  # pragma: no cover
        return False
    return isinstance(exc, RateLimitError)


# ------------------------------------------------------------------ iz holati

@contextmanager
def tag(value: str):
    """Shu blok ichidagi izlarga belgi qo'yadi (masalan baholashda "eval:book_flow_uz"): statistikadan ajratish uchun."""
    token = _tag.set(value)
    try:
        yield
    finally:
        _tag.reset(token)


def last_trace() -> Trace | None:
    return _last.get()


def reset_last() -> None:
    _last.set(None)


def note_tool(name: str) -> None:
    trace = _current.get()
    if trace is not None:
        trace.tools.append(name)


def note_guard_rejection() -> None:
    trace = _current.get()
    if trace is not None:
        trace.guard_rejections += 1


def mark(outcome: str) -> None:
    """Natijani belgilaydi (faqat hali "ok" bo'lsa): run_graph ichidan chaqiriladi."""
    trace = _current.get()
    if trace is not None and trace.outcome == "ok":
        trace.outcome = outcome


# ------------------------------------------------------------------ yozib olish

def record(rec: CallRecord) -> None:
    trace = _current.get()
    if trace is not None:
        trace.calls.append(rec)  # iz tugaganda hammasi birga saqlanadi
    else:
        try:
            with transaction.atomic():
                _persist_calls(None, [rec])
        except Exception as exc:  # kuzatuv asosiy ishni (STT, vision, embedding...) hech qachon buzmasin
            logger.warning("LLM chaqiruvi yozuvini saqlab bo'lmadi: %s", type(exc).__name__)


def usage_from(resp) -> tuple[int, int]:
    """OpenAI-mos javobdan (prompt_tokens, completion_tokens). Provayder bermasa (0, 0)."""
    usage = getattr(resp, "usage", None)
    if usage is None:
        return 0, 0
    prompt = getattr(usage, "prompt_tokens", None) or 0
    completion = getattr(usage, "completion_tokens", None)
    if completion is None:  # embedding: faqat total/prompt bo'ladi
        completion = 0
    return int(prompt), int(completion)


class _Handle:
    def __init__(self, rec: CallRecord):
        self._rec = rec

    def usage(self, resp) -> None:
        self._rec.prompt_tokens, self._rec.completion_tokens = usage_from(resp)

    def tool_calls(self, names) -> None:
        self._rec.tool_calls = list(names)


@contextmanager
def track(kind: str, node: str, model: str):
    rec = CallRecord(kind=kind, node=node, model=model)
    started = time.perf_counter()
    try:
        yield _Handle(rec)
    except Exception as exc:
        rec.status = "rate_limited" if _is_rate_limit(exc) else "error"
        rec.error_type = type(exc).__name__
        raise
    finally:
        rec.latency_ms = int((time.perf_counter() - started) * 1000)
        record(rec)


def traced(engine: str):
    """run_graph / run_agent (user, message, history) atrofida bitta chat so'rovi izini yuritadi."""

    def decorator(fn):
        @functools.wraps(fn)
        def wrapper(user, message, history=None):
            trace = Trace(engine=engine, user_id=getattr(user, "id", None), tag=_tag.get())
            token = _current.set(trace)
            try:
                return fn(user, message, history)
            except Exception as exc:
                trace.outcome = "rate_limited" if _is_rate_limit(exc) else "error"
                raise
            finally:
                _current.reset(token)
                _last.set(trace)
                _persist_trace(trace)

        return wrapper

    return decorator


def _persist_calls(trace_row, records) -> None:
    from .models import LLMCall

    LLMCall.objects.bulk_create([
        LLMCall(trace=trace_row, kind=r.kind, node=r.node, model=r.model[:80], latency_ms=r.latency_ms,
                prompt_tokens=r.prompt_tokens, completion_tokens=r.completion_tokens, status=r.status,
                error_type=r.error_type[:60], tool_calls=r.tool_calls)
        for r in records
    ])


def _route(trace: Trace) -> str:
    nodes = {c.node for c in trace.calls}
    if "answer_info" in nodes:
        return "info"
    if "booking_agent" in nodes:
        return "booking"
    return ""


def _persist_trace(trace: Trace) -> None:
    try:
        from .models import ChatTrace

        with transaction.atomic():  # savepoint: DB xatosi chaqiruvchining tranzaksiyasini buzmaydi
            row = ChatTrace.objects.create(
                trace_id=trace.trace_id, user_id=trace.user_id, engine=trace.engine, route=_route(trace),
                tag=trace.tag[:60], outcome=trace.outcome, latency_ms=trace.latency_ms,
                llm_calls=len(trace.calls), prompt_tokens=trace.prompt_tokens,
                completion_tokens=trace.completion_tokens, tool_names=trace.tools,
                guard_rejections=trace.guard_rejections,
            )
            _persist_calls(row, trace.calls)
    except Exception:
        logger.exception("Kuzatuv yozuvini saqlab bo'lmadi")


# ------------------------------------------------------------------ LangChain/LangGraph

def usage_callback():
    """LangGraph chaqiruvlarining tokeni va vaqtini yozadigan callback (graph.invoke(config=...) ga beriladi)."""
    from langchain_core.callbacks import BaseCallbackHandler

    class UsageCallback(BaseCallbackHandler):
        def __init__(self):
            self._pending = {}

        def on_chat_model_start(self, serialized, messages, *, run_id, metadata=None, **kwargs):
            meta = metadata or {}
            self._pending[run_id] = (time.perf_counter(), meta.get("langgraph_node", ""), meta.get("ls_model_name", ""))

        def _finish(self, run_id):
            return self._pending.pop(run_id, (time.perf_counter(), "", ""))

        def on_llm_end(self, response, *, run_id, **kwargs):
            started, node, model = self._finish(run_id)
            rec = CallRecord(kind="chat", node=node, model=model,
                             latency_ms=int((time.perf_counter() - started) * 1000))
            try:
                message = response.generations[0][0].message
                usage = getattr(message, "usage_metadata", None) or {}
                rec.prompt_tokens = int(usage.get("input_tokens") or 0)
                rec.completion_tokens = int(usage.get("output_tokens") or 0)
                rec.tool_calls = [tc.get("name", "") for tc in (getattr(message, "tool_calls", None) or [])]
            except (AttributeError, IndexError):
                pass
            record(rec)

        def on_llm_error(self, error, *, run_id, **kwargs):
            started, node, model = self._finish(run_id)
            record(CallRecord(kind="chat", node=node, model=model,
                              latency_ms=int((time.perf_counter() - started) * 1000),
                              status="rate_limited" if _is_rate_limit(error) else "error",
                              error_type=type(error).__name__))

    return UsageCallback()
