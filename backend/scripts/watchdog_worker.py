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
from app.domain.watchdog import run_watchdog_job  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Run watchdog jobs")
    parser.add_argument("--job-id", help="specific watchdog job id", default=None)
    args = parser.parse_args()

    with db_connection() as conn:
        result = run_watchdog_job(conn, job_id=args.job_id)
        print(json.dumps(result))


if __name__ == "__main__":
    main()
