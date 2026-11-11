from types import SimpleNamespace as Msg

from django.test import SimpleTestCase

from apps.ai.graph_utils import EMPTY_NUDGE, fallback_reply, invoke_nonempty, is_russian


class InvokeNonEmptyTests(SimpleTestCase):
    def fake(self, replies):
        calls = []

        def invoke(messages):
            calls.append(list(messages))
            return replies[min(len(calls) - 1, len(replies) - 1)]

        return invoke, calls

    def test_non_empty_reply_returned_without_retry(self):
        invoke, calls = self.fake([Msg(content="Salom", tool_calls=[])])
        self.assertEqual(invoke_nonempty(invoke, ["m"], "NUDGE").content, "Salom")
        self.assertEqual(len(calls), 1)

    def test_tool_call_counts_as_non_empty(self):
        invoke, calls = self.fake([Msg(content="", tool_calls=[{"name": "x"}])])
        invoke_nonempty(invoke, ["m"], "NUDGE")
        self.assertEqual(len(calls), 1)

    def test_empty_reply_is_retried_with_nudge(self):
        invoke, calls = self.fake([Msg(content="", tool_calls=[]), Msg(content="Javob", tool_calls=[])])
        self.assertEqual(invoke_nonempty(invoke, ["m"], "NUDGE").content, "Javob")
        self.assertEqual(calls[1], ["m", "NUDGE"])
        self.assertEqual(calls[0], ["m"])  # nudge asl xabarlar ro'yxatiga qo'shilmaydi

    def test_gives_up_after_retries(self):
        invoke, calls = self.fake([Msg(content=" ", tool_calls=[])])
        invoke_nonempty(invoke, ["m"], "NUDGE", retries=2)
        self.assertEqual(len(calls), 3)

    def test_nudge_text_is_defined(self):
        self.assertTrue(EMPTY_NUDGE)


class FallbackTests(SimpleTestCase):
    def test_language_detection(self):
        self.assertTrue(is_russian("Мне нужно подстричься завтра утром"))
        self.assertFalse(is_russian("Ertaga soat 15:00 atrofida soqol olmoqchiman"))
        self.assertFalse(is_russian(""))

    def test_fallback_in_client_language(self):
        self.assertIn("Извините", fallback_reply("Запишите меня завтра"))
        self.assertIn("Kechirasiz", fallback_reply("Ertaga yozib qo'ying"))
        self.assertIn("мои записи", fallback_reply("Да", busy=True))
        self.assertIn("mening bronlarim", fallback_reply("Ha", busy=True))
