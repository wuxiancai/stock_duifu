import argparse
import json
from datetime import date
from typing import Optional

from backend.app.data.ingest import ingest_market_snapshot
from backend.app.data.providers import AkShareSinaMarketDataProvider
from backend.app.db.session import create_database_engine


def parse_date(value: Optional[str]) -> Optional[date]:
    if not value:
        return None
    return date.fromisoformat(value)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Market data ingestion commands")
    subparsers = parser.add_subparsers(dest="command", required=True)

    ingest = subparsers.add_parser("ingest", help="Fetch and store a market data snapshot")
    ingest.add_argument("--provider", choices=["akshare"], default="akshare")
    ingest.add_argument("--trade-date", help="Target trade date in YYYY-MM-DD format")
    ingest.add_argument("--sample-size", type=int, default=30)
    ingest.add_argument("--stock-code", action="append", dest="stock_codes")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "ingest":
        provider = AkShareSinaMarketDataProvider()
        snapshot = provider.fetch_snapshot(
            trade_date=parse_date(args.trade_date),
            sample_size=args.sample_size,
            stock_codes=args.stock_codes,
        )
        summary = ingest_market_snapshot(create_database_engine(), snapshot)
        print(json.dumps(summary.__dict__, ensure_ascii=False, default=str, sort_keys=True))
        return

    parser.error(f"Unsupported command: {args.command}")


if __name__ == "__main__":
    main()

