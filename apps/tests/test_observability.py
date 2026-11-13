import csv
import os
import tempfile
from datetime import timedelta
from io import StringIO
from types import SimpleNamespace
from unittest import mock

import httpx
from django.core.management import call_command
from django.test import SimpleTestCase, TestCase
from django.utils import timezone
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from openai import RateLimitError
from rest_framework.test import APIClient

from apps.ai import observability
from apps.ai.evals.cases import CASES
from apps.ai.evals.runner import EvalEnv, run_case
from apps.ai.evals.scoring import CaseResult, render_markdown, summarize
from apps.ai.graph import run_graph
from apps.ai.models import ChatTrace, LLMCall
from apps.ai.observability import CallRecord
from apps.ai.usage_stats import cost_usd, percentile, usage_stats
from apps.tests.base import BookingTestBase, make_user


def rate_limit_error():
    request = httpx.Request("POST", "http://llm.test")
    return RateLimitError("limit", response=httpx.Response(429, request=request), body=None)


class FakeChat(BaseChatModel):
    """Skriptdagi javoblarni ketma-ket qaytaradi; har biri tokeni (usage_metadata) bilan."""

    script: list
    model_name: str = "fake-model"

    @property
    def _llm_type(self) -> str:
        return "fake"

    def bind_tools(self, tools, **kwargs):
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        message = self.script.pop(0)
        return ChatResult(generations=[ChatGeneration(message=message)])


def reply(text="", tool_calls=None, tokens=(100, 10)):
    return AIMessage(content=text, tool_calls=tool_calls or [],
                     usage_metadata={"input_tokens": tokens[0], "output_tokens": tokens[1],
                                     "total_tokens": sum(tokens)})


class NoDatabaseTests(SimpleTestCase):
    def test_tracking_works_where_database_is_forbidden(self):
        with observability.track("stt", "transcribe", "whisper") as call:
            call.usage(SimpleNamespace(usage=None))
        self.assertTrue(True)  # asosiy ish bazasiz ham xatosiz tugadi


class PercentileTests(SimpleTestCase):
    def test_nearest_rank(self):
        values = list(range(1, 11))
        self.assertEqual(percentile(values, 0.5), 5)
        self.assertEqual(percentile(values, 0.95), 10)
        self.assertEqual(percentile([7], 0.95), 7)
        self.assertEqual(percentile([3, 1, 2], 0.5), 2)  # tartiblanmagan ro'yxat
        self.assertIsNone(percentile([], 0.5))

    def test_cost_needs_prices(self):
        with mock.patch.dict(os.environ, {"LLM_PRICE_INPUT_PER_M": "", "LLM_PRICE_OUTPUT_PER_M": ""}):
            self.assertIsNone(cost_usd(1000, 1000))
        with mock.patch.dict(os.environ, {"LLM_PRICE_INPUT_PER_M": "0.5", "LLM_PRICE_OUTPUT_PER_M": "2"}):
            self.assertEqual(cost_usd(1_000_000, 500_000), 1.5)


class TrackTests(TestCase):
    def test_standalone_call_is_saved_with_usage(self):
        with observability.track("insights", "review_insights", "m1") as call:
            call.usage(SimpleNamespace(usage=SimpleNamespace(prompt_tokens=120, completion_tokens=30)))
        row = LLMCall.objects.get()
        self.assertEqual((row.kind, row.node, row.model, row.status), ("insights", "review_insights", "m1", "ok"))
        self.assertEqual((row.prompt_tokens, row.completion_tokens), (120, 30))
        self.assertIsNone(row.trace)

    def test_missing_usage_is_zero_not_crash(self):
        with observability.track("stt", "transcribe", "whisper") as call:
            call.usage(SimpleNamespace(text="salom"))
        self.assertEqual(LLMCall.objects.get().prompt_tokens, 0)

    def test_storage_failure_does_not_break_the_tracked_call(self):
        with mock.patch.object(LLMCall.objects, "bulk_create", side_effect=RuntimeError("db down")):
            with observability.track("stt", "transcribe", "whisper"):
                result = "matn"
        self.assertEqual(result, "matn")
        self.assertEqual(LLMCall.objects.count(), 0)

    def test_errors_are_classified_and_reraised(self):
        with self.assertRaises(RateLimitError):
            with observability.track("chat", "agent", "m1"):
                raise rate_limit_error()
        with self.assertRaises(ValueError):
            with observability.track("chat", "agent", "m1"):
                raise ValueError("boom")
        statuses = {c.status: c.error_type for c in LLMCall.objects.all()}
        self.assertEqual(statuses, {"rate_limited": "RateLimitError", "error": "ValueError"})


class TracedTests(TestCase):
    def test_trace_collects_calls_tools_and_guard(self):
        user = make_user("+998900000777", "Mijoz")

        @observability.traced("graph")
        def agent(user, message, history=None):
            observability.record(CallRecord("chat", "router", "m", 50, 100, 5))
            observability.record(CallRecord("chat", "booking_agent", "m", 300, 400, 40, tool_calls=["list_shops"]))
            observability.note_tool("list_shops")
            observability.note_guard_rejection()
            return "salom"

        self.assertEqual(agent(user, "Salom"), "salom")
        trace = ChatTrace.objects.get()
        self.assertEqual((trace.engine, trace.route, trace.outcome), ("graph", "booking", "ok"))
        self.assertEqual((trace.llm_calls, trace.prompt_tokens, trace.completion_tokens), (2, 500, 45))
        self.assertEqual(trace.tool_names, ["list_shops"])
        self.assertEqual(trace.guard_rejections, 1)
        self.assertEqual(trace.user_id, user.id)
        self.assertEqual(LLMCall.objects.filter(trace=trace).count(), 2)
        self.assertEqual(observability.last_trace().trace_id, trace.trace_id)

    def test_exceptions_mark_outcome_and_propagate(self):
        @observability.traced("graph")
        def failing(user, message, history=None):
            raise rate_limit_error()

        with self.assertRaises(RateLimitError):
            failing(None, "x")
        self.assertEqual(ChatTrace.objects.get().outcome, "rate_limited")

        @observability.traced("graph")
        def broken(user, message, history=None):
            raise ValueError("boom")

        with self.assertRaises(ValueError):
            broken(None, "x")
        self.assertEqual(ChatTrace.objects.filter(outcome="error").count(), 1)

    def test_tag_is_recorded(self):
        @observability.traced("graph")
        def agent(user, message, history=None):
            return "ok"

        with observability.tag("eval:case1"):
            agent(None, "x")
        self.assertEqual(ChatTrace.objects.get().tag, "eval:case1")

    def test_storage_failure_never_breaks_the_request(self):
        @observability.traced("graph")
        def agent(user, message, history=None):
            return "javob"

        with mock.patch.object(ChatTrace.objects, "create", side_effect=RuntimeError("db down")):
            self.assertEqual(agent(None, "x"), "javob")


class RunGraphTracingTests(BookingTestBase):
    """Haqiqiy run_graph soxta chat model bilan: callback tokenlarni va tugun nomlarini yig'adimi."""

    def run_with(self, script):
        fake = FakeChat(script=script)
        with mock.patch("apps.ai.graph._llm", return_value=fake):
            return run_graph(self.client_user, "Salom", [])

    def test_booking_route_records_router_and_agent_calls(self):
        text = self.run_with([reply("booking", tokens=(80, 2)), reply("Assalomu alaykum!", tokens=(300, 20))])
        self.assertEqual(text, "Assalomu alaykum!")
        trace = ChatTrace.objects.get()
        self.assertEqual((trace.route, trace.outcome, trace.llm_calls), ("booking", "ok", 2))
        self.assertEqual((trace.prompt_tokens, trace.completion_tokens), (380, 22))
        self.assertEqual({c.node for c in trace.calls.all()}, {"router", "booking_agent"})
        self.assertEqual(trace.calls.first().model, "fake-model")

    def test_info_route(self):
        with mock.patch("apps.ai.graph.rag.search_shop_info", return_value={"results": []}):
            self.run_with([reply("info"), reply("Bu haqda ma'lumotim yo'q")])
        trace = ChatTrace.objects.get()
        self.assertEqual(trace.route, "info")
        self.assertIn("answer_info", {c.node for c in trace.calls.all()})

    def test_executed_tools_and_requested_tools_are_recorded(self):
        call = {"name": "list_shops", "args": {}, "id": "c1"}
        self.run_with([reply("booking"), reply("", [call]), reply("Mana ro'yxat")])
        trace = ChatTrace.objects.get()
        self.assertEqual(trace.tool_names, ["list_shops"])
        agent_calls = list(trace.calls.filter(node="booking_agent").order_by("id"))
        self.assertEqual(agent_calls[0].tool_calls, ["list_shops"])

    def test_confirmation_guard_rejection_is_counted_and_nothing_booked(self):
        call = {"name": "create_booking", "id": "c1", "args": {
            "master_id": self.master.id, "service_id": self.service.id, "date": "2030-01-01", "start_time": "10:00"}}
        self.run_with([reply("booking"), reply("", [call]), reply("Tasdiqlaysizmi?")])
        trace = ChatTrace.objects.get()
        self.assertEqual(trace.guard_rejections, 1)
        self.assertEqual(trace.tool_names, [])  # create_booking bajarilmadi
        self.assertEqual(self.client_user.bookings.count(), 0)

    def test_empty_reply_is_marked(self):
        text = self.run_with([reply("booking"), reply(""), reply(""), reply("")])
        self.assertIn("Kechirasiz", text)
        self.assertEqual(ChatTrace.objects.get().outcome, "empty_reply")


class UsageStatsTests(TestCase):
    def make_trace(self, tag="", latency=1000, outcome="ok", tools=(), guard=0, tokens=(100, 10), when=None):
        trace = ChatTrace.objects.create(
            trace_id=os.urandom(8).hex(), engine="graph", route="booking", tag=tag, outcome=outcome,
            latency_ms=latency, llm_calls=2, prompt_tokens=tokens[0], completion_tokens=tokens[1],
            tool_names=list(tools), guard_rejections=guard)
        LLMCall.objects.create(trace=trace, kind="chat", node="booking_agent", model="m", latency_ms=latency // 2,
                               prompt_tokens=tokens[0], completion_tokens=tokens[1])
        if when:
            ChatTrace.objects.filter(pk=trace.pk).update(created_at=when)
            LLMCall.objects.filter(trace=trace).update(created_at=when)
        return trace

    def test_aggregation(self):
        for latency in (1000, 2000, 3000, 4000):
            self.make_trace(latency=latency, tools=["list_shops"])
        self.make_trace(outcome="error", guard=2)
        stats = usage_stats(7)
        self.assertEqual(stats["chat"]["requests"], 5)
        self.assertEqual(stats["chat"]["outcomes"], {"ok": 4, "error": 1})
        self.assertEqual(stats["chat"]["latency_ms"]["p50"], 2000)
        self.assertEqual(stats["chat"]["latency_ms"]["p95"], 4000)
        self.assertEqual(stats["chat"]["tools"], {"list_shops": 4})
        self.assertEqual(stats["chat"]["guard_rejections"], 2)
        self.assertEqual(stats["llm"]["prompt_tokens"], 500)
        self.assertEqual(stats["llm"]["by_node"]["chat:booking_agent"]["calls"], 5)
        self.assertEqual(len(stats["daily"]), 1)

    def test_eval_traces_excluded_unless_requested(self):
        self.make_trace()
        self.make_trace(tag="eval:book_flow_uz")
        self.assertEqual(usage_stats(7)["chat"]["requests"], 1)
        self.assertEqual(usage_stats(7)["llm"]["calls"], 1)
        self.assertEqual(usage_stats(7, include_eval=True)["chat"]["requests"], 2)

    def test_old_data_outside_window_ignored(self):
        self.make_trace(when=timezone.now() - timedelta(days=30))
        self.assertEqual(usage_stats(7)["chat"]["requests"], 0)
        self.assertEqual(usage_stats(60)["chat"]["requests"], 1)

    def test_empty_database(self):
        stats = usage_stats(7)
        self.assertEqual(stats["chat"]["requests"], 0)
        self.assertIsNone(stats["chat"]["latency_ms"]["p95"])
        self.assertIsNone(stats["llm"]["cost_usd"])

    def test_cost_uses_env_prices(self):
        self.make_trace(tokens=(1_000_000, 1_000_000))
        with mock.patch.dict(os.environ, {"LLM_PRICE_INPUT_PER_M": "1", "LLM_PRICE_OUTPUT_PER_M": "3"}):
            self.assertEqual(usage_stats(7)["llm"]["cost_usd"], 4.0)


class UsageApiTests(TestCase):
    URL = "/api/ai/usage/"

    def setUp(self):
        self.api = APIClient()

    def test_only_admin_role_allowed(self):
        self.assertEqual(self.api.get(self.URL).status_code, 401)
        for role in ("client", "owner", "master"):
            self.api.force_authenticate(make_user(f"+99890000{role[:2]}01", role, role))
            self.assertEqual(self.api.get(self.URL).status_code, 403, role)
        self.api.force_authenticate(make_user("+998900009999", "Admin", "admin"))
        resp = self.api.get(self.URL, {"days": 3})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["days"], 3)
        self.assertEqual(self.api.get(self.URL, {"days": "x"}).status_code, 400)
        self.assertEqual(self.api.get(self.URL, {"days": 9999}).data["days"], 90)


class ReportCommandTests(TestCase):
    def setUp(self):
        trace = ChatTrace.objects.create(trace_id="a" * 32, engine="graph", route="booking", latency_ms=1200,
                                         llm_calls=2, prompt_tokens=300, completion_tokens=30,
                                         tool_names=["list_shops", "find_best_slots"])
        LLMCall.objects.create(trace=trace, kind="chat", node="router", model="m", latency_ms=300)

    def test_text_json_and_csv(self):
        out = StringIO()
        call_command("llm_report", stdout=out)
        self.assertIn("Chat so'rovlari: 1", out.getvalue())
        self.assertIn("chat:router", out.getvalue())

        out = StringIO()
        call_command("llm_report", "--json", stdout=out)
        self.assertIn('"requests": 1', out.getvalue())

        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "traces.csv")
            call_command("llm_report", "--csv", path, stdout=StringIO())
            rows = list(csv.DictReader(open(path, encoding="utf-8")))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["tools"], "list_shops find_best_slots")
        self.assertEqual(rows[0]["prompt_tokens"], "300")


class EvalIntegrationTests(TestCase):
    def test_eval_collects_tokens_and_tags_traces(self):
        call_command("seed_demo", stdout=StringIO())
        env = EvalEnv()
        case = next(c for c in CASES if not c.get("setup"))

        @observability.traced("graph")
        def agent(user, message, history=None):
            observability.record(CallRecord("chat", "booking_agent", "m", 10, 200, 20))
            observability.record(CallRecord("chat", "router", "m", 10, 50, 5))
            return "javob"

        result = run_case(case, env, agent)
        self.assertEqual((result.tokens, result.llm_calls), (275 * len(case["turns"]), 2 * len(case["turns"])))
        self.assertTrue(ChatTrace.objects.filter(tag=f"eval:{case['id']}").exists())

    def test_runner_without_tracing_leaves_zero_tokens(self):
        call_command("seed_demo", stdout=StringIO())
        env = EvalEnv()
        case = next(c for c in CASES if not c.get("setup"))
        result = run_case(case, env, lambda user, message, history: "javob")
        self.assertEqual((result.tokens, result.llm_calls), (0, 0))

    def test_report_shows_tokens_only_when_available(self):
        with_tokens = CaseResult("a", ["uz"], latency_s=2.0, tokens=500, llm_calls=2)
        text = render_markdown(summarize([with_tokens]), [with_tokens], {})
        self.assertIn("token: 500", text)
        without = CaseResult("b", ["uz"], latency_s=2.0)
        text = render_markdown(summarize([without]), [without], {})
        self.assertNotIn("token:", text)
        self.assertIn("O'rtacha javob vaqti", text)
