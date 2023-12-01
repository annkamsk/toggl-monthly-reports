#!/usr/bin/env python
import os
import argparse
import calendar
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import List, Optional

import requests
from requests import Response


USERNAME = ""
PASSWORD = ""
SPREADSHEET_ID = ""

HANDLE = ""
COMPANY = ""
WORKSPACE_ID = ""

BASE_URL = "https://api.track.toggl.com"
API_URL = f"{BASE_URL}/api/v9"
REPORTS_URL = (
    BASE_URL
    + "/reports/api/v3/workspace/{workspace_id}/{report_type}/time_entries{extension}"
)

GSHEET_URL = (
    f"https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/export?format=xlsx"
)

SECONDS_IN_H = 3600


class ReportType(Enum):
    SUM = "summary"
    DET = "search"
    INVOICE = "invoice"

    def filename(self) -> str:
        if self == ReportType.DET:
            return "time_entries"
        if self == ReportType.INVOICE:
            return self.value
        return f"{self.value}_report"


class FileExtension(Enum):
    CSV = ".csv"
    PDF = ".pdf"
    XLSX = ".xlsx"
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


@dataclass
class TimeEntry:
    project_id: Optional[int]
    description: str
    start: datetime
    stop: datetime
    seconds: int


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

    check_correctness(month_range)

    download_report(USERNAME, PASSWORD, ReportType.SUM, FileExtension.PDF, month_range)
    download_report(USERNAME, PASSWORD, ReportType.DET, FileExtension.PDF, month_range)
    download_report(USERNAME, PASSWORD, ReportType.DET, FileExtension.CSV, month_range)

    if SPREADSHEET_ID:
        download_invoice(ReportType.INVOICE, FileExtension.XLSX, month_range)


def check_correctness(month_range: MonthRange) -> None:
    time_entries = get_time_entries(month_range)
    try:
        check_if_empty(time_entries)
        check_reasonable_time(time_entries)
        check_if_overlapping(time_entries)
    except Exception as e:
        logging.warning(f"Raised exception {e} while checking for correctness.")


def get_time_entries(month_range: MonthRange) -> List[TimeEntry]:
    """
    Download the list of time entries grouped by tasks and parse it
    to get a flat list of entries with their project and description.
    """
    response = get_report(
        USERNAME, PASSWORD, ReportType.DET, FileExtension.NONE, month_range
    )
    tasks = response.json()
    time_entries = []
    for task in tasks:
        for time_entry in task["time_entries"]:
            task_with_time_entry = {
                "project_id": task["project_id"],
                "description": task["description"],
                "start": datetime.fromisoformat(time_entry["start"]),
                "stop": datetime.fromisoformat(time_entry["stop"]),
                "seconds": time_entry["seconds"],
            }
            time_entries.append(TimeEntry(**task_with_time_entry))
    return time_entries


def get_report(
    user: str,
    password: str,
    report_type: ReportType,
    file_ext: FileExtension,
    month_range: MonthRange,
) -> Response:
    # docs: https://developers.track.toggl.space/docs/reports/
    body = {
        "start_date": month_range.start,
        "end_date": month_range.end,
    }
    url = REPORTS_URL.format(
        workspace_id=WORKSPACE_ID,
        report_type=report_type.value,
        extension=file_ext.value,
    )
    response = requests.post(url, json=body, auth=(user, password))
    response.raise_for_status()
    return response


def check_if_empty(entries: List[TimeEntry]) -> None:
    for entry in entries:
        if not entry.description:
            logging.warning(
                f"Entry: {entry.project_id} at {entry.start} has empty description."
            )
        if entry.project_id is None:
            logging.warning(
                f"Entry: {entry.description} at {entry.start} has empty project."
            )


def check_reasonable_time(entries: List[TimeEntry]) -> None:
    """
    Displays a warning for entries that lasted over 8h.
    """
    for entry in entries:
        hours = round(entry.seconds / SECONDS_IN_H, 2)
        if hours > 8:
            logging.warning(
                f"Entry: {entry.description} at {entry.start} lasted {hours}h."
            )


def check_if_overlapping(entries: List[TimeEntry]) -> None:
    time_intervals_sorted = sorted(entries, key=lambda entry: (entry.start, entry.stop))
    for int1, int2 in zip(time_intervals_sorted, time_intervals_sorted[1:]):
        if int2.start < int1.stop:
            logging.warning(
                f"Entries: {int1.description} at {int1.stop}, {int2.description} at "
                f"{int2.start} are overlapping."
            )


def download_report(
    user: str,
    password: str,
    report_type: ReportType,
    file_ext: FileExtension,
    month_range: MonthRange,
) -> None:
    response = get_report(user, password, report_type, file_ext, month_range)
    save_response(response, report_type, file_ext, month_range)


def download_invoice(
    report_type: ReportType,
    file_ext: FileExtension,
    month_range: MonthRange,
) -> None:
    response = requests.get(GSHEET_URL)
    response.raise_for_status()
    save_response(response, report_type, file_ext, month_range)


def save_response(
    response: Response,
    report_type: ReportType,
    file_ext: FileExtension,
    month_range: MonthRange,
) -> None:
    directory = f"reports/{month_range.month}.{month_range.year}/"
    filename = (
        f"{directory}{COMPANY}_{HANDLE}_{report_type.filename()}"
        f"_{month_range.start}_to_{month_range.end}{file_ext.value}"
    )
    os.makedirs(os.path.dirname(filename), exist_ok=True)
    with open(filename, "wb+") as report:
        report.write(response.content)


if __name__ == "__main__":
    args = parse_args()
    run(args)
