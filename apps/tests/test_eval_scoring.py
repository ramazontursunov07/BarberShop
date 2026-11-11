"""Baholash tizimining o'zini sinaydi: Django ham, LLM ham kerak emas."""
import unittest

from apps.ai.evals.cases import CASES, KNOWN_SETUPS
from apps.ai.evals.scoring import (
    ARGUMENTS,
    CONTENT,
    LANGUAGE,
    RECOVERY,
    SAFETY,
    TOOL_SELECTION,
    CaseResult,
    Check,
    cyrillic_ratio,
    render_markdown,
    score_turn,
    summarize,
    validate_cases,
)

IDS = {"@master:Jasur": 7, "@service:Soch olish": 3, "@date:+1": "2026-11-10"}


def call(name, arguments=None, result=None):
    return {"name": name, "arguments": arguments or {}, "result": result if result is not None else {"ok": 1}}


def failed(checks):
    return [c.name for c in checks if not c.passed]


class DatasetTests(unittest.TestCase):
    def test_dataset_is_valid(self):
        self.assertEqual(validate_cases(CASES, KNOWN_SETUPS), [])

    def test_dataset_has_enough_cases_and_languages(self):
        self.assertGreaterEqual(len(CASES), 25)
        tags = {t for c in CASES for t in c["tags"]}
        self.assertTrue({"uz", "ru", "mixed", "security", "multi_turn"} <= tags)

    def test_validator_catches_problems(self):
        bad = [
            {"id": "a", "tags": ["x"], "turns": [{"say": "salom", "expect": {"nonsense": 1}}]},
            {"id": "a", "tags": [], "turns": []},
            {"id": "b", "tags": ["x"], "setup": ["yo'q"], "turns": [{"say": " "}]},
        ]
        problems = " | ".join(validate_cases(bad, KNOWN_SETUPS))
        for fragment in ("noma'lum kalitlar", "takrorlangan", "tags bo'sh", "turns bo'sh",
                         "noma'lum setup", "'say' yo'q"):
            self.assertIn(fragment, problems)


class ToolChecksTests(unittest.TestCase):
    def test_must_call_and_must_not_call(self):
        calls = [call("list_masters")]
        ok = score_turn({"must_call": ["list_masters"], "must_not_call": ["create_booking"]}, "javob", calls)
        self.assertEqual(failed(ok), [])
        bad = score_turn({"must_call": ["find_best_slots"], "must_not_call": ["list_masters"]}, "javob", calls)
        self.assertEqual(len(failed(bad)), 2)

    def test_must_call_any_and_no_tools(self):
        self.assertEqual(failed(score_turn({"must_call_any": ["a", "b"]}, "x", [call("b")])), [])
        self.assertEqual(len(failed(score_turn({"must_call_any": ["a", "b"]}, "x", [call("c")]))), 1)
        self.assertEqual(failed(score_turn({"no_tools": True}, "x", [])), [])
        self.assertEqual(len(failed(score_turn({"no_tools": True}, "x", [call("a")]))), 1)

    def test_no_successful_distinguishes_error_results(self):
        err = [call("cancel_booking", {"booking_id": 1}, {"error": "Bron topilmadi"})]
        okc = [call("cancel_booking", {"booking_id": 1}, {"id": 1, "status": "cancelled"})]
        self.assertEqual(failed(score_turn({"no_successful": ["cancel_booking"]}, "x", err)), [])
        self.assertEqual(len(failed(score_turn({"no_successful": ["cancel_booking"]}, "x", okc))), 1)


class ArgumentChecksTests(unittest.TestCase):
    def spec(self, **args):
        return {"calls": [{"tool": "find_best_slots", "args": args}]}

    def test_markers_are_resolved_and_ints_compared_loosely(self):
        calls = [call("find_best_slots", {"service_id": "3", "master_id": 7, "date": "2026-11-10"})]
        expect = self.spec(service_id="@service:Soch olish", master_id="@master:Jasur", date="@date:+1")
        self.assertEqual(failed(score_turn(expect, "x", calls, IDS)), [])

    def test_wrong_argument_fails_with_useful_detail(self):
        calls = [call("find_best_slots", {"part_of_day": "morning"})]
        checks = score_turn(self.spec(part_of_day="evening"), "x", calls, IDS)
        self.assertEqual(len(failed(checks)), 1)
        bad = [c for c in checks if not c.passed][0]
        self.assertEqual(bad.category, ARGUMENTS)
        self.assertIn("morning", bad.detail)

    def test_any_of_list_and_time_normalisation(self):
        calls = [call("find_best_slots", {"preferred_time": "9:00"})]
        self.assertEqual(failed(score_turn(self.spec(preferred_time=["09:00", "10:00"]), "x", calls)), [])
        calls = [call("create_booking", {"start_time": "10:00:00"})]
        expect = {"calls": [{"tool": "create_booking", "args": {"start_time": "10:00"}}]}
        self.assertEqual(failed(score_turn(expect, "x", calls)), [])

    def test_any_matching_call_is_enough(self):
        calls = [call("find_best_slots", {"part_of_day": "morning"}),
                 call("find_best_slots", {"part_of_day": "evening"})]
        self.assertEqual(failed(score_turn(self.spec(part_of_day="evening"), "x", calls)), [])

    def test_ok_flag_for_recovery(self):
        spec_ok = {"calls": [{"tool": "create_booking", "ok": True}]}
        spec_err = {"calls": [{"tool": "create_booking", "ok": False}]}
        success = [call("create_booking", {}, {"booking_id": 5})]
        error = [call("create_booking", {}, {"error": "band"})]
        self.assertEqual(failed(score_turn(spec_ok, "x", success)), [])
        self.assertEqual(len(failed(score_turn(spec_ok, "x", error))), 1)
        self.assertEqual(failed(score_turn(spec_err, "x", error)), [])
        recovery = score_turn(spec_err, "x", success)
        self.assertEqual([c.category for c in recovery if not c.passed], [RECOVERY])


class ReplyChecksTests(unittest.TestCase):
    def test_language_heuristic(self):
        self.assertLess(cyrillic_ratio("Ertaga soat 10:00 bo'sh"), 0.2)
        self.assertGreater(cyrillic_ratio("Завтра в 10:00 свободно"), 0.6)
        self.assertEqual(failed(score_turn({"reply_lang": "uz"}, "Ertaga bo'sh vaqt bor", [])), [])
        self.assertEqual(failed(score_turn({"reply_lang": "ru"}, "Завтра есть время", [])), [])
        self.assertEqual(len(failed(score_turn({"reply_lang": "ru"}, "Ertaga bor", []))), 1)
        self.assertEqual(len(failed(score_turn({"reply_lang": "uz"}, "Завтра есть время", []))), 1)

    def test_contains_checks_are_case_insensitive(self):
        reply = "Jasur va Bobur ishlaydi"
        self.assertEqual(failed(score_turn({"reply_contains_all": ["jasur", "BOBUR"]}, reply, [])), [])
        self.assertEqual(len(failed(score_turn({"reply_contains_all": ["Jasur", "Ali"]}, reply, []))), 1)
        self.assertEqual(failed(score_turn({"reply_contains_any": ["Ali", "bobur"]}, reply, [])), [])
        self.assertEqual(len(failed(score_turn({"reply_contains_any": ["Ali"]}, reply, []))), 1)

    def test_not_contains_is_a_safety_check(self):
        checks = score_turn({"reply_not_contains": ["+998"]}, "Raqami +998901234567", [])
        self.assertEqual([c.category for c in checks if not c.passed], [SAFETY])

    def test_empty_reply_always_fails(self):
        self.assertEqual(failed(score_turn({}, "   ", [])), ["javob bo'sh emas"])
        self.assertEqual(failed(score_turn({}, "salom", [])), [])


class SummaryTests(unittest.TestCase):
    def build(self):
        good = CaseResult("good", ["uz", "slots"], checks=[
            Check("a", TOOL_SELECTION, True), Check("b", ARGUMENTS, True)], latency_s=2.0, tool_calls=2)
        bad = CaseResult("bad", ["uz"], checks=[
            Check("c", TOOL_SELECTION, False, "nimadir"), Check("d", LANGUAGE, True)], latency_s=4.0, tool_calls=0)
        broken = CaseResult("broken", ["ru"], error="502")
        return [good, bad, broken]

    def test_case_pass_rules(self):
        good, bad, broken = self.build()
        self.assertTrue(good.passed)
        self.assertFalse(bad.passed)
        self.assertFalse(broken.passed)  # xato = o'tmadi, hatto tekshiruvlar bo'sh bo'lsa ham

    def test_summary_numbers(self):
        summary = summarize(self.build())
        self.assertEqual((summary["total"], summary["passed"]), (3, 1))
        self.assertAlmostEqual(summary["by_category"][TOOL_SELECTION]["rate"], 0.5)
        self.assertEqual(summary["by_category"][LANGUAGE]["passed"], 1)
        self.assertEqual(summary["by_tag"]["uz"], {"passed": 1, "total": 2})
        self.assertAlmostEqual(summary["avg_latency_s"], 3.0)

    def test_markdown_report_mentions_failures(self):
        results = self.build()
        text = render_markdown(summarize(results), results, {"model": "test-model", "sana": "2026-11-09"})
        self.assertIn("1/3", text)
        self.assertIn("test-model", text)
        self.assertIn("### bad", text)
        self.assertIn("nimadir", text)
        self.assertIn("XATO: 502", text)
        self.assertIn("Tool tanlash", text)


if __name__ == "__main__":
    unittest.main()
