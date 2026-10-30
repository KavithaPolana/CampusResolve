
import unittest

from sla_engine import (
    add_business_hours,
    calculate_sla_deadlines,
    evaluate_sla,
    format_datetime
)


class SLATests(unittest.TestCase):

    def test_same_day_deadline(self):
        result = add_business_hours(
            "2026-10-29 10:00:00",
            3
        )

        self.assertEqual(
            format_datetime(result),
            "2026-10-29 13:00:00"
        )

    def test_friday_to_monday(self):
        result = add_business_hours(
            "2026-10-30 16:00:00",
            8
        )

        self.assertEqual(
            format_datetime(result),
            "2026-11-02 16:00:00"
        )

    def test_after_business_hours(self):
        result = add_business_hours(
            "2026-10-29 18:30:00",
            2
        )

        self.assertEqual(
            format_datetime(result),
            "2026-10-30 11:00:00"
        )

    def test_weekend_start(self):
        result = add_business_hours(
            "2026-10-31 11:00:00",
            1
        )

        self.assertEqual(
            format_datetime(result),
            "2026-11-02 10:00:00"
        )

    def test_response_and_resolution(self):
        result = calculate_sla_deadlines(
            "2026-10-30 16:00:00",
            8
        )

        self.assertEqual(
            result["response_deadline"],
            "2026-11-02 10:00:00"
        )

        self.assertEqual(
            result["resolution_deadline"],
            "2026-11-02 16:00:00"
        )

    def test_response_breach(self):
        result = evaluate_sla(
            response_deadline="2026-10-29 11:00:00",
            resolution_deadline="2026-10-29 17:00:00",
            first_response_at="2026-10-29 12:00:00",
            resolved_at="2026-10-29 16:00:00",
            checked_at="2026-10-29 16:00:00"
        )

        self.assertTrue(
            result["response_breached"]
        )

        self.assertFalse(
            result["resolution_breached"]
        )

    def test_unresolved_ticket_breach(self):
        result = evaluate_sla(
            response_deadline="2026-10-29 11:00:00",
            resolution_deadline="2026-10-29 17:00:00",
            checked_at="2026-10-30 09:00:00"
        )

        self.assertTrue(
            result["response_breached"]
        )

        self.assertTrue(
            result["resolution_breached"]
        )

    def test_no_breach_before_deadline(self):
        result = evaluate_sla(
            response_deadline="2026-10-29 11:00:00",
            resolution_deadline="2026-10-29 17:00:00",
            checked_at="2026-10-29 10:00:00"
        )

        self.assertFalse(
            result["response_breached"]
        )

        self.assertFalse(
            result["resolution_breached"]
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
