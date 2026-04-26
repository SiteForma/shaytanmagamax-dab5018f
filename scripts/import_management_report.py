from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from apps.api.app.db.session import SessionLocal
from apps.api.app.modules.reports.management_import import import_management_report_workbook


def main() -> None:
    parser = argparse.ArgumentParser(description="Import MAGAMAX management report workbook.")
    parser.add_argument("file_path", type=Path)
    parser.add_argument("--report-year", type=int, default=2025)
    parser.add_argument("--imported-by-id", default=None)
    args = parser.parse_args()

    with SessionLocal() as db:
        summary = import_management_report_workbook(
            db,
            args.file_path,
            report_year=args.report_year,
            imported_by_id=args.imported_by_id,
        )

    print(json.dumps(summary.__dict__, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
