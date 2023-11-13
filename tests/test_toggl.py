from unittest import TestCase
from freezegun import freeze_time

from toggl import MonthRange


class TestMonthRange(TestCase):
    @freeze_time("2023-07-10")
    def test_date_undefined__last_month_was_midyear(self):
        last_month = MonthRange(None, None)
        self.assertEqual(last_month.month, 6)
        self.assertEqual(last_month.days, 30)
        self.assertEqual(last_month.start, "2023-06-01")
        self.assertEqual(last_month.end, "2023-06-30")

    @freeze_time("2023-01-10")
    def test_date_undefined__last_month_was_last_year(self):
        last_month = MonthRange(None, None)
        self.assertEqual(last_month.month, 12)
        self.assertEqual(last_month.days, 31)
        self.assertEqual(last_month.start, "2022-12-01")
        self.assertEqual(last_month.end, "2022-12-31")

    def test_date_defined(self):
        last_month = MonthRange(10, 2023)
        self.assertEqual(last_month.month, 10)
        self.assertEqual(last_month.days, 31)
        self.assertEqual(last_month.start, "2023-10-01")
        self.assertEqual(last_month.end, "2023-10-31")

    def test_date_defined__valid_values(self):
        invalid_values = [
            (13, 2023),
            (-2, 2023),
            (1, -1),
            (1, 10000),
        ]
        for values in invalid_values:
            with self.assertRaises(ValueError):
                MonthRange(*values)
