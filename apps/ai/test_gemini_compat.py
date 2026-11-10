from unittest import TestCase

from .gemini_compat import BYPASS_SIGNATURE, add_thought_signature_bypass, is_gemini_endpoint


class GeminiCompatTests(TestCase):
    def test_endpoint_detection(self):
        self.assertTrue(is_gemini_endpoint("https://generativelanguage.googleapis.com/v1beta/openai/"))
        self.assertFalse(is_gemini_endpoint("https://api.groq.com/openai/v1"))
        self.assertFalse(is_gemini_endpoint(None))

    def test_adds_bypass_to_tool_calls_without_signature(self):
        messages = [
            {"role": "user", "content": "salom"},
            {"role": "assistant", "content": "", "tool_calls": [{"id": "1", "type": "function"}]},
            {"role": "tool", "tool_call_id": "1", "content": "{}"},
        ]
        add_thought_signature_bypass(messages)
        self.assertEqual(
            messages[1]["tool_calls"][0]["extra_content"],
            {"google": {"thought_signature": BYPASS_SIGNATURE}},
        )
        self.assertNotIn("tool_calls", messages[0])

    def test_keeps_real_signature(self):
        real = {"google": {"thought_signature": "HAQIQIY"}}
        messages = [{"role": "assistant", "tool_calls": [{"id": "1", "extra_content": real}]}]
        add_thought_signature_bypass(messages)
        self.assertEqual(messages[0]["tool_calls"][0]["extra_content"], real)

    def test_handles_empty_and_odd_input(self):
        self.assertEqual(add_thought_signature_bypass([]), [])
        self.assertEqual(add_thought_signature_bypass(None), [])
        odd = [{"role": "assistant"}, "matn", {"role": "assistant", "tool_calls": None}]
        self.assertEqual(add_thought_signature_bypass(odd), odd)
