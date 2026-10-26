"""CSV export helpers with spreadsheet formula-injection protection."""

import csv
import io
from collections.abc import Iterable, Sequence
from typing import Any

from fastapi.responses import Response

UTF8_BOM = "\N{ZERO WIDTH NO-BREAK SPACE}"
_FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


def safe_cell(value: Any) -> Any:
    """Prefix text that a spreadsheet would treat as a formula with a single quote.

    Numbers are left as numbers (a negative number is data, not a formula)."""
    if value is None:
        return ""
    if isinstance(value, bool):
        return "Y" if value else "N"
    if isinstance(value, int | float):
        return value
    text = str(value)
    if text.startswith(_FORMULA_PREFIXES):
        return "'" + text
    return text


def build_csv(
    header: Sequence[str], rows: Iterable[Sequence[Any]], preamble: Sequence[Sequence[Any]] = ()
) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    for line in preamble:
        writer.writerow([safe_cell(v) for v in line])
    if preamble:
        writer.writerow([])
    writer.writerow(header)
    for row in rows:
        writer.writerow([safe_cell(v) for v in row])
    return buffer.getvalue()


def csv_response(
    header: Sequence[str],
    rows: Iterable[Sequence[Any]],
    *,
    filename: str,
    preamble: Sequence[Sequence[Any]] = (),
) -> Response:
    return Response(
        content=UTF8_BOM + build_csv(header, rows, preamble),  # BOM so Excel reads UTF-8
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-store",
        },
    )
