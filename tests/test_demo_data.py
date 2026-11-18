import unittest
from collections import Counter
from datetime import date

from app.demo_data import simulated_dashboard_requests


class SimulatedDashboardDataTests(unittest.TestCase):
    def test_returns_40_fictional_requests_with_expected_status_mix(self):
        requests = simulated_dashboard_requests(date(2026, 11, 18))

        self.assertEqual(len(requests), 40)
        self.assertEqual(
            Counter(request["status"] for request in requests),
            {
                "submitted": 3,
                "accepted": 3,
                "assigned": 3,
                "in_progress": 3,
                "pending": 4,
                "completed": 24,
            },
        )
        self.assertTrue(all(request["id"].startswith("SIM-") for request in requests))
        self.assertTrue(all("simulación" in request["name"] for request in requests))

    def test_dates_cover_the_last_30_days_and_are_repeatable(self):
        today = date(2026, 11, 18)
        first = simulated_dashboard_requests(today)
        second = simulated_dashboard_requests(today)
        request_dates = [date.fromisoformat(request["date"]) for request in first]

        self.assertEqual(first, second)
        self.assertGreaterEqual(min(request_dates), date(2026, 10, 20))
        self.assertLessEqual(max(request_dates), today)
        self.assertIn(today, request_dates)


if __name__ == "__main__":
    unittest.main()
