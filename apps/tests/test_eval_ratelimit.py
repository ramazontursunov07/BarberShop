from unittest import TestCase

from unittest import TestCase

from apps.ai.evals.ratelimit import describe_error, is_daily_limit, parse_retry_delay


class RateLimitParsingTests(TestCase):
    def test_daily_limit_detected(self):
        self.assertTrue(is_daily_limit("quotaId: GenerateRequestsPerDayPerProjectPerModel-FreeTier"))
        self.assertTrue(is_daily_limit("You exceeded your requests per day limit"))

    def test_per_minute_is_not_daily(self):
        self.assertFalse(is_daily_limit("quotaId: GenerateRequestsPerMinutePerProjectPerModel-FreeTier"))
        self.assertFalse(is_daily_limit(""))

    def test_retry_in_message(self):
        self.assertAlmostEqual(parse_retry_delay("Please retry in 12.5s."), 14.5)

    def test_retry_delay_json_field(self):
        self.assertAlmostEqual(parse_retry_delay('"retryDelay": "30s"'), 32.0)

    def test_header_has_priority(self):
        self.assertAlmostEqual(parse_retry_delay("retry in 99s", header="20"), 22.0)

    def test_clamped_and_default(self):
        self.assertAlmostEqual(parse_retry_delay("retry in 500s"), 122.0)
        self.assertAlmostEqual(parse_retry_delay("retry in 1s"), 7.0)
        self.assertAlmostEqual(parse_retry_delay("boshqa matn"), 62.0)
        self.assertAlmostEqual(parse_retry_delay("", header="abc"), 62.0)


class _FakeResponse:
    text = '[{ "error": { "code": 400, "message": "Unknown name default" } }]'


class _FakeError(Exception):
    def __init__(self, message, response=None, body=None):
        super().__init__(message)
        self.response = response
        self.body = body


class DescribeErrorTests(TestCase):
    def test_includes_response_body(self):
        text = describe_error(_FakeError("Error code: 400", response=_FakeResponse()))
        self.assertIn("Error code: 400", text)
        self.assertIn("Unknown name default", text)

    def test_falls_back_to_body_attribute(self):
        text = describe_error(_FakeError("Error code: 400", body={"detail": "nimadir noto'g'ri"}))
        self.assertIn("nimadir", text)

    def test_plain_exception_and_limit(self):
        self.assertEqual(describe_error(ValueError("oddiy xato")), "oddiy xato")
        self.assertLessEqual(len(describe_error(ValueError("x" * 5000), limit=100)), 100)
