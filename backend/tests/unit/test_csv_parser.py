from app.services.ingestion.csv_parser import parse_csv, template_csv
from app.services.ingestion.schema import COLUMN_NAMES

HEADER = ",".join(COLUMN_NAMES)
ROW = (
    "DEMO-INST-001,BTECH-CSE,2026-27,AIT26CSE001,DEMO-APAAR-000123,Aarav Sharma,"
    "2008-03-14,M,2026-08-01,REGULAR,N,N,N,IN,ENROLLED"
)


def parse(text: str | bytes, max_rows: int = 100):
    return parse_csv(text.encode() if isinstance(text, str) else text, max_rows=max_rows)


def file_codes(text: str | bytes) -> list[str]:
    return [e["code"] for e in parse(text).file_errors]


def test_valid_file_with_bom_and_blank_rows():
    parsed = parse("\N{ZERO WIDTH NO-BREAK SPACE}" + HEADER + "\n" + ROW + "\n\n,,,\n" + ROW + "\n")
    assert parsed.ok
    assert [r.line_number for r in parsed.rows] == [2, 5]
    assert parsed.blank_rows == 2
    assert parsed.rows[0].values["apaar_id"] == "DEMO-APAAR-000123"


def test_headers_are_trimmed_and_case_insensitive():
    header = ",".join(f" {c.upper()} " for c in COLUMN_NAMES)
    assert parse(header + "\n" + ROW).ok


def test_empty_and_header_only_files():
    assert file_codes("") == ["EMPTY_FILE"]
    assert file_codes(HEADER + "\n") == ["NO_DATA_ROWS"]


def test_missing_and_duplicate_columns():
    assert file_codes("institution_code,programme_code\nA,B") == ["MISSING_COLUMNS"]
    assert file_codes(HEADER + ",apaar_id\n" + ROW + ",X") == ["DUPLICATE_COLUMNS"]


def test_unknown_columns_are_ignored_with_warning():
    parsed = parse(HEADER + ",remarks\n" + ROW + ",hello")
    assert parsed.ok
    assert parsed.warnings[0]["code"] == "UNKNOWN_COLUMNS_IGNORED"
    assert "remarks" not in parsed.rows[0].values


def test_row_with_wrong_number_of_values_is_flagged():
    parsed = parse(HEADER + "\n" + ROW + ",extra\n")
    assert parsed.rows[0].errors[0].code == "ROW_SHAPE_INVALID"


def test_non_utf8_and_binary_files_are_rejected():
    assert file_codes((HEADER + "\n" + ROW.replace("Aarav", "Ärav")).encode("latin-1")) == [
        "ENCODING_INVALID"
    ]
    assert file_codes(b"PK\x03\x04\x00\x00binary") == ["NOT_A_CSV"]


def test_row_limit():
    assert file_codes(HEADER + "\n" + "\n".join([ROW] * 3)) == []
    assert [e["code"] for e in parse(HEADER + "\n" + "\n".join([ROW] * 3), 2).file_errors] == [
        "TOO_MANY_ROWS"
    ]


def test_malformed_quoting():
    assert file_codes(HEADER + '\n"unterminated,' + ROW) == ["MALFORMED_CSV"]


def test_template_round_trips():
    parsed = parse(template_csv())
    assert parsed.ok and len(parsed.rows) == 1
