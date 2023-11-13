import datetime
from unittest import TestCase
from tests.factories import TimeEntryFactory

from toggl import check_if_empty, check_if_overlapping, check_reasonable_time


MS_IN_H = 3600000


class TestCorrectnessCheck(TestCase):
    def test_check_if_empty__empty_description(self):
        entry = TimeEntryFactory(description="")
        with self.assertLogs(level="WARN") as log:
            check_if_empty([entry])
            self.assertEqual(len(log.output), 1)
            self.assertIn(
                f"{entry['project']} at {entry['start']} has empty description.",
                log.output[0],
            )

    def test_check_if_empty__empty_project(self):
        entry = TimeEntryFactory(project="")
        with self.assertLogs(level="WARN") as log:
            check_if_empty([entry])
            self.assertEqual(len(log.output), 1)
            self.assertIn(
                f"{entry['description']} at {entry['start']} has empty project.",
                log.output[0],
            )

    def test_check_if_empty__no_empty(self):
        entry = TimeEntryFactory()
        with self.assertNoLogs(level="WARN") as _:
            check_if_empty([entry])

    def test_check_reasonable_time__duration_lte_8h(self):
        duration_7h = 7 * MS_IN_H
        duration_8h = 8 * MS_IN_H
        duration_almost_8h = 8.001 * MS_IN_H
        entry1 = TimeEntryFactory(dur=duration_7h)
        entry2 = TimeEntryFactory(dur=duration_8h)
        entry3 = TimeEntryFactory(dur=duration_almost_8h)
        with self.assertNoLogs(level="WARN") as _:
            check_reasonable_time([entry1, entry2, entry3])

    def test_check_reasonable_time_over_8h(self):
        duration_over_8h = 8.01 * MS_IN_H
        entry = TimeEntryFactory(dur=duration_over_8h)
        with self.assertLogs(level="WARN") as log:
            check_reasonable_time([entry])
            self.assertEqual(len(log.output), 1)
            self.assertIn(
                f"Entry: {entry['description']} at {entry['start']} lasted 8.01h",
                log.output[0],
            )

    def test_check_if_overlapping__no_overlapping(self):
        entry1 = TimeEntryFactory()
        entry2 = TimeEntryFactory(_start=entry1["_end"])
        with self.assertNoLogs(level="WARN") as _:
            check_if_overlapping([entry1, entry2])

    def test_check_if_overlapping__overlapping(self):
        entry1 = TimeEntryFactory()
        entry2 = TimeEntryFactory(_start=entry1["_end"] - datetime.timedelta(seconds=1))
        with self.assertLogs(level="WARN") as log:
            check_if_overlapping([entry1, entry2])
            self.assertEqual(len(log.output), 1)
            end1_iso = entry1["end"].replace("T", " ")
            start2_iso = entry2["start"].replace("T", " ")
            self.assertIn(
                f"Entries: {entry1['description']} at {end1_iso}, "
                f"{entry2['description']} at {start2_iso} are overlapping.",
                log.output[0],
            )
