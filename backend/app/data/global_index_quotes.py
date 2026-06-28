from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from datetime import date, datetime
from typing import Callable, Optional
from urllib.request import Request, urlopen


SINA_GLOBAL_INDEX_URL = "https://hq.sinajs.cn/list=gb_dji,gb_ixic,gb_inx,rt_hkHSI"


@dataclass(frozen=True)
class GlobalIndexQuote:
    name: str
    index_code: str
    trade_date: Optional[date]
    close: Optional[float]
    change: Optional[float]
    pct_chg: Optional[float]
    amount: Optional[float]


Fetcher = Callable[[str, float], str]


def load_global_index_quotes(
    fetcher: Optional[Fetcher] = None,
    timeout: float = 5.0,
) -> dict[str, GlobalIndexQuote]:
    """Load Hang Seng and major US index quotes from a separate realtime source."""
    text = (fetcher or _fetch_sina_quotes)(SINA_GLOBAL_INDEX_URL, timeout)
    return parse_sina_global_quotes(text)


def parse_sina_global_quotes(text: str) -> dict[str, GlobalIndexQuote]:
    values = {
        symbol: fields
        for symbol, fields in re.findall(r"var hq_str_([A-Za-z0-9_]+)=\"([^\"]*)\";", text)
    }
    quotes: dict[str, GlobalIndexQuote] = {}

    hsi = _parse_hsi(values.get("rt_hkHSI", ""))
    if hsi is not None:
        quotes[hsi.index_code] = hsi

    for sina_symbol, name, index_code in (
        ("gb_ixic", "纳斯达克", "IXIC"),
        ("gb_inx", "标普", "SPX"),
        ("gb_dji", "道琼斯", "DJI"),
    ):
        quote = _parse_us_index(values.get(sina_symbol, ""), name, index_code)
        if quote is not None:
            quotes[quote.index_code] = quote

    return quotes


def _fetch_sina_quotes(url: str, timeout: float) -> str:
    request = Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0",
            "Referer": "https://finance.sina.com.cn/",
        },
    )
    with urlopen(request, timeout=timeout) as response:
        return response.read().decode("gbk", errors="replace")


def _parse_hsi(raw: str) -> Optional[GlobalIndexQuote]:
    fields = raw.split(",")
    if len(fields) < 18:
        return None
    trade_date = _parse_date(fields[17], "%Y/%m/%d")
    return GlobalIndexQuote(
        name="恒生",
        index_code="HSI",
        trade_date=trade_date,
        close=_to_float(fields[6]),
        change=_to_float(fields[7]),
        pct_chg=_to_float(fields[8]),
        amount=_to_float(fields[11]),
    )


def _parse_us_index(raw: str, name: str, index_code: str) -> Optional[GlobalIndexQuote]:
    fields = raw.split(",")
    if len(fields) < 11:
        return None
    trade_date = _parse_datetime_date(fields[3])
    return GlobalIndexQuote(
        name=name,
        index_code=index_code,
        trade_date=trade_date,
        close=_to_float(fields[1]),
        change=_to_float(fields[4]),
        pct_chg=_to_float(fields[2]),
        amount=_to_float(fields[10]),
    )


def _parse_datetime_date(value: str) -> Optional[date]:
    parsed = _parse_date(value.strip().split(" ")[0], "%Y-%m-%d")
    return parsed


def _parse_date(value: str, fmt: str) -> Optional[date]:
    if not value:
        return None
    try:
        return datetime.strptime(value, fmt).date()
    except ValueError:
        return None


def _to_float(value: str) -> Optional[float]:
    if value in {"", "--"}:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def _json_default(value):
    if isinstance(value, date):
        return value.isoformat()
    raise TypeError(f"{type(value)!r} is not JSON serializable")


def main() -> int:
    try:
        quotes = load_global_index_quotes()
    except Exception as exc:  # pragma: no cover - CLI guard
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        return 1
    print(
        json.dumps(
            {"ok": True, "items": [asdict(item) for item in quotes.values()]},
            ensure_ascii=False,
            default=_json_default,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
