from __future__ import annotations

import csv
import io
import zipfile
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from io import StringIO
from typing import Any, cast
from xml.etree import ElementTree as ET


@dataclass(frozen=True, slots=True)
class ReportFilter:
    date_from: date | None = None
    date_to: date | None = None
    channel: str | None = None
    offset: int = 0
    limit: int = 50

    def __post_init__(self) -> None:
        if self.offset < 0 or self.offset > 100_000:
            raise ValueError("offset must be between 0 and 100000")
        if self.limit < 1 or self.limit > 1000:
            raise ValueError("limit must be between 1 and 1000")
        if self.date_from and self.date_to and self.date_from > self.date_to:
            raise ValueError("date_from cannot be after date_to")
        if self.channel not in {None, "WHOLESALE", "RETAIL"}:
            raise ValueError("channel must be WHOLESALE or RETAIL")

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
    writer.writerows([[_safe_csv_value(value) for value in row] for row in rows])
    return output.getvalue()


def _safe_csv_value(value: Any) -> Any:
    if isinstance(value, str):
        first_non_whitespace = value.lstrip(" \t\r\n")[:1]
        if first_non_whitespace in {"=", "+", "-", "@"} or value.startswith(("\t", "\r", "\n")):
            return "'" + value
    return value


def build_xlsx(headers: list[str], rows: list[list[Any]]) -> bytes:
    """Build a minimal, formula-safe single-sheet Open XML workbook without optional dependencies."""
    main_ns = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
    rel_ns = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
    pkg_rel_ns = "http://schemas.openxmlformats.org/package/2006/relationships"
    content_ns = "http://schemas.openxmlformats.org/package/2006/content-types"
    ET.register_namespace("", main_ns)
    ET.register_namespace("r", rel_ns)

    def column_name(index: int) -> str:
        name = ""
        while index:
            index, remainder = divmod(index - 1, 26)
            name = chr(65 + remainder) + name
        return name

    sheet = ET.Element(f"{{{main_ns}}}worksheet")
    data = ET.SubElement(sheet, f"{{{main_ns}}}sheetData")
    for row_index, values in enumerate([headers, *rows], 1):
        row = ET.SubElement(data, f"{{{main_ns}}}row", {"r": str(row_index)})
        for column_index, value in enumerate(values, 1):
            reference = f"{column_name(column_index)}{row_index}"
            cell = ET.SubElement(row, f"{{{main_ns}}}c", {"r": reference})
            if isinstance(value, (int, float, Decimal)) and not isinstance(value, bool):
                ET.SubElement(cell, f"{{{main_ns}}}v").text = str(value)
            else:
                cell.set("t", "inlineStr")
                inline = ET.SubElement(cell, f"{{{main_ns}}}is")
                ET.SubElement(inline, f"{{{main_ns}}}t").text = "" if value is None else str(value)

    workbook = ET.Element(f"{{{main_ns}}}workbook")
    sheets = ET.SubElement(workbook, f"{{{main_ns}}}sheets")
    ET.SubElement(
        sheets,
        f"{{{main_ns}}}sheet",
        {"name": "Profitability", "sheetId": "1", f"{{{rel_ns}}}id": "rId1"},
    )
    relationships = ET.Element(f"{{{pkg_rel_ns}}}Relationships")
    ET.SubElement(
        relationships,
        f"{{{pkg_rel_ns}}}Relationship",
        {
            "Id": "rId1",
            "Type": "http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet",
            "Target": "worksheets/sheet1.xml",
        },
    )
    content_types = ET.Element(f"{{{content_ns}}}Types")
    ET.SubElement(
        content_types,
        f"{{{content_ns}}}Default",
        {"Extension": "rels", "ContentType": "application/vnd.openxmlformats-package.relationships+xml"},
    )
    ET.SubElement(content_types, f"{{{content_ns}}}Default", {"Extension": "xml", "ContentType": "application/xml"})
    ET.SubElement(
        content_types,
        f"{{{content_ns}}}Override",
        {
            "PartName": "/xl/workbook.xml",
            "ContentType": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml",
        },
    )
    ET.SubElement(
        content_types,
        f"{{{content_ns}}}Override",
        {
            "PartName": "/xl/worksheets/sheet1.xml",
            "ContentType": "application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml",
        },
    )

    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", ET.tostring(content_types, encoding="utf-8", xml_declaration=True))
        archive.writestr("_rels/.rels", _package_relationship_xml())
        archive.writestr("xl/workbook.xml", ET.tostring(workbook, encoding="utf-8", xml_declaration=True))
        archive.writestr(
            "xl/_rels/workbook.xml.rels",
            ET.tostring(relationships, encoding="utf-8", xml_declaration=True),
        )
        archive.writestr("xl/worksheets/sheet1.xml", ET.tostring(sheet, encoding="utf-8", xml_declaration=True))
    return output.getvalue()


def _package_relationship_xml() -> bytes:
    namespace = "http://schemas.openxmlformats.org/package/2006/relationships"
    ET.register_namespace("pr", namespace)
    root = ET.Element(f"{{{namespace}}}Relationships")
    ET.SubElement(
        root,
        f"{{{namespace}}}Relationship",
        {
            "Id": "rId1",
            "Type": "http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument",
            "Target": "xl/workbook.xml",
        },
    )
    return cast(bytes, ET.tostring(root, encoding="utf-8", xml_declaration=True))

