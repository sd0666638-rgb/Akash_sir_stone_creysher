import csv
from decimal import Decimal
from io import BytesIO, StringIO

from openpyxl import load_workbook

from app.api.reports import _csv_response, _excel_response


COLUMNS = [
    ("customer", "Customer"),
    ("amount", "Amount"),
]
ROWS = [
    {
        "customer": "=Unsafe formula",
        "amount": Decimal("1250.50"),
        "not_exported": "hidden",
    }
]


def test_excel_report_uses_explicit_columns_and_safe_cell_values():
    response = _excel_response("sales.xlsx", COLUMNS, ROWS)

    workbook = load_workbook(BytesIO(response.body), data_only=False)
    worksheet = workbook.active

    assert response.media_type == (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    assert response.headers["content-disposition"] == (
        'attachment; filename="sales.xlsx"'
    )
    assert list(worksheet.values) == [
        ("Customer", "Amount"),
        ("'=Unsafe formula", 1250.5),
    ]
    assert worksheet.freeze_panes == "A2"


def test_csv_report_is_utf8_with_explicit_columns_and_safe_cell_values():
    response = _csv_response("sales.csv", COLUMNS, ROWS)
    content = response.body.decode("utf-8-sig")
    parsed_rows = list(csv.reader(StringIO(content)))

    assert response.media_type == "text/csv; charset=utf-8"
    assert response.headers["content-disposition"] == (
        'attachment; filename="sales.csv"'
    )
    assert parsed_rows == [
        ["Customer", "Amount"],
        ["'=Unsafe formula", "1250.50"],
    ]
