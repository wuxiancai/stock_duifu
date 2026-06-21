import argparse
import json
from dataclasses import asdict
from datetime import date
from typing import Optional

from backend.app.db.session import create_database_engine
from backend.app.simulation.service import load_latest_simulation, run_simulation


def parse_date(value: Optional[str]) -> Optional[date]:
    if not value:
        return None
    return date.fromisoformat(value)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Simulation trading commands")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run = subparsers.add_parser("run", help="Run simulated trading for a trade date")
    run.add_argument("--trade-date", help="Trade date in YYYY-MM-DD format")

    subparsers.add_parser("latest", help="Print latest simulation summary")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    engine = create_database_engine()

    if args.command == "run":
        trade_date = parse_date(args.trade_date) or date.today()
        print(json.dumps(asdict(run_simulation(engine, trade_date)), ensure_ascii=False, default=str, sort_keys=True))
        return

    if args.command == "latest":
        summary = load_latest_simulation(engine)
        print(json.dumps(asdict(summary) if summary else None, ensure_ascii=False, default=str, sort_keys=True))
        return

    parser.error(f"Unsupported command: {args.command}")


if __name__ == "__main__":
    main()
