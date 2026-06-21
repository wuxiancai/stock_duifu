import argparse
import json
from dataclasses import asdict
from datetime import date
from typing import Optional

from backend.app.db.session import create_database_engine
from backend.app.trade.service import (
    generate_trade_plans,
    generate_trade_reviews,
    retarget_closed_trade_plans,
    track_trade_plans,
)


def parse_date(value: Optional[str]) -> Optional[date]:
    if not value:
        return None
    return date.fromisoformat(value)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Trade plan commands")
    subparsers = parser.add_subparsers(dest="command", required=True)

    generate = subparsers.add_parser("generate", help="Generate and store trade plans")
    generate.add_argument("--plan-date", help="Plan generation date in YYYY-MM-DD format")
    generate.add_argument("--target-trade-date", help="Target trade date in YYYY-MM-DD format")
    generate.add_argument("--limit", type=int)

    track = subparsers.add_parser("track", help="Track target-day trade plan status")
    track.add_argument("--target-trade-date", help="Target trade date in YYYY-MM-DD format")
    track.add_argument(
        "--mark-untriggered-at-close",
        action="store_true",
        help="Mark still-untriggered plans as 未触发 after close",
    )

    retarget = subparsers.add_parser("retarget-closed", help="Retarget plans whose target date is closed")
    retarget.add_argument("--target-trade-date", required=True, help="Closed target trade date in YYYY-MM-DD format")
    retarget.add_argument("--limit", type=int)

    review = subparsers.add_parser("review", help="Generate and store trade reviews")
    review.add_argument("--trade-date", help="Trade date in YYYY-MM-DD format")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "generate":
        plan_date = parse_date(args.plan_date) or date.today()
        plans = generate_trade_plans(
            create_database_engine(),
            plan_date,
            target_trade_date=parse_date(args.target_trade_date),
            limit=args.limit,
        )
        print(json.dumps([plan.__dict__ for plan in plans], ensure_ascii=False, default=str, sort_keys=True))
        return

    if args.command == "track":
        target_trade_date = parse_date(args.target_trade_date) or date.today()
        results = track_trade_plans(
            create_database_engine(),
            target_trade_date,
            mark_untriggered_at_close=args.mark_untriggered_at_close,
        )
        print(json.dumps([item.__dict__ for item in results], ensure_ascii=False, default=str, sort_keys=True))
        return

    if args.command == "retarget-closed":
        result = retarget_closed_trade_plans(
            create_database_engine(),
            parse_date(args.target_trade_date),
            limit=args.limit,
        )
        print(json.dumps(asdict(result), ensure_ascii=False, default=str, sort_keys=True))
        return

    if args.command == "review":
        trade_date = parse_date(args.trade_date) or date.today()
        summary = generate_trade_reviews(create_database_engine(), trade_date)
        print(json.dumps(asdict(summary), ensure_ascii=False, default=str, sort_keys=True))
        return

    parser.error(f"Unsupported command: {args.command}")


if __name__ == "__main__":
    main()
