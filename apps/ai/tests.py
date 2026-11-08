from datetime import date, datetime, time
from unittest import TestCase

from .chunking import chunk_text
from .graph_utils import flatten_content, last_user_text, make_query, parse_route, transcript
from .slots import compute_slots

DAY = date(2026, 11, 9)


class ComputeSlotsTests(TestCase):
    def test_empty_day_returns_all_slots(self):
        slots = compute_slots(DAY, time(9, 0), time(12, 0), [], 30, 30)
        self.assertEqual(slots, ["09:00", "09:30", "10:00", "10:30", "11:00", "11:30"])

    def test_service_must_fit_before_closing(self):
        slots = compute_slots(DAY, time(9, 0), time(11, 0), [], 60, 30)
        self.assertEqual(slots, ["09:00", "09:30", "10:00"])

    def test_busy_interval_blocks_overlapping_slots(self):
        busy = [(time(10, 0), time(11, 0))]
        slots = compute_slots(DAY, time(9, 0), time(12, 0), busy, 60, 30)
        self.assertEqual(slots, ["09:00", "11:00"])

    def test_past_slots_are_skipped(self):
        now = datetime(2026, 11, 9, 10, 15)
        slots = compute_slots(DAY, time(9, 0), time(12, 0), [], 30, 30, now=now)
        self.assertEqual(slots, ["10:30", "11:00", "11:30"])

    def test_invalid_duration_returns_empty(self):
        self.assertEqual(compute_slots(DAY, time(9, 0), time(12, 0), [], 0), [])


class ChunkTextTests(TestCase):
    def test_empty_text(self):
        self.assertEqual(chunk_text(""), [])
        self.assertEqual(chunk_text("   \n  "), [])

    def test_short_text_is_one_chunk(self):
        self.assertEqual(chunk_text("Salom dunyo"), ["Salom dunyo"])

    def test_long_text_is_split_within_limit(self):
        text = "\n".join(f"Qoida raqami {i}: bu juda muhim qoida matni." for i in range(60))
        chunks = chunk_text(text, max_chars=200)
        self.assertGreater(len(chunks), 1)
        self.assertTrue(all(len(c) <= 200 for c in chunks))
        joined = "\n".join(chunks)
        self.assertIn("Qoida raqami 0:", joined)
        self.assertIn("Qoida raqami 59:", joined)

    def test_single_very_long_line_terminates(self):
        chunks = chunk_text("a" * 5000, max_chars=800, overlap=100)
        self.assertGreater(len(chunks), 5)
        self.assertTrue(all(len(c) <= 800 for c in chunks))


class Msg:
    """LangChain xabarining soddalashtirilgan nusxasi (faqat type va content)."""

    def __init__(self, type, content):
        self.type = type
        self.content = content


class GraphUtilsTests(TestCase):
    def test_parse_route(self):
        self.assertEqual(parse_route("info"), "info")
        self.assertEqual(parse_route("  INFO\n"), "info")
        self.assertEqual(parse_route("booking"), "booking")
        self.assertEqual(parse_route("info yoki booking"), "booking")  # noaniq -> booking
        self.assertEqual(parse_route(""), "booking")
        self.assertEqual(parse_route("tushunmadim"), "booking")

    def test_flatten_content(self):
        self.assertEqual(flatten_content("salom"), "salom")
        self.assertEqual(flatten_content([{"type": "text", "text": "a"}, {"type": "text", "text": "b"}]), "ab")
        self.assertEqual(flatten_content(None), "")

    def test_last_user_text(self):
        msgs = [Msg("human", "bir"), Msg("ai", "javob"), Msg("human", "ikki")]
        self.assertEqual(last_user_text(msgs), "ikki")
        self.assertEqual(last_user_text([]), "")

    def test_transcript_skips_tools_and_limits(self):
        msgs = [
            Msg("human", "salom"),
            Msg("ai", ""),
            Msg("tool", "{}"),
            Msg("ai", "assalomu alaykum"),
            Msg("human", "narxlar?"),
        ]
        self.assertEqual(
            transcript(msgs, limit=2), "Yordamchi: assalomu alaykum\nMijoz: narxlar?"
        )

    def test_make_query_joins_short_followups(self):
        msgs = [Msg("human", "Bronni bekor qilish qoidalari qanday?"), Msg("ai", "..."), Msg("human", "Kechiksam-chi?")]
        self.assertEqual(make_query(msgs), "Bronni bekor qilish qoidalari qanday? Kechiksam-chi?")

    def test_make_query_keeps_long_question(self):
        msgs = [Msg("human", "oldingi"), Msg("human", "Bolalar uchun chegirma bormi sizlarda?")]
        self.assertEqual(make_query(msgs), "Bolalar uchun chegirma bormi sizlarda?")
