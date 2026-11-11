import unittest

from apps.ai.confirmation import GUARDED_TOOLS, is_confirmation, needs_confirmation
from apps.ai.evals.cases import CASES


class IsConfirmationTests(unittest.TestCase):
    def test_real_confirmations(self):
        for text in ["Ha, tasdiqlayman", "Да, подтверждаю", "Ha", "ha, yozing", "Xo'p", "Ha, bekor qiling",
                     "Mayli, tasdiqlayman.", "Да", "Хорошо, давайте"]:
            self.assertTrue(is_confirmation(text), text)

    def test_initial_requests_are_not_confirmations(self):
        for text in ["Ertaga soat 10:00 da Jasurga soch olish uchun yozib qo'ying",
                     "Запишите меня завтра на 11:00 к Бобуру на бороду",
                     "Ertaga Jasurga soch olish uchun 10:00 ga yozing",
                     "Ertangi bronimni bekor qilmoqchiman", "", "   "]:
            self.assertFalse(is_confirmation(text), text)

    def test_negation_and_changes_are_not_confirmations(self):
        for text in ["Yo'q, 12:00 ga o'zgartiring", "Yoq", "Нет, не надо", "Ha, lekin 12:00 ga o'zgartiring",
                     "Да, но завтра в 12", "Ha, bekor qilmang"]:
            self.assertFalse(is_confirmation(text), text)

    def test_long_message_is_not_plain_confirmation(self):
        self.assertFalse(is_confirmation("ha " + "so'z " * 20))

    def test_apostrophe_variants(self):
        self.assertTrue(is_confirmation("Xo\u2019p"))
        self.assertTrue(is_confirmation("To\u02bbg\u02bbri"))  # to'g'ri

    def test_needs_confirmation(self):
        self.assertTrue(needs_confirmation([{"name": "list_shops"}, {"name": "create_booking"}]))
        self.assertTrue(needs_confirmation([{"name": "cancel_booking"}]))
        self.assertFalse(needs_confirmation([{"name": "find_best_slots"}]))
        self.assertFalse(needs_confirmation([]))
        self.assertFalse(needs_confirmation(None))
        self.assertEqual(GUARDED_TOOLS, {"create_booking", "cancel_booking"})


class DatasetConsistencyTests(unittest.TestCase):
    """To'siq baholash ma'lumotlar to'plami bilan ziddiyatga kelmasligi kerak:
    bron/bekor qilish KUTILGAN tur tasdiq bo'lishi, kutilmagan tur esa tasdiq bo'lmasligi shart."""

    def test_turns_match_guard_decision(self):
        checked = 0
        for case in CASES:
            for turn in case["turns"]:
                expect = turn.get("expect", {})
                wanted = set(expect.get("must_call", [])) | {c["tool"] for c in expect.get("calls", [])}
                forbidden = set(expect.get("must_not_call", []))
                say = turn["say"]
                for tool in wanted & GUARDED_TOOLS:
                    self.assertTrue(is_confirmation(say), f"{case['id']}: {tool} kutiladi, lekin tasdiq emas: {say!r}")
                    checked += 1
                for tool in forbidden & GUARDED_TOOLS:
                    self.assertFalse(is_confirmation(say), f"{case['id']}: {tool} mumkin emas, lekin tasdiq: {say!r}")
                    checked += 1
        self.assertGreater(checked, 5)


if __name__ == "__main__":
    unittest.main()
