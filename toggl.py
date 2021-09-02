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
PASSWORD = ""

BASE_URL = "https://api.track.toggl.com"


class ReportType(Enum):
    SUM = "summary"
    DET = "details"


class FileExtension(Enum):
    CSV = "csv"
    PDF = "pdf"
    NONE = ""


@dataclass
class MonthRange:
    _start: datetime
    _end: datetime

    @property
    def start(self) -> str:
        return self._start.strftime("%Y-%m-%d")

    @property
    def end(self) -> str:
        return self._end.strftime("%Y-%m-%d")

    def __init__(self, first_day: Optional[datetime]) -> None:
        if not first_day:
            self._end = (datetime.now().replace(day=1) - timedelta(days=1))
            self._start = self._end.replace(day=1)
            return

        self._start = first_day
        _, days_count = calendar.monthrange(self._start.year, self._start.month)
        self._end = self._start + timedelta(days=days_count)


def parse_args():
    parser = argparse.ArgumentParser(description="Downloads your monthly toggl reports.")

    def type_date(value):
        if not value:
            return value

        try:
            dvalue = datetime.strptime(value, "%Y-%m-%d")
        except ValueError:
            raise argparse.ArgumentTypeError(f"{value} is an invalid date value. Must have YYYY-mm-dd format.")
        return dvalue

    parser.add_argument("--date", metavar="D",
                        help="First day of the month in YYYY-mm-dd format, default: whole previous month",
                        default=None, type=type_date)
    return parser.parse_args()


def run(args: argparse.Namespace):
    month_range = MonthRange(args.date)
    api_token = authenticate(USERNAME, PASSWORD)
    check_correctness(api_token, month_range)
    save_report(api_token, ReportType.SUM, FileExtension.PDF, month_range)
    save_report(api_token, ReportType.DET, FileExtension.PDF, month_range)
    save_report(api_token, ReportType.DET, FileExtension.CSV, month_range)


def authenticate(user: str, password: str) -> str:
    response = requests.get(
        f"{BASE_URL}/api/v8/me", auth=HTTPBasicAuth(user, password)
    )
    response.raise_for_status()
    return response.json()["data"]["api_token"]


def check_correctness(api_token: str, month_range: MonthRange):
    response = get_report(api_token, ReportType.DET, FileExtension.NONE, month_range)

    entries = response.json()["data"]
    try:
        check_if_empty(entries)
        check_reasonable_time(entries)
        check_if_overlapping(entries)
    except Exception as e:
        logging.warning(
            f"Raised exception {e} while checking for correctness."
        )


def get_report(
    api_token: str, report_type: ReportType, file_ext: FileExtension, month_range: MonthRange
) -> Response:
    # docs: https://github.com/toggl/toggl_api_docs/blob/master/reports.md

    params = {
        "since": month_range.start,
        "until": month_range.end,
        "workspace_id": "4014667",
        "user_agent": "ak@qed.ai",
    }
    url = f"{BASE_URL}/reports/api/v2/" \
          f"{report_type.value}{'.' if file_ext != FileExtension.NONE else ''}{file_ext.value}"

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
    named_interval = namedtuple(
        "named_interval", ["start", "end", "description"]
    )
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
    api_token: str, report_type: ReportType, file_ext: FileExtension, month_range: MonthRange
) -> None:
    response = get_report(api_token, report_type, file_ext, month_range)
    filename = f"{report_type.value}_report_{month_range.start}_to_{month_range.end}.{file_ext.value}"
    with open(filename, "wb+") as report:
        report.write(response.content)


if __name__ == "__main__":
    args = parse_args()
    run(args)
