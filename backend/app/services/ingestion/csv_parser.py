"""Strict CSV parsing. File-level problems reject the whole file; row-shape problems reject the
row. Header names are trimmed and lower-cased; nothing else is guessed."""

import csv
import io
from dataclasses import dataclass, field

from app.services.ingestion.schema import COLUMN_NAMES, REQUIRED_COLUMNS, RowError


@dataclass
class ParsedRow:
    line_number: int  # spreadsheet line number; the header is line 1
    values: dict[str, str]
    errors: list[RowError] = field(default_factory=list)


@dataclass
class ParsedFile:
    rows: list[ParsedRow] = field(default_factory=list)
    blank_rows: int = 0
    file_errors: list[dict[str, str]] = field(default_factory=list)
    warnings: list[dict[str, str]] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.file_errors


def _file_error(parsed: ParsedFile, code: str, message: str) -> ParsedFile:
    parsed.file_errors.append({"code": code, "message": message})
    return parsed


def parse_csv(content: bytes, *, max_rows: int) -> ParsedFile:
    parsed = ParsedFile()
    if not content.strip():
        return _file_error(parsed, "EMPTY_FILE", "The file is empty")
    if b"\x00" in content:
        return _file_error(parsed, "NOT_A_CSV", "The file does not look like a text CSV file")
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        return _file_error(
            parsed, "ENCODING_INVALID", "The file must be UTF-8 encoded. Re-save it as CSV UTF-8"
        )

    reader = csv.reader(io.StringIO(text, newline=""), strict=True)
    try:
        header = next(reader, None)
        while header is not None and not any(cell.strip() for cell in header):
            header = next(reader, None)
        if header is None:
            return _file_error(parsed, "EMPTY_FILE", "The file has no header row")

        headers = [h.strip().lower() for h in header]
        duplicates = sorted({h for h in headers if h and headers.count(h) > 1})
        if duplicates:
            return _file_error(
                parsed, "DUPLICATE_COLUMNS", f"Duplicate columns: {', '.join(duplicates)}"
            )
        missing = [c for c in REQUIRED_COLUMNS if c not in headers]
        if missing:
            return _file_error(
                parsed,
                "MISSING_COLUMNS",
                f"Missing required columns: {', '.join(missing)}. Download the template "
                "for the expected headers",
            )
        unknown = [h for h in headers if h and h not in COLUMN_NAMES]
        if unknown:
            parsed.warnings.append(
                {
                    "code": "UNKNOWN_COLUMNS_IGNORED",
                    "message": f"These columns are not part of the template and were ignored: "
                    f"{', '.join(unknown)}",
                }
            )

        for row in reader:
            line_number = reader.line_num
            if not any(cell.strip() for cell in row):
                parsed.blank_rows += 1
                continue
            if len(parsed.rows) >= max_rows:
                return _file_error(
                    parsed, "TOO_MANY_ROWS", f"The file has more than {max_rows} data rows"
                )
            values = {
                h: row[i] for i, h in enumerate(headers) if h in COLUMN_NAMES and i < len(row)
            }
            errors = []
            if len(row) != len(headers):
                errors.append(
                    RowError(
                        "ROW_SHAPE_INVALID",
                        f"Row has {len(row)} values but the header has {len(headers)} columns",
                    )
                )
            parsed.rows.append(ParsedRow(line_number, values, errors))
    except csv.Error as exc:
        return _file_error(
            parsed, "MALFORMED_CSV", f"The CSV is malformed near line {reader.line_num}: {exc}"
        )

    if not parsed.rows:
        return _file_error(parsed, "NO_DATA_ROWS", "The file has a header but no data rows")
    return parsed


def template_csv() -> str:
    from app.services.ingestion.schema import COLUMNS

    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow([c.name for c in COLUMNS])
    writer.writerow([c.example for c in COLUMNS])
    return buffer.getvalue()
