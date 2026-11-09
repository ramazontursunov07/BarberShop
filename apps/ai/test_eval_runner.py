"""Baholash runner'ini LLM'siz sinaydi: "agent" o'rniga skriptlangan soxta agent ishlatiladi.

Maqsad: runner, tool yozuvchisi, holat tekshiruvi va tozalash to'g'ri ishlashini isbotlash.
Agent sifatining o'zini haqiqiy LLM bilan `python manage.py eval_agent` o'lchaydi.
"""
import re
from datetime import date, timedelta
from io import StringIO

from django.core.management import call_command
from django.test import SimpleTestCase, TestCase

from apps.bookings.models import Booking

from .evals.cases import CASES
from .evals.runner import EvalEnv, eval_today, fixed_today, run_case
from .tools import run_tool

BY_ID = {c["id"]: c for c in CASES}


class EvalHelpersTests(SimpleTestCase):
    def test_eval_today_is_a_monday_within_a_week(self):
        for offset in range(14):
            day = date(2026, 11, 1) + timedelta(days=offset)
            result = eval_today(day)
            self.assertEqual(result.weekday(), 0)
            self.assertTrue(day <= result < day + timedelta(days=7))

    def test_fixed_today_changes_the_prompt_date(self):
        from . import graph

        with fixed_today(date(2030, 1, 7)):
            self.assertIn("2030-01-07", graph._booking_prompt())
        self.assertNotIn("2030-01-07", graph._booking_prompt())


class EvalRunnerTests(TestCase):
    def setUp(self):
        call_command("seed_demo", stdout=StringIO())
        self.env = EvalEnv()
        self.jasur = self.env.masters["Jasur"].id
        self.soch = self.env.services["Soch olish"].id
        self.tomorrow = (self.env.today + timedelta(days=1)).isoformat()

    def leftovers(self):
        return Booking.objects.filter(client__in=[self.env.client, self.env.other]).count()

    # --- soxta agentlar
    def careful_agent(self, user, message, history):
        """Avval bo'sh vaqtni tekshiradi, tasdiqdan keyingina bron qiladi."""
        if "tasdiqlayman" in message.lower():
            run_tool("create_booking", user, {
                "master_id": self.jasur, "service_id": self.soch, "date": self.tomorrow, "start_time": "10:00"})
            return "Bron yaratildi."
        run_tool("get_available_slots", user, {"master_id": self.jasur, "service_id": self.soch, "date": self.tomorrow})
        return "Ertaga 10:00 bo'sh. Tasdiqlaysizmi?"

    def reckless_agent(self, user, message, history):
        """Tasdiq so'ramay darhol bron qiladi (qoidani buzadi)."""
        run_tool("create_booking", user, {
            "master_id": self.jasur, "service_id": self.soch, "date": self.tomorrow, "start_time": "10:00"})
        return "Bron yaratildi."

    # --- testlar
    def test_careful_agent_passes_booking_flow_and_db_is_cleaned(self):
        result = run_case(BY_ID["book_flow_uz"], self.env, self.careful_agent)
        self.assertTrue(result.passed, [(c.name, c.detail) for c in result.failures()])
        self.assertEqual(result.tool_calls, 2)
        self.assertEqual(self.leftovers(), 0)

    def test_reckless_agent_fails_the_confirmation_rule(self):
        result = run_case(BY_ID["book_flow_uz"], self.env, self.reckless_agent)
        self.assertFalse(result.passed)
        self.assertIn("create_booking chaqirilmasligi kerak", [c.name for c in result.failures()])
        self.assertEqual(self.leftovers(), 0)

    def test_cancel_flow_with_setup_booking(self):
        def agent(user, message, history):
            booking = Booking.objects.filter(client=user).first()
            if "bekor qiling" in message.lower():
                run_tool("cancel_booking", user, {"booking_id": booking.id})
                return "Bron bekor qilindi."
            run_tool("my_bookings", user, {})
            return "Ertaga 15:00 da broningiz bor. Bekor qilaymi?"

        result = run_case(BY_ID["cancel_flow_uz"], self.env, agent)
        self.assertTrue(result.passed, [(c.name, c.detail) for c in result.failures()])
        self.assertEqual(self.leftovers(), 0)

    def test_foreign_booking_cannot_be_cancelled_through_tools(self):
        def agent(user, message, history):
            booking_id = int(re.search(r"\d+", message).group())
            run_tool("cancel_booking", user, {"booking_id": booking_id})
            return "Bron topilmadi."

        result = run_case(BY_ID["inject_cancel_foreign"], self.env, agent)
        self.assertTrue(result.passed, [(c.name, c.detail) for c in result.failures()])

    def test_blocked_user_cannot_book_and_block_is_reset(self):
        result = run_case(BY_ID["blocked_user_cannot_book"], self.env, self.reckless_agent)
        self.assertTrue(result.passed, [(c.name, c.detail) for c in result.failures()])
        self.env.client.refresh_from_db()
        self.assertIsNone(self.env.client.blocked_until)

    def test_state_check_catches_unexpected_booking(self):
        # "Boshqa nomidan bron" holatida agent bron qilib yuborsa, holat tekshiruvi buni ushlaydi
        result = run_case(BY_ID["inject_book_for_other"], self.env, self.reckless_agent)
        self.assertFalse(result.passed)
        names = [c.name for c in result.failures()]
        self.assertIn("create_booking chaqirilmasligi kerak", names)
        self.assertIn("yaratilgan bronlar soni: 0", names)

    def test_agent_crash_is_reported_not_raised(self):
        def broken(user, message, history):
            raise RuntimeError("boom")

        result = run_case(BY_ID["greeting_uz"], self.env, broken)
        self.assertFalse(result.passed)
        self.assertIn("boom", result.error)

    def test_busy_slot_setup_blocks_the_slot(self):
        def agent(user, message, history):
            data = run_tool("get_available_slots", user, {
                "master_id": self.jasur, "service_id": self.soch, "date": self.tomorrow})
            assert "10:00" not in data["slots"]
            return "10:00 band. Boshqa vaqtlar: 10:30, 11:00."

        result = run_case(BY_ID["book_busy_slot_recovery"], self.env, agent)
        self.assertTrue(result.passed, [(c.name, c.detail) for c in result.failures()])
