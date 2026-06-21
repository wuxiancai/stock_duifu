import argparse
import json
from dataclasses import asdict, is_dataclass
from datetime import date
from typing import Optional

from backend.app.db.session import create_database_engine
from backend.app.simulation.service import load_latest_simulation, run_simulation, run_simulation_workflow, run_trading_loop


def parse_date(value: Optional[str]) -> Optional[date]:
    if not value:
        return None
    return date.fromisoformat(value)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Simulation trading commands")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run = subparsers.add_parser("run", help="Run simulated trading for a trade date")
    run.add_argument("--trade-date", help="Trade date in YYYY-MM-DD format")

    workflow = subparsers.add_parser("run-workflow", help="Track trade plans, then run simulated trading")
    workflow.add_argument("--trade-date", help="Trade date in YYYY-MM-DD format")
    workflow.add_argument(
        "--mark-untriggered-at-close",
        action="store_true",
        help="Mark still-untriggered plans as 未触发 before running simulation",
    )

    loop = subparsers.add_parser("loop", help="Run simulated trading repeatedly during trading hours")
    loop.add_argument("--trade-date", help="Trade date in YYYY-MM-DD format")
    loop.add_argument("--interval-seconds", type=int, default=300, help="Polling interval, defaults to 300 seconds")
    loop.add_argument("--max-iterations", type=int, help="Optional maximum loop count for validation or supervised runs")

    subparsers.add_parser("latest", help="Print latest simulation summary")
    return parser


def _json_payload(value):
    return asdict(value) if is_dataclass(value) else value


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    engine = create_database_engine()

    if args.command == "run":
        trade_date = parse_date(args.trade_date) or date.today()
        print(json.dumps(_json_payload(run_simulation(engine, trade_date)), ensure_ascii=False, default=str, sort_keys=True))
        return

    if args.command == "run-workflow":
        trade_date = parse_date(args.trade_date) or date.today()
        print(
            json.dumps(
                _json_payload(
                    run_simulation_workflow(
                        engine,
                        trade_date,
                        mark_untriggered_at_close=args.mark_untriggered_at_close,
                    )
                ),
                ensure_ascii=False,
                default=str,
                sort_keys=True,
            )
        )
        return

    if args.command == "loop":
        trade_date = parse_date(args.trade_date) or date.today()
        print(
            json.dumps(
                _json_payload(
                    run_trading_loop(
                        engine,
                        trade_date,
                        interval_seconds=args.interval_seconds,
                        max_iterations=args.max_iterations,
                    )
                ),
                ensure_ascii=False,
                default=str,
                sort_keys=True,
            )
        )
        return

    if args.command == "latest":
        summary = load_latest_simulation(engine)
        print(json.dumps(_json_payload(summary) if summary else None, ensure_ascii=False, default=str, sort_keys=True))
        return

    parser.error(f"Unsupported command: {args.command}")


if __name__ == "__main__":
    main()
