import argparse
import json
from datetime import date
from typing import Optional

from backend.app.candidate.providers import MissingCandidateDataTokenError, TushareDCSectorMembershipProvider
from backend.app.candidate.service import generate_candidate_stocks
from backend.app.core.config import get_settings
from backend.app.db.session import create_database_engine


def parse_date(value: Optional[str]) -> date:
    if not value:
        return date.today()
    return date.fromisoformat(value)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Candidate stock screening commands")
    subparsers = parser.add_subparsers(dest="command", required=True)
    generate = subparsers.add_parser("generate", help="Generate and store candidate stocks")
    generate.add_argument("--trade-date", help="Target trade date in YYYY-MM-DD format")
    generate.add_argument("--limit", type=int, default=50)
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "generate":
        trade_date = parse_date(args.trade_date)
        settings = get_settings()
        provider = TushareDCSectorMembershipProvider(
            token=settings.tushare_token,
            trade_date=trade_date,
        )
        try:
            candidates = generate_candidate_stocks(
                create_database_engine(),
                trade_date,
                provider,
                limit=args.limit,
            )
        except MissingCandidateDataTokenError as exc:
            parser.error(str(exc))
        print(json.dumps([candidate.__dict__ for candidate in candidates], ensure_ascii=False, default=str, sort_keys=True))
        return

    parser.error(f"Unsupported command: {args.command}")


if __name__ == "__main__":
    main()
