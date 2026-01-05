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
from app.domain.watchdog import enqueue_watchdog_job  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Enqueue a watchdog job")
    parser.add_argument("--payload", help="JSON payload to attach", default=None)
    args = parser.parse_args()

    payload = json.loads(args.payload) if args.payload else None
    with db_connection() as conn:
        result = enqueue_watchdog_job(conn, payload=payload)
        print(json.dumps(result))


if __name__ == "__main__":
    main()
