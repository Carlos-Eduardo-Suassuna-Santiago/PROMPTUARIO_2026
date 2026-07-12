"""Tests for the XLSX multi-sheet builder and single-sheet builder."""
from __future__ import annotations

from app.infrastructure.xlsx_builder import build_xlsx, build_multi_sheet_xlsx


class TestSingleSheetXlsx:
    def test_build_xlsx_with_data(self):
        data = [
            {"date": "2025-01-01", "consultations": 10},
            {"date": "2025-01-02", "consultations": 15},
        ]
        xlsx_bytes = build_xlsx(data, "Consultations")
        assert len(xlsx_bytes) > 0
        # Verify it's a valid XLSX by checking ZIP magic bytes
        assert xlsx_bytes[:2] == b"PK"

    def test_build_xlsx_empty_data(self):
        xlsx_bytes = build_xlsx([], "Empty")
        assert len(xlsx_bytes) > 0
        assert xlsx_bytes[:2] == b"PK"

    def test_build_xlsx_single_row(self):
        data = [{"col1": "val1", "col2": 42}]
        xlsx_bytes = build_xlsx(data, "Single")
        assert len(xlsx_bytes) > 0
        assert xlsx_bytes[:2] == b"PK"


class TestMultiSheetXlsx:
    def test_build_multi_sheet(self):
        sheets_data = [
            {
                "sheet_name": "Consults",
                "data": [
                    {"date": "2025-01-01", "val": 10},
                    {"date": "2025-01-02", "val": 20},
                ],
            },
            {
                "sheet_name": "Patients",
                "data": [
                    {"date": "2025-01-01", "new": 5},
                    {"date": "2025-01-02", "new": 8},
                ],
            },
        ]
        xlsx_bytes = build_multi_sheet_xlsx(sheets_data)
        assert len(xlsx_bytes) > 0
        assert xlsx_bytes[:2] == b"PK"

    def test_build_multi_sheet_empty_sheet(self):
        sheets_data = [
            {"sheet_name": "Empty", "data": []},
            {"sheet_name": "WithData", "data": [{"a": 1}]},
        ]
        xlsx_bytes = build_multi_sheet_xlsx(sheets_data)
        assert len(xlsx_bytes) > 0
        assert xlsx_bytes[:2] == b"PK"

    def test_build_multi_sheet_single_sheet(self):
        sheets_data = [
            {"sheet_name": "OnlyOne", "data": [{"x": 1, "y": 2}]},
        ]
        xlsx_bytes = build_multi_sheet_xlsx(sheets_data)
        assert len(xlsx_bytes) > 0
        assert xlsx_bytes[:2] == b"PK"