import argparse
import calendar
import logging
from collections import namedtuple
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import List, Optional

import requests
from requests import Response
from requests.auth import HTTPBasicAuth


USERNAME = ""
PASSWORD = ''

HANDLE = ""
COMPANY = ""
WORKSPACE_ID = ""

BASE_URL = "https://api.track.toggl.com"


class ReportType(Enum):
    SUM = "summary"
    DET = "details"

    def filename(self) -> str:
        if self == ReportType.DET:
            return "time_entries"
        return f"{self.value}_report"


class FileExtension(Enum):
    CSV = "csv"
    PDF = "pdf"
    NONE = ""


@dataclass
class MonthRange:
    _start: datetime
    _end: datetime
    days: int
    month: int
    year: int

    @property
    def start(self) -> str:
        return self._start.strftime("%Y-%m-%d")

    @property
    def end(self) -> str:
        return self._end.strftime("%Y-%m-%d")

    def __init__(self, month: Optional[int], year: Optional[int]) -> None:
        last_day_of_prev_month = datetime.now().replace(day=1) - timedelta(days=1)
        self.month = month or last_day_of_prev_month.month
        self.year = year or last_day_of_prev_month.year

        self._start = datetime(self.year, self.month, 1)
        _, self.days = calendar.monthrange(self._start.year, self._start.month)
        self._end = self._start + timedelta(days=self.days - 1)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Downloads your monthly toggl reports."
    )
    parser.add_argument(
        "--month",
        metavar="m",
        help="Month as integer number, default: previous month",
        default=None,
        type=int,
    )
    parser.add_argument(
        "--year",
        metavar="y",
        help="Year in yyyy format, default: year of the previous month.",
        default=None,
        type=int,
    )
    return parser.parse_args()


def run(args: argparse.Namespace):
    month_range = MonthRange(args.month, args.year)
    api_token = authenticate(USERNAME, PASSWORD)

    response = get_report(api_token, ReportType.DET, FileExtension.NONE, month_range)
    entries = response.json()["data"]

    check_correctness(entries)
    save_report(api_token, ReportType.SUM, FileExtension.PDF, month_range)
    save_report(api_token, ReportType.DET, FileExtension.PDF, month_range)
    save_report(api_token, ReportType.DET, FileExtension.CSV, month_range)


def authenticate(user: str, password: str) -> str:
    response = requests.get(f"{BASE_URL}/api/v8/me", auth=HTTPBasicAuth(user, password))
    response.raise_for_status()
    return response.json()["data"]["api_token"]


def check_correctness(entries: List) -> None:
    try:
        check_if_empty(entries)
        check_reasonable_time(entries)
        check_if_overlapping(entries)
    except Exception as e:
        logging.warning(f"Raised exception {e} while checking for correctness.")


def get_report(
    api_token: str,
    report_type: ReportType,
    file_ext: FileExtension,
    month_range: MonthRange,
) -> Response:
    # docs: https://github.com/toggl/toggl_api_docs/blob/master/reports.md
    params = {
        "since": month_range.start,
        "until": month_range.end,
        "workspace_id": WORKSPACE_ID,
        "user_agent": USERNAME,
    }
    url = (
        f"{BASE_URL}/reports/api/v2/"
        f"{report_type.value}{'.' if file_ext != FileExtension.NONE else ''}{file_ext.value}"
    )

    response = requests.get(
        url, params=params, auth=HTTPBasicAuth(api_token, "api_token")
    )
    response.raise_for_status()
    return response


def check_if_empty(entries: List):
    for entry in entries:
        if not entry["description"]:
            logging.warning(
                f"Entry: {entry['project']} at {entry['start']} has empty description."
            )
        if not entry["project"]:
            logging.warning(
                f"Entry: {entry['description']} at {entry['start']} has empty project."
            )


def check_reasonable_time(entries: List):
    for entry in entries:
        hours = entry["dur"] / 3600000
        if hours > 8:
            logging.warning(
                f"Entry: {entry['description']} at {entry['start']} lasted for at least {hours}."
            )


def check_if_overlapping(entries: List):
    named_interval = namedtuple("named_interval", ["start", "end", "description"])
    time_intervals = [
        named_interval(
            datetime.fromisoformat(entry["start"]),
            datetime.fromisoformat(entry["end"]),
            entry["description"],
        )
        for entry in entries
    ]
    time_intervals_sorted = sorted(time_intervals)
    for int1, int2 in zip(time_intervals_sorted, time_intervals_sorted[1:]):
        if int2.start < int1.end:
            logging.warning(
                f"Entries: {int1.description} at {int1.end}, {int2.description} at {int2.start} are overlapping."
            )


def save_report(
    api_token: str,
    report_type: ReportType,
    file_ext: FileExtension,
    month_range: MonthRange,
) -> None:
    response = get_report(api_token, report_type, file_ext, month_range)
    filename = f"{COMPANY}_{HANDLE}_{report_type.filename()}_{month_range.start}_to_{month_range.end}.{file_ext.value}"
    with open(filename, "wb+") as report:
        report.write(response.content)


if __name__ == "__main__":
    args = parse_args()
    run(args)
