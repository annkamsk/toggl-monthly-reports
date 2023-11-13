import datetime
import factory
from factory.fuzzy import FuzzyDateTime, FuzzyText

from toggl import TimeEntry


class TimeEntryFactory(factory.Factory):
    class Meta:
        model = TimeEntry

    project_id: int = factory.Sequence(lambda n: n)
    description: str = FuzzyText()
    start = FuzzyDateTime(datetime.datetime(2020, 1, 1, tzinfo=datetime.timezone.utc))
    seconds: int = 14340
    stop = factory.LazyAttribute(
        lambda o: o.start + datetime.timedelta(seconds=o.seconds)
    )
