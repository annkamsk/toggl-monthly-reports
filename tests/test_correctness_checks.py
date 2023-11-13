import datetime
from unittest import TestCase
from tests.factories import TimeEntryFactory

from toggl import (
    SECONDS_IN_H,
    check_if_empty,
    check_if_overlapping,
    check_reasonable_time,
)


class TestCorrectnessCheck(TestCase):
    def test_check_if_empty__empty_description(self):
        entry = TimeEntryFactory(description="")
        with self.assertLogs(level="WARN") as log:
            check_if_empty([entry])
            self.assertEqual(len(log.output), 1)
            self.assertIn(
                f"{entry.project_id} at {entry.start} has empty description.",
                log.output[0],
            )

    def test_check_if_empty__empty_project(self):
        entry = TimeEntryFactory(project_id=None)
        with self.assertLogs(level="WARN") as log:
            check_if_empty([entry])
            self.assertEqual(len(log.output), 1)
            self.assertIn(
                f"{entry.description} at {entry.start} has empty project.",
                log.output[0],
            )

    def test_check_if_empty__no_empty(self):
        entry = TimeEntryFactory()
        with self.assertNoLogs(level="WARN") as _:
            check_if_empty([entry])

    def test_check_reasonable_time__duration_lte_8h(self):
        duration_7h = 7 * SECONDS_IN_H
        duration_8h = 8 * SECONDS_IN_H
        duration_almost_8h = 8.001 * SECONDS_IN_H
        entry1 = TimeEntryFactory(seconds=duration_7h)
        entry2 = TimeEntryFactory(seconds=duration_8h)
        entry3 = TimeEntryFactory(seconds=duration_almost_8h)
        with self.assertNoLogs(level="WARN") as _:
            check_reasonable_time([entry1, entry2, entry3])

    def test_check_reasonable_time_over_8h(self):
        duration_over_8h = 8.01 * SECONDS_IN_H
        entry = TimeEntryFactory(seconds=duration_over_8h)
        with self.assertLogs(level="WARN") as log:
            check_reasonable_time([entry])
            self.assertEqual(len(log.output), 1)
            self.assertIn(
                f"Entry: {entry.description} at {entry.start} lasted 8.01h",
                log.output[0],
            )

    def test_check_if_overlapping__no_overlapping(self):
        entry1 = TimeEntryFactory()
        entry2 = TimeEntryFactory(start=entry1.stop)
        with self.assertNoLogs(level="WARN") as _:
            check_if_overlapping([entry1, entry2])

    def test_check_if_overlapping__overlapping(self):
        entry1 = TimeEntryFactory()
        entry2 = TimeEntryFactory(start=entry1.stop - datetime.timedelta(seconds=1))
        with self.assertLogs(level="WARN") as log:
            check_if_overlapping([entry1, entry2])
            self.assertEqual(len(log.output), 1)
            self.assertIn(
                f"Entries: {entry1.description} at {entry1.stop}, "
                f"{entry2.description} at {entry2.start} are overlapping.",
                log.output[0],
            )
