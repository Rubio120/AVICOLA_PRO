from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date
from io import StringIO
from typing import Any


@dataclass(frozen=True, slots=True)
class ReportFilter:
    date_from: date | None = None
    date_to: date | None = None
    offset: int = 0
    limit: int = 50

    def __post_init__(self) -> None:
        if self.offset < 0 or self.offset > 100_000:
            raise ValueError("offset must be between 0 and 100000")
        if self.limit < 1 or self.limit > 100:
            raise ValueError("limit must be between 1 and 100")
        if self.date_from and self.date_to and self.date_from > self.date_to:
            raise ValueError("date_from cannot be after date_to")

    @property
    def export_limit(self) -> int:
        return 1000


def confirmed_statuses(report: str) -> tuple[str, ...]:
    statuses = {
        "sales": ("ISSUED",),
        "purchasing": ("APPROVED", "PARTIALLY_RECEIVED", "RECEIVED"),
        "cash": ("CONFIRMED",),
        "inventory": ("CONFIRMED",),
        "production": ("CONFIRMED",),
        "costing": ("CONFIRMED", "CLOSED"),
    }
    return statuses.get(report, ("CONFIRMED",))


def build_csv(headers: list[str], rows: list[list[Any]]) -> str:
    output = StringIO(newline="")
    writer = csv.writer(output, lineterminator="\r\n")
    writer.writerow(headers)
    writer.writerows(rows)
    return output.getvalue()
