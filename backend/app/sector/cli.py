import argparse
import json
from datetime import date
from typing import Optional

from backend.app.db.session import create_database_engine
from backend.app.sector.providers import FallbackSectorDataProvider
from backend.app.sector.service import generate_sector_rankings


def parse_date(value: Optional[str]) -> date:
    if not value:
        return date.today()
    return date.fromisoformat(value)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Sector ranking commands")
    subparsers = parser.add_subparsers(dest="command", required=True)
    generate = subparsers.add_parser("generate", help="Generate and store sector ranking")
    generate.add_argument("--trade-date", help="Target trade date in YYYY-MM-DD format")
    generate.add_argument("--member-fetch-limit", type=int, default=80)
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "generate":
        provider = FallbackSectorDataProvider(member_fetch_limit=args.member_fetch_limit)
        rankings = generate_sector_rankings(
            create_database_engine(),
            parse_date(args.trade_date),
            provider,
        )
        print(json.dumps([ranking.__dict__ for ranking in rankings], ensure_ascii=False, default=str, sort_keys=True))
        return

    parser.error(f"Unsupported command: {args.command}")


if __name__ == "__main__":
    main()
