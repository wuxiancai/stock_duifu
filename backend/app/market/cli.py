import argparse
import json
from datetime import date
from typing import Optional

from backend.app.db.session import create_database_engine
from backend.app.market.service import generate_market_environment


def parse_date(value: Optional[str]) -> date:
    if not value:
        return date.today()
    return date.fromisoformat(value)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Market environment commands")
    subparsers = parser.add_subparsers(dest="command", required=True)
    generate = subparsers.add_parser("generate", help="Generate and store market environment")
    generate.add_argument("--trade-date", help="Target trade date in YYYY-MM-DD format")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "generate":
        result = generate_market_environment(
            create_database_engine(),
            parse_date(args.trade_date),
        )
        print(json.dumps(result.__dict__, ensure_ascii=False, default=str, sort_keys=True))
        return

    parser.error(f"Unsupported command: {args.command}")


if __name__ == "__main__":
    main()
