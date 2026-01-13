from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT))

from app.env import load_env  # noqa: E402

load_env()

from app.db import db_connection  # noqa: E402
from app.domain.input_sources import ingest_weekly_reports  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest weekly reports")
    parser.add_argument(
        "--source",
        help="path to weekly reports JSON",
        default=None,
    )
    args = parser.parse_args()

    source_path = Path(args.source).resolve() if args.source else None
    with db_connection() as conn:
        result = ingest_weekly_reports(conn, source_path=source_path)
        print(json.dumps(result.__dict__, ensure_ascii=False))


if __name__ == "__main__":
    main()
