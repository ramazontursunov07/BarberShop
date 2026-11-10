import unittest

from .evals.scoring import CaseResult, Check, render_markdown, summarize


class FailedCaseReportTests(unittest.TestCase):
    def _result(self):
        res = CaseResult("slot_x", ["slots"])
        res.checks = [Check("find_best_slots chaqirilishi kerak", "tool_selection", False, "chaqirilmadi")]
        res.turns = [{
            "say": "Ertaga kechqurun soch olish kerak",
            "reply": "Qaysi xizmat kerak?",
            "tools": [{"name": "list_masters", "arguments": {}, "result": "{}"}, {"name": "list_shops"}],
        }]
        return res

    def test_failed_case_shows_reply_and_tools(self):
        results = [self._result()]
        text = render_markdown(summarize(results), results, {"model": "m"})
        self.assertIn("Ertaga kechqurun soch olish kerak", text)
        self.assertIn("list_masters, list_shops", text)
        self.assertIn("Qaysi xizmat kerak?", text)

    def test_error_case_with_plain_tool_names_does_not_crash(self):
        res = CaseResult("bad", ["x"])
        res.error = "XATO: 502"
        res.turns = [{"say": "salom", "reply": None, "tools": ["list_shops"]}]
        text = render_markdown(summarize([res]), [res], {})
        self.assertIn("list_shops", text)
