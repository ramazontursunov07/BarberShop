"""Tool qatlamining xavfsizligi: LLM'siz, deterministik. Agent nima desa ham, qoidalar buzilmasligi kerak."""
import json

from apps.bookings.models import Booking
from apps.bookings.tests import BookingTestBase

from .lc_tools import make_tools
from .tools import record_tool_calls, run_tool


class ToolLayerTests(BookingTestBase):
    def test_cancel_foreign_booking_is_refused(self):
        foreign = self.make_booking(client=self.other_client, hours_from_now=24)
        result = run_tool("cancel_booking", self.client_user, {"booking_id": foreign.id})
        self.assertIn("error", result)
        foreign.refresh_from_db()
        self.assertEqual(foreign.status, Booking.Status.PENDING)

    def test_my_bookings_returns_only_own(self):
        own = self.make_booking(client=self.client_user, hours_from_now=24)
        self.make_booking(client=self.other_client, hours_from_now=25)
        result = run_tool("my_bookings", self.client_user, {})
        self.assertEqual([b["id"] for b in result["bookings"]], [own.id])

    def test_unknown_tool_returns_error(self):
        self.assertIn("error", run_tool("drop_database", self.client_user, {}))

    def test_bad_arguments_never_raise(self):
        user = self.client_user
        cases = [
            ("create_booking", {}),
            ("create_booking", {"master_id": 999999, "service_id": self.service.id,
                                "date": "2030-01-01", "start_time": "10:00"}),
            ("create_booking", {"master_id": self.master.id, "service_id": self.service.id,
                                "date": "01-01-2030", "start_time": "10:00"}),
            ("find_best_slots", {"service_id": self.service.id, "date": "10-11-2026"}),
            ("find_best_slots", {"service_id": self.service.id, "date": "2030-01-01", "part_of_day": "midnight"}),
            ("get_available_slots", {"master_id": 999999, "service_id": 999999, "date": "2030-01-01"}),
        ]
        for name, args in cases:
            with self.subTest(tool=name, args=args):
                self.assertIn("error", run_tool(name, user, args))

    def test_model_cannot_book_on_behalf_of_someone_else(self):
        # create_booking sxemasida client/user maydoni yo'q: qo'shimcha argument rad etiladi
        result = run_tool("create_booking", self.client_user, {
            "master_id": self.master.id, "service_id": self.service.id,
            "date": "2030-01-07", "start_time": "10:00", "client_id": self.other_client.id,
        })
        self.assertIn("error", result)
        self.assertEqual(Booking.objects.filter(client=self.other_client).count(), 0)

    def test_langchain_tools_are_bound_to_the_calling_user(self):
        own = self.make_booking(client=self.client_user, hours_from_now=24)
        self.make_booking(client=self.other_client, hours_from_now=25)
        tools = {t.name: t for t in make_tools(self.client_user)}
        data = json.loads(tools["my_bookings"].invoke({}))
        self.assertEqual([b["id"] for b in data["bookings"]], [own.id])

    def test_find_best_slots_is_registered_everywhere(self):
        names = {t.name for t in make_tools(self.client_user)}
        self.assertTrue({"find_best_slots", "my_bookings", "cancel_booking"} <= names)

    def test_recorder_captures_calls_only_inside_the_block(self):
        with record_tool_calls() as calls:
            run_tool("list_masters", self.client_user, {})
        self.assertEqual([c["name"] for c in calls], ["list_masters"])
        run_tool("list_masters", self.client_user, {})
        self.assertEqual(len(calls), 1)
