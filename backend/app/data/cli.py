import argparse
import json
import os
from dataclasses import asdict
from datetime import date
from typing import Optional

from backend.app.data.audit import audit_market_data_coverage
from backend.app.data.ingest import ingest_market_snapshot
from backend.app.data.realtime_quotes import run_realtime_quote_workflow
from backend.app.data.target_daily import backfill_trade_plan_target_daily
from backend.app.data.providers import (
    AkShareRealtimeQuoteProvider,
    AkShareSinaMarketDataProvider,
    MissingTushareTokenError,
    TushareMarketDataProvider,
)
from backend.app.core.config import get_settings
from backend.app.db.session import create_database_engine


def parse_date(value: Optional[str]) -> Optional[date]:
    if not value:
        return None
    return date.fromisoformat(value)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Market data ingestion commands")
    subparsers = parser.add_subparsers(dest="command", required=True)

    ingest = subparsers.add_parser("ingest", help="Fetch and store a market data snapshot")
    ingest.add_argument("--provider", choices=["auto", "tushare", "akshare"], default="auto")
    ingest.add_argument("--trade-date", help="Target trade date in YYYY-MM-DD format")
    ingest.add_argument("--sample-size", type=int, default=30)
    ingest.add_argument("--all-stocks", action="store_true", help="Fetch all active stocks for the target trade date")
    ingest.add_argument("--stock-code", action="append", dest="stock_codes")

    audit = subparsers.add_parser("audit", help="Report market data coverage")
    audit.add_argument("--trade-date", required=True, help="Target trade date in YYYY-MM-DD format")

    backfill = subparsers.add_parser(
        "backfill-target-daily",
        help="Fetch missing stock_daily rows for trade plans on a target trade date",
    )
    backfill.add_argument("--provider", choices=["auto", "tushare", "akshare"], default="auto")
    backfill.add_argument("--target-trade-date", required=True, help="Target trade date in YYYY-MM-DD format")
    backfill.add_argument(
        "--include-existing",
        action="store_true",
        help="Refetch plan stocks even when stock_daily already exists",
    )

    realtime = subparsers.add_parser(
        "run-realtime-workflow",
        help="Fetch delayed realtime quotes for target trade plans, then track and simulate",
    )
    realtime.add_argument("--provider", choices=["akshare"], default="akshare")
    realtime.add_argument("--target-trade-date", required=True, help="Target trade date in YYYY-MM-DD format")
    realtime.add_argument(
        "--include-existing",
        action="store_true",
        help="Refetch plan stocks even when stock_daily already exists",
    )
    realtime.add_argument(
        "--mark-untriggered-at-close",
        action="store_true",
        help="Mark plans as untriggered when the quote range never reaches the buy interval",
    )
    realtime.add_argument(
        "--allow-date-mismatch",
        action="store_true",
        help="Allow writing the current realtime snapshot to a target date different from China today",
    )
    return parser


def load_realtime_quote_provider(provider_name: str):
    if provider_name == "akshare":
        return AkShareRealtimeQuoteProvider()
    raise ValueError(f"Unsupported realtime provider: {provider_name}")


def load_provider(provider_name: str, tushare_token: Optional[str] = None):
    token = (
        tushare_token
        if tushare_token is not None
        else os.environ.get("TUSHARE_TOKEN", "") or get_settings().tushare_token
    )
    if provider_name == "tushare":
        return TushareMarketDataProvider(token=token or "")
    if provider_name == "akshare":
        return AkShareSinaMarketDataProvider()
    if provider_name == "auto":
        if token:
            return TushareMarketDataProvider(token=token)
        return AkShareSinaMarketDataProvider()
    raise ValueError(f"Unsupported provider: {provider_name}")


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "ingest":
        provider = load_provider(args.provider)
        try:
            snapshot = provider.fetch_snapshot(
                trade_date=parse_date(args.trade_date),
                sample_size=0 if args.all_stocks else args.sample_size,
                stock_codes=args.stock_codes,
            )
        except MissingTushareTokenError as exc:
            parser.error(str(exc))
        summary = ingest_market_snapshot(create_database_engine(), snapshot)
        print(json.dumps(summary.__dict__, ensure_ascii=False, default=str, sort_keys=True))
        return

    if args.command == "audit":
        audit = audit_market_data_coverage(create_database_engine(), parse_date(args.trade_date))
        print(json.dumps(audit.__dict__, ensure_ascii=False, default=str, sort_keys=True))
        return

    if args.command == "backfill-target-daily":
        provider = load_provider(args.provider)
        try:
            result = backfill_trade_plan_target_daily(
                create_database_engine(),
                parse_date(args.target_trade_date),
                provider,
                include_existing=args.include_existing,
            )
        except MissingTushareTokenError as exc:
            parser.error(str(exc))
        print(json.dumps(asdict(result), ensure_ascii=False, default=str, sort_keys=True))
        return

    if args.command == "run-realtime-workflow":
        result = run_realtime_quote_workflow(
            create_database_engine(),
            parse_date(args.target_trade_date),
            load_realtime_quote_provider(args.provider),
            include_existing=args.include_existing,
            mark_untriggered_at_close=args.mark_untriggered_at_close,
            allow_date_mismatch=args.allow_date_mismatch,
        )
        print(json.dumps(asdict(result), ensure_ascii=False, default=str, sort_keys=True))
        return

    parser.error(f"Unsupported command: {args.command}")


if __name__ == "__main__":
    main()
