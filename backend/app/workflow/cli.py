import argparse
import json
from dataclasses import asdict
from datetime import date
from typing import Optional

from backend.app.candidate.providers import EastmoneyIndustrySectorMembershipProvider
from backend.app.data.cli import load_provider
from backend.app.data.providers import MissingTushareTokenError
from backend.app.db.session import create_database_engine
from backend.app.sector.providers import EastmoneyIndustrySectorDataProvider
from backend.app.workflow.service import run_after_close_workflow


def parse_date(value: Optional[str]) -> date:
    if not value:
        return date.today()
    return date.fromisoformat(value)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="MVP workflow commands")
    subparsers = parser.add_subparsers(dest="command", required=True)

    after_close = subparsers.add_parser("after-close", help="Run the PRD after-close workflow")
    after_close.add_argument("--trade-date", help="Target trade date in YYYY-MM-DD format")
    after_close.add_argument("--provider", choices=["auto", "tushare", "akshare"], default="auto")
    after_close.add_argument("--member-fetch-limit", type=int, default=80)
    after_close.add_argument("--candidate-limit", type=int, default=50)
    after_close.add_argument("--trade-plan-limit", type=int)
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "after-close":
        trade_date = parse_date(args.trade_date)
        sector_provider = EastmoneyIndustrySectorDataProvider(member_fetch_limit=args.member_fetch_limit)
        candidate_provider = EastmoneyIndustrySectorMembershipProvider(trade_date=trade_date)
        try:
            result = run_after_close_workflow(
                create_database_engine(),
                trade_date,
                load_provider(args.provider),
                sector_provider,
                candidate_provider,
                candidate_limit=args.candidate_limit,
                trade_plan_limit=args.trade_plan_limit,
            )
        except MissingTushareTokenError as exc:
            parser.error(str(exc))
        print(json.dumps(asdict(result), ensure_ascii=False, default=str, sort_keys=True))
        return

    parser.error(f"Unsupported command: {args.command}")


if __name__ == "__main__":
    main()
