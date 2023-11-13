import datetime
import factory
from factory.fuzzy import FuzzyDateTime, FuzzyText


def datetime_to_str(d: datetime.datetime) -> str:
    # Converts datetime to string with colon in the timezone offset
    d_str = d.strftime("%Y-%m-%dT%H:%M:%S%z")
    return f"{d_str[:-2]}:{d_str[-2:]}"


class TimeEntryFactory(factory.DictFactory):
    id: int = factory.Sequence(lambda n: n)
    description: str = FuzzyText()
    _start = FuzzyDateTime(datetime.datetime(2020, 1, 1, tzinfo=datetime.timezone.utc))
    start = factory.LazyAttribute(lambda o: datetime_to_str(o._start))
    dur: int = 14340000
    _end = factory.LazyAttribute(
        lambda o: o._start + datetime.timedelta(milliseconds=o.dur)
    )
    end = factory.LazyAttribute(lambda o: datetime_to_str(o._end))
    user = FuzzyText()
    project = FuzzyText()
