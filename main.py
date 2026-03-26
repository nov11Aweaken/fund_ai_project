import json
import threading
import webbrowser
import os
import sys
import logging
import tempfile
import base64
import io
import time as time_module
from contextlib import contextmanager
from datetime import datetime, time, timedelta
from pathlib import Path
from tkinter import ttk

import flet as ft
try:
    from flet_webview import WebView
except Exception:
    WebView = None
import akshare as ak
import pandas as pd
import requests
import pyecharts.options as opts
from pyecharts.charts import Line, Kline

import matplotlib
matplotlib.use("Agg")
import mplfinance as mpf
import matplotlib.pyplot as plt

from funds_manager import (
    add_fund_and_save,
    calculate_holding_metrics,
    normalize_fund_code,
    normalize_fund_items,
    preview_fund_candidate,
    remove_fund_and_save,
    update_fund_holding_and_save,
)


BG = "#F0F2F5"  # Window background
SURFACE = "#FFFFFF"  # Card surface
ACCENT = "#2196F3"
UP = "#FF5252"
DOWN = "#4CAF50"
TEXT = "#111827"
VALUE_TEXT = "#0F172A"
SUBTEXT = "#6B7280"
SURFACE_VARIANT = "#FAFAFA"  # Inner data grid / tiles

FONT_SANS = "Segoe UI"
FONT_MONO = "Consolas"
MARKET_INDEX_CONFIGS = [
    {"code": "000001", "name": "上证指数", "category": "上证系列指数"},
    {"code": "000688", "name": "科创50", "category": "上证系列指数"},
    {"code": "000016", "name": "上证50", "category": "上证系列指数"},
    {"code": "000300", "name": "沪深300", "category": "中证系列指数"},
    {"code": "399001", "name": "深证成指", "category": "深证系列指数"},
    {"code": "399006", "name": "创业板指", "category": "深证系列指数"},
    {"code": "000905", "name": "中证500", "category": "中证系列指数"},
    {"code": "000852", "name": "中证1000", "category": "中证系列指数"},
    {"code": "899050", "name": "北证50", "category": "北证系列指数"},
]
MARKET_INDEX_NAMES = [item["name"] for item in MARKET_INDEX_CONFIGS]


MARKET_PAGE_SIZE = 50
MARKET_MIN_REFRESH_SECONDS = 120


YF_GOLD = "XAUUSD=X"
FX_USDCNY = "USDCNY=X"
STOOQ_MAP = {YF_GOLD: "xauusd"}
HEADERS = {"Referer": "https://finance.sina.com.cn/", "User-Agent": "Mozilla/5.0"}
FUND_HEADERS = {"Referer": "http://fundf10.eastmoney.com/", "User-Agent": "Mozilla/5.0"}
EM_HEADERS = {"Referer": "https://quote.eastmoney.com/", "User-Agent": "Mozilla/5.0"}
REFRESH_MS = 300000  # 5分钟自动刷新
COUNTDOWN_MS = 1000


def build_market_placeholder_items() -> list[dict]:
    return [
        {"code": item["code"], "name": item["name"], "price": None, "chg": None, "pct": None}
        for item in MARKET_INDEX_CONFIGS
    ]


def _log_dir() -> Path:
    base = os.getenv("LOCALAPPDATA") or os.getenv("APPDATA")
    if base:
        p = Path(base) / "market_watch"
    else:
        p = Path(tempfile.gettempdir()) / "market_watch"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _init_logging() -> logging.Logger:
    logger = logging.getLogger("market_watch")
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)
    log_file = _log_dir() / "app.log"
    fh = logging.FileHandler(log_file, encoding="utf-8")
    fh.setLevel(logging.INFO)
    fh.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(fh)
    return logger


LOGGER = _init_logging()


PROXY_ENV_KEYS = [
    "HTTP_PROXY",
    "HTTPS_PROXY",
    "ALL_PROXY",
    "http_proxy",
    "https_proxy",
    "all_proxy",
]


@contextmanager
def _without_proxy_env():
    backup: dict[str, str] = {}
    removed: list[str] = []
    for key in PROXY_ENV_KEYS:
        if key in os.environ:
            backup[key] = os.environ[key]
            removed.append(key)
            del os.environ[key]
    try:
        yield
    finally:
        for key in removed:
            if key in backup:
                os.environ[key] = backup[key]


def _app_dir() -> Path:
    # In PyInstaller onefile/onedir, sys.executable points to the bundled exe.
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).parent


def _config_path() -> Path:
    # Prefer funds.json, but allow fund.json as a fallback.
    base = _app_dir()
    p1 = base / "funds.json"
    if p1.exists():
        return p1
    p2 = base / "fund.json"
    if p2.exists():
        return p2
    return p1


# funds.json can contain either:
# - {"funds": [{"code": "110022"}, ...]}
# - {"funds": ["110022", "161725", ...]}
DEFAULT_FUND_CONFIG = {"funds": [{"code": "110022"}]}

KLINE_PRESETS = {
    "日K": {"range": "1mo", "interval": "1d"},
    "近半年": {"range": "6mo", "interval": "1d"},
    "月K": {"range": "2y", "interval": "1mo"},
}



def load_fund_config():
    """Load fund list from config file, falling back to defaults on error."""

    try:
        cfg_path = _config_path()
        with cfg_path.open("r", encoding="utf-8") as f:
            data = json.load(f)
            return normalize_fund_items(data.get("funds") or [], ignore_invalid_holding=True)
    except FileNotFoundError:
        return DEFAULT_FUND_CONFIG["funds"]
    except Exception as exc:
        LOGGER.exception("加载基金配置失败，使用默认配置")
        return DEFAULT_FUND_CONFIG["funds"]


def fetch_gold(source: str = "sina"):
    try:
        df = ak.futures_foreign_commodity_realtime(symbol=['XAU'])
        if df is None or df.empty:
             raise ValueError("返回数据为空")

        row = df.iloc[0]
        # akshare futures_foreign_commodity_realtime columns mapping:
        # Based on manual inspection: 1:Latest, 3:Change, 4:Pct, 8:PrevClose, 12:Time, 13:Date
        current = float(row.iloc[1])
        change = float(row.iloc[3])
        pct = float(row.iloc[4])
        prev_close = float(row.iloc[8])
        date_str = str(row.iloc[13])
        time_str = str(row.iloc[12])
        ts = f"{date_str} {time_str}"

        return {
            "name": "伦敦金",
            "current": current,
            "change": change,
            "pct": pct,
            "prev_close": prev_close,
            "ts": ts,
            "source": "Akshare"
        }
    except Exception as exc:
        raise ValueError(f"Akshare黄金获取失败: {exc}")


def fetch_shanghai_gold_sge(symbol: str = "Au(T+D)"):
    """Fetch Shanghai Gold Exchange spot quotation and compute change/pct from latest two ticks."""
    try:
        df = ak.spot_quotations_sge(symbol=symbol)
    except Exception as exc:
        raise ValueError(f"SGE 行情获取失败: {exc}")

    if df is None or df.empty:
        raise ValueError("SGE 行情为空")

    try:
        df = df.dropna(subset=["现价"]).copy()
        last_row = df.iloc[-1]
        current = float(last_row["现价"])
        ts = f"{last_row.get('更新时间', '')} {last_row.get('时间', '')}".strip()

        if len(df) >= 2:
            prev = float(df.iloc[-2]["现价"])
        else:
            prev = current

        change = current - prev
        pct = (change / prev * 100) if prev else 0.0

        return {
            "name": f"上海金 {symbol}",
            "current": current,
            "change": change,
            "pct": pct,
            "prev_close": prev,
            "ts": ts or datetime.now().strftime("%Y-%m-%d %H:%M"),
            "source": "Akshare(SGE)",
        }
    except Exception as exc:
        raise ValueError(f"SGE 行情解析失败: {exc}")


def fetch_cn_indices(configs: list[dict] | None = None):
    """Fetch common CN indices spot data from Eastmoney with code-first matching."""

    def _to_float(v):
        try:
            return float(v)
        except Exception:
            return None

    def _request_json(url: str, params: dict, *, bypass_env_proxy: bool = False) -> dict:
        request_kwargs = {"params": params, "headers": EM_HEADERS, "timeout": 8}
        if bypass_env_proxy:
            with _without_proxy_env():
                session = requests.Session()
                session.trust_env = False
                resp = session.get(url, **request_kwargs)
        else:
            resp = requests.get(url, **request_kwargs)
        resp.raise_for_status()
        data_json = resp.json()
        if not isinstance(data_json, dict):
            raise ValueError("Eastmoney 返回格式异常")
        return data_json

    def _candidate_secids(code: str, category: str) -> list[str]:
        if category == "上证系列指数":
            return [f"1.{code}", f"2.{code}"]
        if category == "深证系列指数":
            return [f"0.{code}", f"47.{code}"]
        if category == "中证系列指数":
            return [f"1.{code}", f"2.{code}", f"0.{code}"]
        if category == "北证系列指数":
            return [f"0.{code}", f"47.{code}", f"1.{code}"]
        return [f"1.{code}", f"0.{code}", f"2.{code}", f"47.{code}"]

    def _fetch_index_quote(config: dict) -> dict:
        url = "https://push2.eastmoney.com/api/qt/stock/get"
        params_template = {
            "fltt": "2",
            "invt": "2",
            "fields": "f43,f57,f58,f169,f170",
        }
        retry_delays = [0.5]
        last_err = None

        for secid in _candidate_secids(config["code"], config["category"]):
            params = {**params_template, "secid": secid}

            for attempt in range(1, len(retry_delays) + 2):
                try:
                    data_json = _request_json(url, params)
                    data = data_json.get("data") or {}
                    current = _to_float(data.get("f43"))
                    name = str(data.get("f58") or "").strip()
                    returned_code = str(data.get("f57") or "").strip()
                    if current is None or returned_code != config["code"]:
                        raise ValueError("返回代码或价格无效")
                    return {
                        "code": config["code"],
                        "name": name or config["name"],
                        "current": current,
                        "change": _to_float(data.get("f169")),
                        "pct": _to_float(data.get("f170")),
                        "ts": datetime.now().strftime("%Y-%m-%d %H:%M"),
                        "source": "Eastmoney",
                    }
                except Exception as exc:
                    last_err = exc
                    if attempt <= len(retry_delays):
                        time_module.sleep(retry_delays[attempt - 1])

            try:
                data_json = _request_json(url, params, bypass_env_proxy=True)
                data = data_json.get("data") or {}
                current = _to_float(data.get("f43"))
                name = str(data.get("f58") or "").strip()
                returned_code = str(data.get("f57") or "").strip()
                if current is None or returned_code != config["code"]:
                    raise ValueError("返回代码或价格无效")
                return {
                    "code": config["code"],
                    "name": name or config["name"],
                    "current": current,
                    "change": _to_float(data.get("f169")),
                    "pct": _to_float(data.get("f170")),
                    "ts": datetime.now().strftime("%Y-%m-%d %H:%M"),
                    "source": "Eastmoney",
                }
            except Exception as exc:
                last_err = exc

        raise ValueError(f"{config['name']}({config['code']}) 抓取失败: {last_err}")

    target_configs = [
        {
            "code": str(item.get("code") or "").strip(),
            "name": str(item.get("name") or "").strip(),
            "category": str(item.get("category") or "").strip(),
        }
        for item in (configs or MARKET_INDEX_CONFIGS)
        if str(item.get("code") or "").strip() and str(item.get("name") or "").strip()
    ]
    collected: dict[str, dict] = {}
    errors: list[str] = []

    for config in target_configs:
        try:
            collected[config["code"]] = _fetch_index_quote(config)
        except Exception as exc:
            errors.append(str(exc))
            LOGGER.warning("大盘指数抓取失败: %s", exc)

    if not collected:
        raise ValueError("指数行情获取失败: " + " | ".join(errors[:3]))

    res: list[dict] = []
    for config in target_configs:
        row = collected.get(config["code"])
        if row:
            res.append(row)

    return res


def fetch_fund(code: str):
    url = f"http://fundgz.1234567.com.cn/js/{code}.js"
    resp = requests.get(url, headers=HEADERS, timeout=5)
    text = resp.text.strip()
    if resp.status_code != 200 or "jsonpgz" not in text:
        raise ValueError("基金接口返回异常")

    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("基金数据解析失败")

    data = json.loads(text[start : end + 1])
    name = data.get("name") or data.get("fS_name") or code
    est_nav = float(data["gsz"]) if data.get("gsz") else None
    prev_nav = float(data["dwjz"]) if data.get("dwjz") else None
    pct = float(data["gszzl"]) if data.get("gszzl") else None
    ts = data.get("gztime") or ""

    if est_nav is None:
        raise ValueError("基金估算净值缺失")

    change = est_nav - prev_nav if prev_nav else 0.0
    pct = pct if pct is not None else (change / prev_nav * 100 if prev_nav else 0.0)

    stats = {}
    try:
        stats = fund_history_stats(code)
    except Exception as exc:
        LOGGER.exception("基金历史获取失败: %s", code)

    return {
        "name": name,
        "current": est_nav,
        "change": change,
        "pct": pct,
        "prev_close": prev_nav or 0.0,
        "ts": ts,
        **stats,
    }


def fetch_fund_estimate(code: str):
    """Fetch fund estimate (估值) from 1234567 endpoint.

    Returns: {name, pct, ts, prev_nav, current_nav}
    """

    url = f"http://fundgz.1234567.com.cn/js/{code}.js"
    resp = requests.get(url, headers=HEADERS, timeout=5)
    text = resp.text.strip()
    if resp.status_code != 200 or "jsonpgz" not in text:
        raise ValueError("基金接口返回异常")

    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("基金数据解析失败")

    data = json.loads(text[start : end + 1])
    name = data.get("name") or data.get("fS_name") or code
    current_nav = float(data["gsz"]) if data.get("gsz") else None
    pct = float(data["gszzl"]) if data.get("gszzl") else None
    prev_nav = float(data["dwjz"]) if data.get("dwjz") else None
    ts = data.get("gztime") or ""
    return {"name": name, "pct": pct, "ts": ts, "prev_nav": prev_nav, "current_nav": current_nav}


def fund_list_stats_from_history(code: str):
    """Compute fund list stats from history.

    - prev_day_pct: last trading day pct change (last vs prev)
    """

    df = fetch_fund_history_data(code)
    series = df["单位净值"].astype(float)

    prev_day_pct = None
    latest_nav = float(series.iloc[-1]) if len(series) >= 1 else None
    history_prev_nav = float(series.iloc[-2]) if len(series) >= 2 else None
    if len(series) >= 2:
        if history_prev_nav != 0:
            prev_day_pct = (latest_nav - history_prev_nav) / history_prev_nav * 100

    return {
        "prev_day_pct": prev_day_pct,
        "latest_nav": latest_nav,
        "history_prev_nav": history_prev_nav,
    }


def fetch_usdcny():
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{FX_USDCNY}"
    params = {"range": "1d", "interval": "1m"}
    resp = requests.get(url, params=params, headers=HEADERS, timeout=6)
    result = resp.json().get("chart", {}).get("result")
    if not result:
        raise ValueError("汇率接口无数据")
    meta = result[0].get("meta", {})
    last = meta.get("regularMarketPrice")
    if not last:
        indicators = result[0].get("indicators", {}).get("quote", [{}])[0]
        closes = indicators.get("close") or []
        last = [c for c in closes if c][-1] if closes else None
    if not last:
        raise ValueError("汇率数据缺失")
    return float(last)


def fetch_fund_history_data(code: str):
    try:
        df = ak.fund_open_fund_info_em(symbol=code, indicator="单位净值走势")
    except AttributeError as exc:
        raise ValueError("当前 akshare 版本不支持 fund_open_fund_info_em") from exc
    except Exception as exc:
        raise ValueError(f"akshare 历史数据获取失败: {exc}")

    if df is None or df.empty:
        raise ValueError("基金历史数据为空")

    try:
        df = df.dropna(subset=["单位净值"]).copy()
        df["净值日期"] = pd.to_datetime(df["净值日期"], errors="coerce")
        df = df.dropna(subset=["净值日期"])
        df.sort_values("净值日期", inplace=True)
    except Exception as exc:
        raise ValueError(f"基金历史数据解析失败: {exc}")

    return df


def plot_fund_chart(code: str, name: str = ""):
    try:
        df = fetch_fund_history_data(code)
    except Exception as e:
        LOGGER.exception("制图失败: %s", code)
        return

    dates = df["净值日期"].dt.strftime("%Y-%m-%d").tolist()
    values = df["单位净值"].astype(float).tolist()

    # 简单计算均线用于显示
    ma_days = [5, 10, 20, 250]
    ma_lines = []

    # pyecharts 需要列表数据
    for d in ma_days:
        # Pandas rolling mean
        ma = df["单位净值"].rolling(window=d).mean()
        ma_list = ma.astype(float).where(pd.notnull(ma), None).tolist()
        ma_lines.append((d, ma_list))

    c = (
        Line()
        .add_xaxis(dates)
        .add_yaxis(
            "单位净值",
            values,
            is_symbol_show=False,
            label_opts=opts.LabelOpts(is_show=False),
            linestyle_opts=opts.LineStyleOpts(width=2),
        )
    )

    for d, ma_data in ma_lines:
        c.add_yaxis(
            f"MA{d}",
            ma_data,
            is_symbol_show=False,
            is_smooth=True,
            linestyle_opts=opts.LineStyleOpts(width=1),
            label_opts=opts.LabelOpts(is_show=False),
        )

    c.set_global_opts(
        title_opts=opts.TitleOpts(title=f"{name} ({code}) 净值走势"),
        tooltip_opts=opts.TooltipOpts(trigger="axis"),
        datazoom_opts=[opts.DataZoomOpts(range_start=80, range_end=100), opts.DataZoomOpts(type_="inside", range_start=80, range_end=100)],
        xaxis_opts=opts.AxisOpts(type_="category", boundary_gap=False),
        yaxis_opts=opts.AxisOpts(
            type_="value",
            is_scale=True,
        ),
        toolbox_opts=opts.ToolboxOpts(is_show=True),
    )

    filename = f"fund_{code}_chart.html"
    filepath = os.path.abspath(filename)
    c.render(filepath)
    webbrowser.open(f"file://{filepath}")


def fund_history_stats(code: str):
    """Fetch history from akshare and compute short-term changes and moving averages."""

    df = fetch_fund_history_data(code)

    try:
        navs = df["单位净值"].astype(float).tolist()
    except Exception as exc:
        raise ValueError(f"基金历史数据解析失败: {exc}")

    if not navs:
        raise ValueError("基金历史数据解析为空")

    def pct_change(days: int):
        if len(navs) <= days:
            return None
        past = navs[-days - 1]
        latest = navs[-1]
        if past == 0:
            return None
        return (latest - past) / past * 100

    def moving_avg(window: int):
        if not navs:
            return None, 0
        subset = navs[-window:]
        return sum(subset) / len(subset), len(subset)

    ma5, n5 = moving_avg(5)
    ma10, n10 = moving_avg(10)
    ma20, n20 = moving_avg(20)
    ma250, n250 = moving_avg(250)

    latest = navs[-1]
    def dist(ma_value):
        if ma_value is None or ma_value == 0:
            return None
        return (latest - ma_value) / ma_value * 100

    dist5 = dist(ma5)
    dist10 = dist(ma10)
    dist20 = dist(ma20)
    dist250 = dist(ma250)

    # 估值百分位：近窗口内最新净值所处分位
    try:
        rank = sum(1 for v in navs if v <= latest)
        percentile = rank / len(navs) * 100 if navs else None
    except Exception:
        percentile = None

    return {
        "chg3": pct_change(3),
        "chg7": pct_change(7),
        "chg15": pct_change(15),
        "chg30": pct_change(30),
        "ma5": ma5,
        "ma10": ma10,
        "ma20": ma20,
        "ma250": ma250,
        "ma5_n": n5,
        "ma10_n": n10,
        "ma20_n": n20,
        "ma250_n": n250,
        "dist_ma5": dist5,
        "dist_ma10": dist10,
        "dist_ma20": dist20,
        "dist_ma250": dist250,
        "percentile": percentile,
    }


def next_gold_open(now: datetime):
    if now.weekday() < 5:
        return None, True  # 简化为工作日 24h
    days_ahead = (7 - now.weekday()) % 7 or 1
    target_date = (now + timedelta(days=days_ahead)).date()
    return datetime.combine(target_date, time(hour=6, minute=0)), False


def fetch_kline_yahoo(symbol: str, range_str: str, interval: str):
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
    params = {"range": range_str, "interval": interval}
    resp = requests.get(url, params=params, headers=HEADERS, timeout=8)
    data = resp.json().get("chart", {}).get("result")
    if not data:
        raise ValueError("K线接口无数据")
    result = data[0]
    timestamps = result.get("timestamp")
    indicators = result.get("indicators", {}).get("quote", [{}])[0]
    opens = indicators.get("open")
    highs = indicators.get("high")
    lows = indicators.get("low")
    closes = indicators.get("close")
    if not (timestamps and opens and highs and lows and closes):
        raise ValueError("K线数据缺失")

    records = []
    for ts, o, h, l, c in zip(timestamps, opens, highs, lows, closes):
        if None in (ts, o, h, l, c):
            continue
        dt = datetime.fromtimestamp(ts)
        records.append((dt, o, h, l, c))

    if not records:
        raise ValueError("K线数据为空")

    df = pd.DataFrame(records, columns=["Date", "Open", "High", "Low", "Close"])
    df.set_index("Date", inplace=True)
    return df


def _parse_range_days(range_str: str) -> int | None:
    mapping = {
        "5d": 5,
        "1mo": 31,
        "3mo": 93,
        "6mo": 186,
        "1y": 366,
        "2y": 366 * 2,
        "5y": 366 * 5,
        "10y": 366 * 10,
        "max": None,
    }
    return mapping.get(range_str)


def fetch_kline_stooq(symbol: str, preset: dict):
    """Fetch daily K-line from Stooq.

    Note: Stooq is daily-only for this endpoint, so preset["interval"] is ignored.
    Returns DataFrame indexed by Date with columns: Open, High, Low, Close.
    """

    stooq_symbol = STOOQ_MAP.get(symbol)
    if not stooq_symbol:
        raise ValueError(f"Stooq不支持该symbol: {symbol}")

    url = f"https://stooq.com/q/d/l/?s={stooq_symbol}&i=d"
    resp = requests.get(url, headers=HEADERS, timeout=10)
    if resp.status_code != 200 or not resp.text:
        raise ValueError("Stooq接口返回异常")

    from io import StringIO

    df = pd.read_csv(StringIO(resp.text))
    if df is None or df.empty:
        raise ValueError("Stooq数据为空")

    expected = {"Date", "Open", "High", "Low", "Close"}
    if not expected.issubset(set(df.columns)):
        raise ValueError("Stooq数据列缺失")

    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    df = df.dropna(subset=["Date"]).copy()
    df.sort_values("Date", inplace=True)
    df.set_index("Date", inplace=True)

    for col in ["Open", "High", "Low", "Close"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df.dropna(subset=["Open", "High", "Low", "Close"]).copy()

    days = _parse_range_days(str(preset.get("range") or ""))
    if days is not None:
        cutoff = datetime.now() - timedelta(days=days)
        df = df[df.index >= cutoff]

    if df.empty:
        raise ValueError("Stooq过滤后无数据")

    return df


def render_gold_kline_png_bytes(preset: dict | None = None) -> bytes:
    preset = preset or {"range": "6mo", "interval": "1d"}
    try:
        df = fetch_kline_stooq(YF_GOLD, preset)
    except Exception:
        df = fetch_kline_yahoo(YF_GOLD, str(preset.get("range") or "6mo"), str(preset.get("interval") or "1d"))

    df = df[["Open", "High", "Low", "Close"]].copy()

    style = mpf.make_mpf_style(base_mpf_style="charles")
    fig, _axes = mpf.plot(
        df,
        type="candle",
        style=style,
        volume=False,
        returnfig=True,
        figsize=(9, 4.8),
        title="XAUUSD K-line",
    )
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight")
    plt.close(fig)

    return buf.getvalue()


def render_fund_nav_png_bytes(code: str) -> bytes:
    df = fetch_fund_history_data(code)
    dates = df["净值日期"]
    nav = df["单位净值"].astype(float)

    # Compute MAs on full history, but only plot the latest ~3 months.
    ma5 = nav.rolling(window=5).mean()
    ma10 = nav.rolling(window=10).mean()
    ma20 = nav.rolling(window=20).mean()
    ma250 = nav.rolling(window=250).mean()

    cutoff = pd.Timestamp.now() - pd.Timedelta(days=92)
    try:
        mask = dates >= cutoff
        if int(mask.sum()) < 10:
            raise ValueError("too few points")
        plot_dates = dates[mask]
        plot_nav = nav[mask]
        plot_ma5 = ma5[mask]
        plot_ma10 = ma10[mask]
        plot_ma20 = ma20[mask]
        plot_ma250 = ma250[mask]
    except Exception:
        # Fallback: last ~3 months worth of trading days
        plot_dates = dates.tail(60)
        plot_nav = nav.tail(60)
        plot_ma5 = ma5.tail(60)
        plot_ma10 = ma10.tail(60)
        plot_ma20 = ma20.tail(60)
        plot_ma250 = ma250.tail(60)

    fig = plt.figure(figsize=(9, 4.8), dpi=150)
    ax = fig.add_subplot(1, 1, 1)
    ax.plot(plot_dates, plot_nav, linewidth=1.6, label="NAV")
    ax.plot(plot_dates, plot_ma5, linewidth=1.0, label="MA5")
    ax.plot(plot_dates, plot_ma10, linewidth=1.0, label="MA10")
    ax.plot(plot_dates, plot_ma20, linewidth=1.0, label="MA20")
    ax.plot(plot_dates, plot_ma250, linewidth=1.0, label="MA250")
    ax.grid(True, alpha=0.25)
    ax.legend(loc="upper left")
    # Avoid chart title to prevent font/garbled text issues on some systems
    fig.autofmt_xdate(rotation=20)
    fig.tight_layout()

    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight")
    plt.close(fig)
    return buf.getvalue()


def write_dynamic_chart_html(tgt: dict) -> Path:
    name = tgt["label"].split(" ")[0]
    embed = get_chart_html(tgt["code"], name, tgt["type"])
    html = (
        "<!doctype html><html><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width, initial-scale=1'>"
        f"<title>{name} 图表</title>"
        "</head><body style='margin:0;padding:0'>"
        + embed
        + "</body></html>"
    )
    out_dir = _log_dir() / "charts"
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"dynamic_{tgt['type']}_{tgt['code']}.html"
    out.write_text(html, encoding="utf-8")
    return out



def get_chart_html(code: str, name: str = "", chart_type="fund", symbol_data=None):
    c = None
    if chart_type == "fund":
        try:
            df = fetch_fund_history_data(code)
            dates = df["净值日期"].dt.strftime("%Y-%m-%d").tolist()
            values = df["单位净值"].astype(float).tolist()

            ma_days = [5, 10, 20, 250]
            ma_lines = []
            for d in ma_days:
                ma = df["单位净值"].rolling(window=d).mean()
                ma_list = ma.astype(float).where(pd.notnull(ma), None).tolist()
                ma_lines.append((d, ma_list))

            c = (
                Line()
                .add_xaxis(dates)
                .add_yaxis(
                    "单位净值",
                    values,
                    is_symbol_show=False,
                    label_opts=opts.LabelOpts(is_show=False),
                    linestyle_opts=opts.LineStyleOpts(width=2),
                )
            )
            for d, ma_data in ma_lines:
                c.add_yaxis(
                    f"MA{d}",
                    ma_data,
                    is_symbol_show=False,
                    is_smooth=True,
                    linestyle_opts=opts.LineStyleOpts(width=1),
                    label_opts=opts.LabelOpts(is_show=False),
                )
            c.set_global_opts(
                title_opts=opts.TitleOpts(title=f"{name} ({code}) 净值走势"),
                tooltip_opts=opts.TooltipOpts(trigger="axis"),
                datazoom_opts=[opts.DataZoomOpts(range_start=80, range_end=100)],
                xaxis_opts=opts.AxisOpts(type_="category", boundary_gap=False),
                yaxis_opts=opts.AxisOpts(type_="value", is_scale=True),
            )
        except Exception:
            return "<div>暂无数据</div>"

    elif chart_type == "gold":
        # Simplified Gold K-Line using Stooq helper logic (re-implemented for pyecharts)
        try:
            # We need to fetch K-Line data here or pass it in.
            # For simplicity, we re-fetch Stooq data synchronously or reuse existing logic
            # But the existing fetch_kline_stooq is coupled? No, it's standalone.
            # We use '近半年' preset by default
            preset = {"range": "6mo", "interval": "1d"}
            try:
                df = fetch_kline_stooq("XAUUSD=X", preset)
            except Exception:
                df = fetch_kline_yahoo("XAUUSD=X", "6mo", "1d")

            dates = df.index.strftime("%Y-%m-%d").tolist()
            # Pyecharts Kline data: [Open, Close, Low, High]
            data = df[["Open", "Close", "Low", "High"]].values.tolist()

            c = (
                Kline()
                .add_xaxis(dates)
                .add_yaxis(
                    "黄金K线",
                    data,
                    itemstyle_opts=opts.ItemStyleOpts(color="#ef232a", color0="#14b143"),
                )
                .set_global_opts(
                    title_opts=opts.TitleOpts(title="伦敦金 (Stooq/Yahoo)"),
                    xaxis_opts=opts.AxisOpts(is_scale=True),
                    yaxis_opts=opts.AxisOpts(is_scale=True, splitarea_opts=opts.SplitAreaOpts(is_show=True, areastyle_opts=opts.AreaStyleOpts(opacity=1))),
                    datazoom_opts=[opts.DataZoomOpts(type_="inside", range_start=80, range_end=100), opts.DataZoomOpts(range_start=80, range_end=100)],
                    tooltip_opts=opts.TooltipOpts(trigger="axis", axis_pointer_type="cross"),
                )
            )

        except Exception as e:
            return f"<div>获取K线失败: {e}</div>"

    if c:
        return c.render_embed()
    return "<div>无法生成图表</div>"


class FletApp:
    def __init__(self, page: ft.Page):
        self.page = page
        self.page.title = "基你太美 V 0.2 by Aweaken"
        self.page.bgcolor = BG
        self.page.padding = 20
        self.page.theme = ft.Theme(font_family=FONT_SANS)
        self.page.on_close = self.on_close

        self.funds = load_fund_config()
        self._fund_name_cache: dict[str, str] = {}
        self.targets = self._build_targets()

        self.active_tab = "market"  # "market" | "fund_list" | "fund"

        self._cache: dict[str, dict] = {}
        self._pending_refresh_key: str | None = None
        self._fund_list_cache: dict[str, dict] = {}
        self._fund_list_refreshing = False
        self._pending_fund_list_refresh = False
        self._fund_list_sort_field: str | None = None
        self._fund_list_sort_desc = False

        # === Market indices view state ===1
        self._market_cache: dict[str, dict] = {}
        self._market_refreshing = False
        self._pending_market_refresh = False
        self._market_page_index = 1

        default_target = self.targets[0] if self.targets else {"code": None, "label": "暂无基金"}

        # UI Components
        self.dd_target = ft.Dropdown(
            options=[ft.dropdown.Option(key=t["code"], text=t["label"]) for t in self.targets],
            value=default_target["code"],
            on_select=self.on_target_change,
            width=440
        )
        self.btn_refresh = ft.IconButton(
            ft.Icons.REFRESH,
            on_click=self.refresh_current_view,
            icon_color=ACCENT,
            tooltip="刷新",
        )
        self.btn_dynamic_kline = ft.Button(
            "动态K线图",
            on_click=self.open_dynamic_kline,
            style=ft.ButtonStyle(
                bgcolor={ft.ControlState.DEFAULT: SURFACE},
                color={ft.ControlState.DEFAULT: ACCENT},
                overlay_color={ft.ControlState.HOVERED: "#1AFFFFFF"},
                shape={ft.ControlState.DEFAULT: ft.RoundedRectangleBorder(radius=10)},
            ),
        )

        # === Data card UI ===
        self.txt_header_title = ft.Text(
            default_target["label"],
            size=22,
            weight=ft.FontWeight.W_700,
            color=TEXT,
            no_wrap=True,
        )
        self.txt_header_time = ft.Text("", size=12, color=SUBTEXT)
        self.prg_loading = ft.ProgressRing(visible=False, width=14, height=14, stroke_width=2, color=ACCENT)
        self.prg_market_loading = ft.ProgressRing(visible=False, width=14, height=14, stroke_width=2, color=ACCENT)

        self.txt_price = ft.Text("--", size=44, weight=ft.FontWeight.BOLD, color=VALUE_TEXT, font_family=FONT_MONO)
        self.txt_change = ft.Text("", size=18, weight=ft.FontWeight.W_600, color=SUBTEXT, font_family=FONT_MONO)

        self.btn_edit_detail_holding = ft.TextButton(
            "编辑持仓",
            on_click=self.open_current_target_holding_dialog,
            style=ft.ButtonStyle(
                padding=ft.Padding(14, 10, 14, 10),
                shape=ft.RoundedRectangleBorder(radius=999),
                color={ft.ControlState.DEFAULT: ACCENT},
                bgcolor={ft.ControlState.DEFAULT: "#102196F3"},
                overlay_color={ft.ControlState.HOVERED: "#162196F3"},
            ),
        )

        self.detail_holding_tiles = [
            self._create_metric_tile("持仓份额"),
            self._create_metric_tile("持仓成本"),
            self._create_metric_tile("当日盈亏"),
            self._create_metric_tile("累计盈亏"),
        ]
        self.detail_return_tiles = [
            self._create_metric_tile("近3日"),
            self._create_metric_tile("近7日"),
            self._create_metric_tile("近15日"),
            self._create_metric_tile("近30日"),
        ]
        self.detail_ma_tiles = [
            self._create_metric_tile("估值分位"),
            self._create_metric_tile("MA5"),
            self._create_metric_tile("MA10"),
            self._create_metric_tile("MA20"),
            self._create_metric_tile("MA250"),
        ]

        # Embedded chart area: static images only
        self.chart_img = ft.Image(src=b"", visible=False, expand=True, fit=ft.BoxFit.CONTAIN)
        self.chart_loading_hint = ft.Column(
            [
                ft.ProgressRing(width=20, height=20, stroke_width=2, color=ACCENT),
                ft.Text("图表加载中...", color=SUBTEXT, size=12),
            ],
            spacing=8,
            alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            visible=False,
        )
        self.chart_view = ft.Stack(
            [
                self.chart_img,
                ft.Container(content=self.chart_loading_hint, alignment=ft.Alignment(0, 0), expand=True),
            ],
            expand=True,
        )

        def tab_btn(label: str, selected: bool, on_click):
            return ft.Button(
                label,
                on_click=on_click,
                style=ft.ButtonStyle(
                    bgcolor={ft.ControlState.DEFAULT: (ACCENT if selected else SURFACE)},
                    color={ft.ControlState.DEFAULT: (VALUE_TEXT if selected else SUBTEXT)},
                    overlay_color={ft.ControlState.HOVERED: "#1AFFFFFF"},
                    shape={ft.ControlState.DEFAULT: ft.RoundedRectangleBorder(radius=12)},
                ),
            )

        self.btn_tab_market = tab_btn("大盘行情", True, self.on_tab_market)
        self.btn_tab_fund_list = tab_btn("基金列表", False, self.on_tab_fund_list)
        self.btn_tab_fund = tab_btn("基金详情", False, self.on_tab_fund)
        tabs_row = ft.Row([self.btn_tab_market, self.btn_tab_fund_list, self.btn_tab_fund], spacing=10)

        def module_card(content: ft.Control, *, padding: int = 14, expand: bool | int | None = None):
            return ft.Container(
                content=content,
                padding=padding,
                bgcolor=SURFACE_VARIANT,
                border_radius=14,
                border=ft.Border.all(1, "#14000000"),
                shadow=ft.BoxShadow(
                    spread_radius=0,
                    blur_radius=10,
                    color="#18000000",
                    offset=ft.Offset(0, 6),
                ),
                expand=expand,
            )

        header_row = ft.Row(
            [
                ft.Column(
                    [
                        self.txt_header_title,
                        ft.Text("先看价格和盈亏概览，再看收益区间、均线和图表。", color=SUBTEXT, size=12),
                    ],
                    spacing=6,
                    expand=True,
                ),
                ft.Row([self.prg_loading, self.txt_header_time], spacing=8),
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        )

        price_row = ft.Row(
            [self.txt_price, self.txt_change],
            spacing=12,
            vertical_alignment=ft.CrossAxisAlignment.END,
        )

        header_price_card = module_card(
            ft.Column(
                [
                    header_row,
                    price_row,
                    ft.Row(
                        [
                            ft.Container(
                                content=ft.Text("基金详情概览", color=ACCENT, size=12, weight=ft.FontWeight.W_600),
                                padding=ft.Padding(10, 6, 10, 6),
                                bgcolor="#102196F3",
                                border_radius=999,
                            ),
                            ft.Container(
                                content=ft.Text("净值 / 估值实时更新", color=SUBTEXT, size=12),
                                padding=ft.Padding(10, 6, 10, 6),
                                bgcolor="#0D111827",
                                border_radius=999,
                            ),
                        ],
                        spacing=8,
                    ),
                ],
                spacing=12,
            ),
            padding=16,
        )

        chart_header = ft.Row(
            [
                ft.Column(
                    [
                        ft.Text("净值图表", color=TEXT, size=14, weight=ft.FontWeight.W_600),
                        ft.Text("图表下移，核心指标先读。", color=SUBTEXT, size=12),
                    ],
                    spacing=4,
                ),
                self.btn_dynamic_kline,
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

        self.chart_card = ft.Container(
            content=ft.Column([chart_header, self.chart_view], spacing=10, expand=True),
            expand=True,
            padding=10,
            bgcolor=SURFACE,
            border_radius=15,
            border=ft.Border.all(1, "#332196F3"),
            shadow=ft.BoxShadow(
                spread_radius=0,
                blur_radius=12,
                color="#22000000",
                offset=ft.Offset(0, 6),
            ),
        )

        top_row = ft.Row(
            [
                self.dd_target,
                ft.Row([self.btn_refresh, self.btn_edit_detail_holding], spacing=10),
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        )

        holding_section = ft.Column(
            [
                ft.Text("持仓概览", color=TEXT, size=14, weight=ft.FontWeight.W_600),
                self._build_metric_wrap_row([tile["wrapper"] for tile in self.detail_holding_tiles]),
            ],
            spacing=10,
        )

        returns_section = ft.Column(
            [
                ft.Text("收益区间", color=TEXT, size=14, weight=ft.FontWeight.W_600),
                self._build_metric_wrap_row([tile["wrapper"] for tile in self.detail_return_tiles]),
            ],
            spacing=10,
        )

        ma_section = ft.Column(
            [
                ft.Text("均线与位置", color=TEXT, size=14, weight=ft.FontWeight.W_600),
                self._build_metric_wrap_row([tile["wrapper"] for tile in self.detail_ma_tiles]),
            ],
            spacing=10,
        )

        self.info_card = ft.Container(
            content=ft.Column(
                [top_row, header_price_card, holding_section, returns_section, ma_section, self.chart_card],
                spacing=14,
                expand=True,
            ),
            padding=16,
            bgcolor=SURFACE,
            border_radius=20,
            border=ft.Border.all(1, "#14000000"),
            shadow=ft.BoxShadow(
                spread_radius=0,
                blur_radius=14,
                color="#22000000",
                offset=ft.Offset(0, 8),
            ),
            expand=True,
        )

        self.fund_panel = ft.Column(
            [self.info_card],
            spacing=16,
            expand=True,
            visible=False,
        )

        # === Fund list view ===
        self.txt_fund_list_title = ft.Text("基金概览", color=TEXT, size=20, weight=ft.FontWeight.W_700)
        self.txt_fund_list_sort_state = ft.Text("默认排序", color=SUBTEXT, size=12)

        def make_sort_btn(label, field, desc, tooltip):
            return ft.TextButton(
                label,
                on_click=lambda e: self.on_fund_list_sort(field, desc),
                tooltip=tooltip,
                style=ft.ButtonStyle(
                    padding=ft.Padding(12, 8, 12, 8),
                    shape=ft.RoundedRectangleBorder(radius=999),
                    color={ft.ControlState.DEFAULT: SUBTEXT},
                    bgcolor={ft.ControlState.DEFAULT: "#00FFFFFF"},
                    overlay_color={ft.ControlState.HOVERED: "#142196F3"},
                ),
            )

        self.btn_fund_list_sort_est_asc = make_sort_btn("估值 ↑", "est_pct", False, "实时估值升序")
        self.btn_fund_list_sort_est_desc = make_sort_btn("估值 ↓", "est_pct", True, "实时估值降序")
        self.btn_fund_list_sort_prev_asc = make_sort_btn("净值 ↑", "prev_day_pct", False, "净值变化升序")
        self.btn_fund_list_sort_prev_desc = make_sort_btn("净值 ↓", "prev_day_pct", True, "净值变化降序")
        self.txt_fund_list_page_info = ft.Text("第 1/1 页 · 共 0 条", color=SUBTEXT, size=12)
        self.prg_fund_list_loading = ft.ProgressRing(visible=False, width=14, height=14, stroke_width=2, color=ACCENT)
        self.btn_fund_list_refresh = ft.IconButton(
            ft.Icons.REFRESH,
            on_click=lambda e: self.refresh_fund_list(e),
            icon_color=ACCENT,
            tooltip="刷新基金列表",
        )
        self.btn_fund_list_add = ft.IconButton(
            ft.Icons.ADD,
            on_click=self.on_add_fund_click,
            icon_color=ACCENT,
            tooltip="添加基金",
        )
        fund_list_header_row = ft.Column(
            [
                ft.Row(
                    [
                        ft.Column(
                            [
                                self.txt_fund_list_title,
                                ft.Text("用卡片概览展示每只基金的行情、持仓与盈亏。", color=SUBTEXT, size=12),
                            ],
                            spacing=4,
                            expand=True,
                        ),
                        ft.Row(
                            [self.prg_fund_list_loading, self.btn_fund_list_refresh, self.btn_fund_list_add],
                            spacing=6,
                            alignment=ft.MainAxisAlignment.END,
                        ),
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                ft.Row(
                    [
                        ft.Container(
                            content=self.txt_fund_list_sort_state,
                            padding=ft.Padding(12, 8, 12, 8),
                            bgcolor="#0F2196F3",
                            border_radius=999,
                        ),
                        self.btn_fund_list_sort_est_asc,
                        self.btn_fund_list_sort_est_desc,
                        self.btn_fund_list_sort_prev_asc,
                        self.btn_fund_list_sort_prev_desc,
                    ],
                    spacing=8,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
            ],
            spacing=12,
        )

        self.fund_list_list = ft.ListView(
            expand=True,
            spacing=10,
            padding=0,
            auto_scroll=False,
            scroll=ft.ScrollMode.AUTO,
        )

        # One bigger rounded rectangle wrapping header + list
        self.fund_list_outer_card = ft.Container(
            content=ft.Column(
                [
                    fund_list_header_row,
                    ft.Container(height=1, bgcolor="#14000000"),
                    self.fund_list_list,
                    ft.Container(height=1, bgcolor="#14000000"),
                    ft.Row(
                        [
                            self.txt_fund_list_page_info,
                            ft.Container(),
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    ),
                ],
                spacing=12,
                expand=True,
            ),
            padding=12,
            bgcolor=SURFACE,
            border_radius=20,
            border=ft.Border.all(1, "#14000000"),
            shadow=ft.BoxShadow(
                spread_radius=0,
                blur_radius=14,
                color="#22000000",
                offset=ft.Offset(0, 8),
            ),
            expand=True,
        )

        self.fund_list_panel = ft.Column(
            [self.fund_list_outer_card],
            spacing=12,
            expand=True,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
            visible=True,
        )

        # === Market indices view ===
        self.txt_market_time = ft.Text("", color=SUBTEXT, size=12)
        self.txt_market_page_info = ft.Text("", color=SUBTEXT, size=12)
        self.btn_market_refresh = ft.IconButton(
            ft.Icons.REFRESH,
            on_click=lambda e: self.refresh_market_indices(e),
            icon_color=ACCENT,
            tooltip="刷新大盘行情",
        )

        self.btn_market_prev = ft.IconButton(
            ft.Icons.CHEVRON_LEFT,
            tooltip="上一页",
            on_click=self.on_market_prev,
            icon_color=ACCENT,
        )
        self.btn_market_next = ft.IconButton(
            ft.Icons.CHEVRON_RIGHT,
            tooltip="下一页",
            on_click=self.on_market_next,
            icon_color=ACCENT,
        )

        self.market_list = ft.ListView(
            expand=True,
            spacing=10,
            padding=0,
            auto_scroll=False,
            scroll=ft.ScrollMode.AUTO,
        )

        # Seed cache and show placeholders immediately (never blank while loading)
        self._market_cache["items"] = build_market_placeholder_items()
        self._market_cache["last_fetch_time"] = ""
        self._market_cache["last_fetch_dt"] = None
        self._market_cache["error"] = None
        self.txt_market_time.value = "拉取中..."
        self.txt_market_page_info.value = f"第 1/1 页 · 共 {len(self._market_cache['items'])} 条"
        self.btn_market_prev.disabled = True
        self.btn_market_next.disabled = True

        market_top_bar = ft.Row(
            [
                ft.Column(
                    [
                        ft.Text("大盘行情", size=20, weight=ft.FontWeight.W_700, color=TEXT),
                        ft.Text("用卡片概览快速查看指数涨跌与波动。", color=SUBTEXT, size=12),
                    ],
                    spacing=4,
                    expand=True,
                ),
                ft.Row([self.prg_market_loading, self.txt_market_time, self.btn_market_refresh], spacing=8),
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

        market_pager_bar = ft.Row(
            [
                ft.Row(
                    [
                        self.btn_market_prev,
                        self.btn_market_next,
                        ft.Container(
                            content=self.txt_market_page_info,
                            padding=ft.Padding(12, 8, 12, 8),
                            bgcolor="#0F2196F3",
                            border_radius=999,
                        ),
                    ],
                    spacing=6,
                ),
                ft.Container(),
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        )

        self.market_outer_card = ft.Container(
            content=ft.Column(
                [
                    market_top_bar,
                    ft.Container(height=1, bgcolor="#14000000"),
                    self.market_list,
                    ft.Container(height=1, bgcolor="#14000000"),
                    market_pager_bar,
                ],
                spacing=12,
                expand=True,
            ),
            padding=12,
            bgcolor=SURFACE,
            border_radius=20,
            border=ft.Border.all(1, "#14000000"),
            shadow=ft.BoxShadow(
                spread_radius=0,
                blur_radius=14,
                color="#22000000",
                offset=ft.Offset(0, 8),
            ),
            expand=True,
        )

        self.market_panel = ft.Column(
            [self.market_outer_card],
            spacing=12,
            expand=True,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
            visible=False,
        )

        self.page.add(
            ft.Column(
                [
                    tabs_row,
                    self.fund_list_panel,
                    self.market_panel,
                    self.fund_panel,
                ],
                spacing=16,
                horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
                expand=True,
            )
        )

        self.running = True
        self.current_chart_code = None
        self._refreshing = False

        # Ensure default tab is Fund List
        self._set_tab_selected("market")

        # Hydrate fund names asynchronously for Dropdown + detail view
        self._hydrate_fund_names_async()

        # Initial load
        self.refresh_market_indices()
        self.refresh_fund_list()
        self.start_timer()

        # Default placeholders
        self._clear_view_state()

    def on_close(self, e):
        self.running = False

    def _safe_run_task(self, handler, *args):
        if not getattr(self, "running", False):
            return
        try:
            self.page.run_task(handler, *args)
        except RuntimeError:
            # Session might be destroyed if the window is closed
            return

    def _fund_prev_trade_day_nav_header(self) -> str:
        dt = datetime.now().date() - timedelta(days=1)
        while dt.weekday() >= 5:
            dt = dt - timedelta(days=1)
        return f"{dt.month}-{dt.day}净值变化"

    def _set_tab_selected(self, tab: str):
        self.active_tab = tab
        is_fund = tab == "fund"
        is_fund_list = tab == "fund_list"
        is_market = tab == "market"

        # Toggle panels
        self.fund_panel.visible = is_fund
        self.fund_list_panel.visible = is_fund_list
        self.market_panel.visible = is_market

        # Toggle fund-only controls
        self.dd_target.visible = is_fund
        self.btn_dynamic_kline.visible = is_fund

        # Update button styles
        self.btn_tab_fund.style = ft.ButtonStyle(
            bgcolor={ft.ControlState.DEFAULT: (ACCENT if is_fund else SURFACE)},
            color={ft.ControlState.DEFAULT: (VALUE_TEXT if is_fund else SUBTEXT)},
            overlay_color={ft.ControlState.HOVERED: "#1AFFFFFF"},
            shape={ft.ControlState.DEFAULT: ft.RoundedRectangleBorder(radius=12)},
        )
        self.btn_tab_fund_list.style = ft.ButtonStyle(
            bgcolor={ft.ControlState.DEFAULT: (ACCENT if is_fund_list else SURFACE)},
            color={ft.ControlState.DEFAULT: (VALUE_TEXT if is_fund_list else SUBTEXT)},
            overlay_color={ft.ControlState.HOVERED: "#1AFFFFFF"},
            shape={ft.ControlState.DEFAULT: ft.RoundedRectangleBorder(radius=12)},
        )

        self.btn_tab_market.style = ft.ButtonStyle(
            bgcolor={ft.ControlState.DEFAULT: (ACCENT if is_market else SURFACE)},
            color={ft.ControlState.DEFAULT: (VALUE_TEXT if is_market else SUBTEXT)},
            overlay_color={ft.ControlState.HOVERED: "#1AFFFFFF"},
            shape={ft.ControlState.DEFAULT: ft.RoundedRectangleBorder(radius=12)},
        )

        self.page.update()

    def on_tab_fund(self, e):
        if not self.targets:
            self._show_message("暂无基金，请先添加")
            self._set_tab_selected("fund_list")
            return
        self._set_tab_selected("fund")
        self.manual_refresh()

    def on_tab_fund_list(self, e):
        self._set_tab_selected("fund_list")
        self.refresh_fund_list(e)

    def on_fund_list_sort(self, field: str, desc: bool):
        self._fund_list_sort_field = field
        self._fund_list_sort_desc = bool(desc)
        items = self._fund_list_cache.get("items") or []
        fetch_time = self._fund_list_cache.get("last_fetch_time") or datetime.now().strftime("%H:%M:%S")
        self._safe_run_task(self._update_fund_list_ui, items, fetch_time)

    def _fund_list_sort_summary(self) -> str:
        sort_field = getattr(self, "_fund_list_sort_field", None)
        sort_desc = bool(getattr(self, "_fund_list_sort_desc", False))
        if sort_field == "est_pct":
            return "按实时估值降序" if sort_desc else "按实时估值升序"
        if sort_field == "prev_day_pct":
            return "按净值变化降序" if sort_desc else "按净值变化升序"
        return "默认排序"

    def _update_fund_list_sort_icons(self):
        sort_field = getattr(self, "_fund_list_sort_field", None)
        sort_desc = bool(getattr(self, "_fund_list_sort_desc", False))
        self.txt_fund_list_sort_state.value = self._fund_list_sort_summary()

        def apply_style(button: ft.TextButton, active: bool):
            button.style = ft.ButtonStyle(
                padding=ft.Padding(12, 8, 12, 8),
                shape=ft.RoundedRectangleBorder(radius=999),
                color={ft.ControlState.DEFAULT: (ACCENT if active else SUBTEXT)},
                bgcolor={ft.ControlState.DEFAULT: ("#122196F3" if active else "#00FFFFFF")},
                overlay_color={ft.ControlState.HOVERED: "#142196F3"},
            )

        apply_style(self.btn_fund_list_sort_est_asc, sort_field == "est_pct" and not sort_desc)
        apply_style(self.btn_fund_list_sort_est_desc, sort_field == "est_pct" and sort_desc)
        apply_style(self.btn_fund_list_sort_prev_asc, sort_field == "prev_day_pct" and not sort_desc)
        apply_style(self.btn_fund_list_sort_prev_desc, sort_field == "prev_day_pct" and sort_desc)

    def _sort_fund_list_items(self, items: list[dict]) -> list[dict]:
        sort_field = getattr(self, "_fund_list_sort_field", None)
        if sort_field not in {"est_pct", "prev_day_pct"}:
            return list(items or [])

        valid_items: list[tuple[float, dict]] = []
        missing_items: list[dict] = []
        for it in items or []:
            raw = it.get(sort_field)
            try:
                value = float(raw)
            except (TypeError, ValueError):
                missing_items.append(it)
                continue
            valid_items.append((value, it))

        valid_items.sort(key=lambda x: x[0], reverse=bool(getattr(self, "_fund_list_sort_desc", False)))
        sorted_valid = [it for _, it in valid_items]
        return sorted_valid + missing_items

    def on_tab_market(self, e):
        self._set_tab_selected("market")
        # Show cached data immediately, then refresh in background if stale.
        items = self._market_cache.get("items") or []
        fetch_time = self._market_cache.get("last_fetch_time") or ""
        self._safe_run_task(self._update_market_ui, items, fetch_time)

        last_dt = self._market_cache.get("last_fetch_dt")
        stale = True
        if isinstance(last_dt, datetime):
            stale = (datetime.now() - last_dt).total_seconds() >= float(MARKET_MIN_REFRESH_SECONDS)
        if stale:
            self.refresh_market_indices(e)

    def open_fund_detail(self, code: str):
        # Switch to detail tab and select corresponding fund
        self._set_tab_selected("fund")
        self.dd_target.value = str(code)
        # Trigger refresh flow
        self.on_target_change(None)

    def _show_message(self, message: str):
        self.page.snack_bar = ft.SnackBar(content=ft.Text(message))
        self.page.snack_bar.open = True
        self.page.update()

    def _close_dialog(self):
        dialog = getattr(self.page, "dialog", None)
        LOGGER.info("关闭弹窗: 尝试 page.dialog / overlay / page.close")
        if dialog:
            try:
                dialog.open = False
                self.page.dialog = None
            except Exception:
                pass
        try:
            overlays = list(getattr(self.page, "overlay", []) or [])
            for ctrl in overlays:
                if isinstance(ctrl, ft.AlertDialog):
                    ctrl.open = False
        except Exception:
            pass
        try:
            if dialog:
                self.page.close(dialog)
        except Exception:
            pass
        self.page.update()

    def _open_dialog(self, dialog: ft.AlertDialog):
        LOGGER.info("打开弹窗: 尝试 overlay 路径")
        err = None
        try:
            overlay = getattr(self.page, "overlay", None)
            if overlay is not None:
                if dialog not in overlay:
                    overlay.append(dialog)
                dialog.open = True
                self.page.update()
                return
        except Exception as exc:
            err = exc

        LOGGER.info("打开弹窗: 尝试 page.dialog 路径")
        try:
            self.page.dialog = dialog
            dialog.open = True
            self.page.update()
            return
        except Exception as exc:
            err = exc
            LOGGER.info("打开弹窗: page.dialog 失败，回退 page.open")
        try:
            self.page.open(dialog)
        except Exception as exc:
            LOGGER.exception("打开弹窗失败")
            self._show_message(f"弹窗打开失败：{exc or err}")

    def on_add_fund_click(self, e=None):
        # Visible feedback to confirm click event is firing.
        self._show_message("正在打开添加窗口...")
        self.open_add_fund_input_dialog(e)

    def open_add_fund_input_dialog(self, e=None):
        LOGGER.info("点击添加基金按钮")
        self._add_fund_input_field = ft.TextField(
            label="基金代码",
            hint_text="例如 110022",
            autofocus=True,
            on_submit=self.on_add_fund_input_submit,
            width=260,
        )
        self._add_fund_input_hint = ft.Text("", color=SUBTEXT, size=12)
        self._add_fund_query_btn = ft.Button("确定", on_click=self.on_add_fund_input_submit)
        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("添加基金"),
            content=ft.Column(
                [
                    self._add_fund_input_field,
                    self._add_fund_input_hint,
                ],
                tight=True,
                spacing=6,
            ),
            actions=[
                ft.TextButton("取消", on_click=lambda ev: self._close_dialog()),
                self._add_fund_query_btn,
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        self._open_dialog(dialog)

    def on_add_fund_input_submit(self, e=None):
        field = getattr(self, "_add_fund_input_field", None)
        hint = getattr(self, "_add_fund_input_hint", None)
        query_btn = getattr(self, "_add_fund_query_btn", None)

        raw_code = ""
        if e is not None and getattr(e, "data", None):
            raw_code = e.data
        elif field is not None:
            raw_code = field.value or ""
        code = normalize_fund_code(raw_code)
        if not code:
            if hint is not None:
                hint.value = "请输入基金代码"
            self._show_message("请输入基金代码")
            self.page.update()
            return

        if hint is not None:
            hint.value = "查询中，请稍候..."
        if query_btn is not None:
            query_btn.disabled = True
        self.page.update()

        try:
            preview = preview_fund_candidate(code, fetch_fund_estimate)
        except ValueError as exc:
            if hint is not None:
                hint.value = f"查询失败：{exc}"
            if query_btn is not None:
                query_btn.disabled = False
            self.page.update()
            self._show_message(f"查询失败：{exc}")
            return

        if query_btn is not None:
            query_btn.disabled = False
        self._close_dialog()
        self._open_add_fund_preview_dialog(preview)

    def _open_add_fund_preview_dialog(self, preview: dict):
        pct = preview.get("pct")
        pct_text = "--"
        if pct is not None:
            try:
                v = float(pct)
                pct_text = f"{'+' if v > 0 else ''}{v:.2f}%"
            except (TypeError, ValueError):
                pct_text = "--"

        self._pending_add_preview = preview
        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("基金预览"),
            content=ft.Column(
                [
                    ft.Text(f"{preview.get('name', '')} ({preview.get('code', '')})", weight=ft.FontWeight.W_600),
                    ft.Text(f"实时估值涨跌幅：{pct_text}", color=SUBTEXT),
                ],
                tight=True,
                spacing=8,
            ),
            actions=[
                ft.TextButton("取消", on_click=lambda ev: self._close_dialog()),
                ft.Button("添加到列表", on_click=self.on_add_fund_confirm),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        self._open_dialog(dialog)

    def on_add_fund_confirm(self, e=None):
        preview = getattr(self, "_pending_add_preview", None) or {}
        code = normalize_fund_code(preview.get("code"))
        if not code:
            self._show_message("基金代码无效")
            return

        try:
            funds_path = _config_path()
            self.funds = add_fund_and_save(self.funds, code, funds_path)
        except (ValueError, OSError) as exc:
            # Close preview dialog first so failure feedback is clearly visible.
            self._close_dialog()
            self._show_message(f"添加失败：{exc}")
            return

        self.targets = self._build_targets()
        self.dd_target.options = [ft.dropdown.Option(key=t["code"], text=t["label"]) for t in self.targets]
        if self.targets:
            self.dd_target.value = self.targets[0]["code"]
        else:
            self.dd_target.value = None

        self._close_dialog()
        self._hydrate_fund_names_async()
        self.refresh_fund_list()
        self._show_message("已添加到列表")

    def _get_fund_config_item(self, code: str) -> dict:
        normalized_code = normalize_fund_code(code)
        for item in self.funds or []:
            if isinstance(item, dict) and normalize_fund_code(item.get("code")) == normalized_code:
                return item
        return {}

    def _on_holding_form_change(self, field_name: str, value: str):
        state = getattr(self, "_holding_form_state", None)
        if not isinstance(state, dict):
            state = {}
            self._holding_form_state = state
        state[field_name] = str(value or "")

    def _read_holding_form_values(self) -> tuple[str, str]:
        state = getattr(self, "_holding_form_state", None)
        if not isinstance(state, dict):
            state = {}

        units_field = getattr(self, "_holding_units_field", None)
        cost_field = getattr(self, "_holding_cost_field", None)
        units_text = str(getattr(units_field, "value", "") or state.get("units") or "").strip()
        cost_text = str(getattr(cost_field, "value", "") or state.get("cost_amount") or "").strip()
        return units_text, cost_text

    def _show_holding_form_error(self, message: str):
        error_text = getattr(self, "_holding_form_error_text", None)
        if error_text is not None:
            error_text.value = str(message or "")
            error_text.visible = bool(message)
            self.page.update()

    def _apply_holding_to_cached_items(self, code: str, holding: dict) -> tuple[list[dict], str]:
        normalized_code = normalize_fund_code(code)
        cached_items = self._fund_list_cache.get("items") or []
        fetch_time = datetime.now().strftime("%H:%M:%S")
        local_items: list[dict] = []

        for item in cached_items:
            local_item = dict(item)
            if normalize_fund_code(local_item.get("code")) == normalized_code:
                local_item["holding_units"] = holding.get("units")
                local_item["holding_cost_amount"] = holding.get("cost_amount")
                local_item.update(
                    calculate_holding_metrics(
                        units=local_item.get("holding_units"),
                        cost_amount=local_item.get("holding_cost_amount"),
                        current_nav=local_item.get("current_nav"),
                        previous_nav=local_item.get("previous_nav"),
                    )
                )
            local_items.append(local_item)

        self._fund_list_cache["items"] = local_items
        self._fund_list_cache["last_fetch_time"] = fetch_time
        return local_items, fetch_time

    def open_holding_dialog(self, code: str, name: str):
        normalized_code = normalize_fund_code(code)
        if not normalized_code:
            self._show_message("基金代码无效")
            return

        fund_item = self._get_fund_config_item(normalized_code)
        existing_holding = fund_item.get("holding") if isinstance(fund_item, dict) else {}
        units = existing_holding.get("units") if isinstance(existing_holding, dict) else None
        cost_amount = existing_holding.get("cost_amount") if isinstance(existing_holding, dict) else None

        self._pending_holding_target = {"code": normalized_code, "name": (name or "").strip() or normalized_code}
        units_value = "" if units is None else f"{float(units):.4f}".rstrip("0").rstrip(".")
        cost_value = "" if cost_amount is None else f"{float(cost_amount):.2f}"
        self._holding_form_state = {"units": units_value, "cost_amount": cost_value}
        self._holding_units_field = ft.TextField(
            label="持有份额",
            hint_text="例如 1234.56",
            value=units_value,
            autofocus=True,
            on_submit=self.on_holding_save_confirm,
            on_change=lambda e: self._on_holding_form_change("units", e.control.value),
            width=260,
        )
        self._holding_cost_field = ft.TextField(
            label="持仓成本（元）",
            hint_text="例如 1500.00",
            value=cost_value,
            on_submit=self.on_holding_save_confirm,
            on_change=lambda e: self._on_holding_form_change("cost_amount", e.control.value),
            width=260,
        )
        self._holding_form_error_text = ft.Text("", color=DOWN, size=12, visible=False)
        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text(f"编辑持仓 - {(name or normalized_code)}"),
            content=ft.Column(
                [
                    self._holding_units_field,
                    self._holding_cost_field,
                    self._holding_form_error_text,
                    ft.Text("用于计算当前市值、当日盈亏和累计盈亏。", color=SUBTEXT, size=12),
                ],
                tight=True,
                spacing=10,
            ),
            actions=[
                ft.TextButton("取消", on_click=lambda ev: self._close_dialog()),
                ft.Button("保存", on_click=self.on_holding_save_confirm),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        self._open_dialog(dialog)

    def on_holding_save_confirm(self, e=None):
        pending = getattr(self, "_pending_holding_target", None) or {}
        code = normalize_fund_code(pending.get("code"))
        if not code:
            self._show_message("基金代码无效")
            return

        units_text, cost_text = self._read_holding_form_values()
        if not units_text or not cost_text:
            self._show_holding_form_error("请填写持有份额和持仓成本")
            self._show_message("请填写持有份额和持仓成本")
            return

        try:
            units = float(units_text)
        except ValueError:
            self._show_holding_form_error("持有份额必须是数字")
            self._show_message("持有份额必须是数字")
            return

        try:
            cost_amount = float(cost_text)
        except ValueError:
            self._show_holding_form_error("持仓成本必须是数字")
            self._show_message("持仓成本必须是数字")
            return

        try:
            funds_path = _config_path()
            self.funds = update_fund_holding_and_save(self.funds, code, units, cost_amount, funds_path)
        except (ValueError, OSError) as exc:
            self._show_holding_form_error(str(exc))
            self._show_message(f"保存持仓失败：{exc}")
            return

        self._show_holding_form_error("")
        local_items, fetch_time = self._apply_holding_to_cached_items(
            code,
            {"units": units, "cost_amount": cost_amount},
        )
        self._close_dialog()
        if local_items:
            self._safe_run_task(self._update_fund_list_ui, local_items, fetch_time)
        elif self.active_tab == "fund_list":
            self.refresh_fund_list()
        if self.active_tab == "fund" and normalize_fund_code(self.current_target_data().get("code")) == code:
            self.manual_refresh()
        self._show_message("持仓已保存")

    def open_delete_fund_confirm_dialog(self, code: str, name: str):
        normalized = normalize_fund_code(code)
        if not normalized:
            self._show_message("基金代码无效")
            return

        self._pending_delete_fund = {"code": normalized, "name": (name or "").strip()}
        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("删除基金"),
            content=ft.Text(f"确认删除 {(name or normalized)} ({normalized}) 吗？"),
            actions=[
                ft.TextButton("取消", on_click=lambda ev: self._close_dialog()),
                ft.Button("确认", on_click=self.on_delete_fund_confirm),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        self._open_dialog(dialog)

    def on_delete_fund_confirm(self, e=None):
        pending = getattr(self, "_pending_delete_fund", None) or {}
        code = normalize_fund_code(pending.get("code"))
        if not code:
            self._show_message("基金代码无效")
            return

        try:
            funds_path = _config_path()
            self.funds = remove_fund_and_save(self.funds, code, funds_path)
        except (ValueError, OSError) as exc:
            self._show_message(f"删除失败：{exc}")
            return

        deleting_current = str(self.dd_target.value or "").strip() == code
        self.targets = self._build_targets()
        self.dd_target.options = [ft.dropdown.Option(key=t["code"], text=t["label"]) for t in self.targets]
        if self.targets:
            self.dd_target.value = self.targets[0]["code"]
        else:
            self.dd_target.value = None

        cached_items = self._fund_list_cache.get("items") or []
        local_items = [it for it in cached_items if str(it.get("code") or "").strip() != code]
        fetch_time = datetime.now().strftime("%H:%M:%S")
        self._fund_list_cache["items"] = local_items
        self._fund_list_cache["last_fetch_time"] = fetch_time

        self._close_dialog()
        self._set_tab_selected("fund_list" if deleting_current else self.active_tab)
        self._safe_run_task(self._update_fund_list_ui, local_items, fetch_time)
        self._show_message("已删除基金")

    def open_current_target_holding_dialog(self, e=None):
        tgt = self.current_target_data()
        code = normalize_fund_code(tgt.get("code"))
        if not code:
            self._show_message("暂无基金")
            return
        name = str(tgt.get("label") or "").strip() or code
        self.open_holding_dialog(code, name)

    def refresh_current_view(self, e):
        if self.active_tab == "fund_list":
            self.refresh_fund_list(e)
        elif self.active_tab == "market":
            self.refresh_market_indices(e)
        else:
            self.manual_refresh()

    def on_market_prev(self, e):
        if self._market_page_index > 1:
            self._market_page_index -= 1
        items = self._market_cache.get("items") or []
        fetch_time = self._market_cache.get("last_fetch_time") or ""
        self._safe_run_task(self._update_market_ui, items, fetch_time)

    def on_market_next(self, e):
        items = self._market_cache.get("items") or []
        total = len(items)
        page_size = max(1, int(MARKET_PAGE_SIZE))
        pages = max(1, (total + page_size - 1) // page_size)
        if self._market_page_index < pages:
            self._market_page_index += 1
        fetch_time = self._market_cache.get("last_fetch_time") or ""
        self._safe_run_task(self._update_market_ui, items, fetch_time)

    def refresh_market_indices(self, e=None):
        if self._market_refreshing:
            self._pending_market_refresh = True
            return

        self._market_refreshing = True
        configs = list(MARKET_INDEX_CONFIGS)
        cached_items = self._market_cache.get("items") or []
        placeholders = build_market_placeholder_items()
        show_items = cached_items if cached_items else placeholders
        show_fetch_time = self._market_cache.get("last_fetch_time") or ""
        self._market_cache["error"] = None
        self._safe_run_task(self._set_market_loading, True)
        self._safe_run_task(self._update_market_ui, show_items, show_fetch_time)

        def worker():
            fetch_time = datetime.now().strftime("%H:%M:%S")
            prev_items = self._market_cache.get("items") or []
            prev_fetch_time = self._market_cache.get("last_fetch_time") or ""

            err = None
            try:
                fetched = fetch_cn_indices(configs)
                fetched_map = {str(it.get("code") or "").strip(): it for it in (fetched or [])}

                items: list[dict] = []
                for config in configs:
                    row = fetched_map.get(config["code"])
                    if not row:
                        items.append({"code": config["code"], "name": config["name"], "price": None, "chg": None, "pct": None})
                        continue

                    items.append(
                        {
                            "code": config["code"],
                            "name": config["name"],
                            "price": row.get("current"),
                            "chg": row.get("change"),
                            "pct": row.get("pct"),
                        }
                    )

                self._market_cache["last_fetch_time"] = fetch_time
                self._market_cache["last_fetch_dt"] = datetime.now()  # record completion time
                self._market_cache["items"] = items

            except Exception as exc:
                err = str(exc)
                LOGGER.exception("市场指数刷新失败")
                items = prev_items if prev_items else placeholders
                fetch_time = prev_fetch_time
            self._market_cache["error"] = err
            self._safe_run_task(self._update_market_ui, items, fetch_time)

        def finalize():
            self._market_refreshing = False
            self._safe_run_task(self._set_market_loading, False)
            if self._pending_market_refresh:
                self._pending_market_refresh = False
                self.refresh_market_indices()

        def run_all():
            try:
                worker()
            finally:
                finalize()

        threading.Thread(target=run_all, daemon=True).start()

    async def _update_market_ui(self, items: list[dict], fetch_time: str):
        err = (self._market_cache.get("error") or "").strip()
        if err:
            safe = err.replace("\n", " ")
            if len(safe) > 120:
                safe = safe[:120] + "..."
            self.txt_market_time.value = f"更新失败 {fetch_time} · {safe}" if fetch_time else f"更新失败 · {safe}"
        elif not self._market_refreshing:
            self.txt_market_time.value = f"更新于 {fetch_time}" if fetch_time else ""

        total = len(items or [])
        page_size = max(1, int(MARKET_PAGE_SIZE))
        pages = max(1, (total + page_size - 1) // page_size)
        if self._market_page_index < 1:
            self._market_page_index = 1
        if self._market_page_index > pages:
            self._market_page_index = pages

        start = (self._market_page_index - 1) * page_size
        end = min(total, start + page_size)
        page_items = (items or [])[start:end]

        self.txt_market_page_info.value = f"第 {self._market_page_index}/{pages} 页 · 共 {total} 条"

        self.btn_market_prev.disabled = self._market_page_index <= 1
        self.btn_market_next.disabled = self._market_page_index >= pages

        def fmt_price(v):
            if v is None:
                return "--"
            try:
                return f"{float(v):.2f}"
            except Exception:
                return "--"

        def fmt_chg(v):
            if v is None:
                return "--"
            try:
                fv = float(v)
                sign = "+" if fv > 0 else ""
                return f"{sign}{fv:.2f}"
            except Exception:
                return "--"

        def fmt_pct(v):
            if v is None:
                return "--"
            try:
                fv = float(v)
                sign = "+" if fv > 0 else ""
                return f"{sign}{fv:.2f}%"
            except Exception:
                return "--"

        def col_color(v):
            try:
                fv = float(v)
            except Exception:
                return SUBTEXT
            return UP if fv > 0 else DOWN if fv < 0 else VALUE_TEXT

        rows: list[ft.Control] = []
        for it in page_items:
            card_data = self._build_market_overview_card_data(it)
            metric_controls: list[ft.Control] = []
            for metric in card_data["metrics"]:
                metric_controls.append(
                    ft.Container(
                        expand=True,
                        padding=12,
                        bgcolor="#F8FAFC",
                        border_radius=16,
                        border=ft.Border.all(1, "#120F172A"),
                        content=ft.Column(
                            [
                                ft.Text(metric["label"], color=SUBTEXT, size=11),
                                ft.Text(metric["value"], color=metric["color"], size=16, weight=ft.FontWeight.W_700, font_family=FONT_MONO),
                            ],
                            spacing=6,
                        ),
                    )
                )

            card = ft.Column(
                [
                    ft.Text(card_data["title"], color=TEXT, size=17, weight=ft.FontWeight.W_700),
                    ft.Text(card_data["subtitle"], color=SUBTEXT, size=12),
                    ft.Row(metric_controls, spacing=10),
                ],
                spacing=12,
            )
            rows.append(self._module_card(card, padding=16))

        if not rows:
            rows = [self._module_card(ft.Text("暂无数据", color=SUBTEXT), padding=12)]

        self.market_list.controls = rows
        if self.active_tab == "market":
            self.page.update()

    async def _set_market_loading(self, loading: bool):
        self.prg_market_loading.visible = loading
        if loading:
            self.txt_market_time.value = "拉取中..."
        self.btn_market_refresh.disabled = loading
        if self.active_tab == "market":
            self.page.update()

    def refresh_fund_list(self, e=None):
        import threading

        if self._fund_list_refreshing:
            self._pending_fund_list_refresh = True
            return

        self._fund_list_refreshing = True
        self._safe_run_task(self._set_fund_list_loading, True)

        def worker():
            fetch_time = datetime.now().strftime("%H:%M:%S")
            funds = self.funds or DEFAULT_FUND_CONFIG["funds"]

            items: list[dict] = []
            for f in funds:
                code = str(f.get("code") or "").strip()
                if not code:
                    continue
                cfg_name = (f.get("name") or "").strip()
                cached_name = self._fund_name_cache.get(code, "").strip()

                row = {
                    "code": code,
                    "name": cfg_name or cached_name,
                    "est_pct": None,
                    "prev_day_pct": None,
                    "current_nav": None,
                    "previous_nav": None,
                    "holding_units": None,
                    "holding_cost_amount": None,
                    "daily_profit": None,
                    "daily_profit_pct": None,
                    "total_profit": None,
                    "total_profit_pct": None,
                    "error": None,
                }

                holding = f.get("holding") if isinstance(f, dict) else None
                if isinstance(holding, dict):
                    row["holding_units"] = holding.get("units")
                    row["holding_cost_amount"] = holding.get("cost_amount")

                try:
                    est = fetch_fund_estimate(code)
                    row["name"] = cfg_name or (est.get("name") or "").strip() or cached_name or code
                    row["est_pct"] = est.get("pct")
                    row["current_nav"] = est.get("current_nav")
                    row["previous_nav"] = est.get("prev_nav")
                except Exception as exc:
                    LOGGER.exception("Fund estimate failed: %s", code)
                    row["error"] = str(exc)

                try:
                    st = fund_list_stats_from_history(code)
                    row.update(st)
                except Exception as exc:
                    LOGGER.exception("Fund history(list) failed: %s", code)
                    row["error"] = (row["error"] + " | " if row["error"] else "") + str(exc)

                if row["current_nav"] is None:
                    row["current_nav"] = row.get("latest_nav")
                if row["previous_nav"] is None:
                    row["previous_nav"] = row.get("history_prev_nav")

                row.update(
                    calculate_holding_metrics(
                        units=row.get("holding_units"),
                        cost_amount=row.get("holding_cost_amount"),
                        current_nav=row.get("current_nav"),
                        previous_nav=row.get("previous_nav"),
                    )
                )

                items.append(row)

            self._fund_list_cache["last_fetch_time"] = fetch_time
            self._fund_list_cache["items"] = items
            self._safe_run_task(self._update_fund_list_ui, items, fetch_time)

        def finalize():
            self._fund_list_refreshing = False
            self._safe_run_task(self._set_fund_list_loading, False)
            if self._pending_fund_list_refresh:
                self._pending_fund_list_refresh = False
                self.refresh_fund_list()

        def run_all():
            try:
                worker()
            finally:
                finalize()

        threading.Thread(target=run_all, daemon=True).start()

    async def _update_fund_list_ui(self, items: list[dict], fetch_time: str):
        if self.active_tab != "fund_list":
            return

        prev_nav_label = self._fund_prev_trade_day_nav_header()
        self._update_fund_list_sort_icons()
        render_items = self._sort_fund_list_items(items)
        self.txt_fund_list_page_info.value = f"第 1/1 页 · 共 {len(items or [])} 条 · 更新于 {fetch_time}"

        cards: list[ft.Control] = []
        for it in render_items:
            name = (it.get("name") or "").strip() or it.get("code")
            code = it.get("code")
            title = f"{name} ({code})" if code else name
            holding_action_label = "编辑持仓" if it.get("holding_units") is not None else "录入持仓"

            name_color = TEXT if not it.get("error") else SUBTEXT
            has_holding = it.get("holding_units") is not None
            metrics = self._build_fund_overview_metrics(it, prev_nav_label)

            tags = ft.Row(
                [
                    ft.Container(
                        content=ft.Text("估值中" if it.get("est_pct") is not None else "待刷新", size=11, color=ACCENT),
                        padding=ft.Padding(8, 4, 8, 4),
                        bgcolor="#102196F3",
                        border_radius=999,
                    ),
                    ft.Container(
                        content=ft.Text("有持仓" if has_holding else "未录入持仓", size=11, color=(TEXT if has_holding else SUBTEXT)),
                        padding=ft.Padding(8, 4, 8, 4),
                        bgcolor="#0D111827",
                        border_radius=999,
                    ),
                ],
                spacing=8,
            )

            actions = (
                ft.Row(
                    [
                        ft.TextButton(
                            "详情",
                            on_click=(lambda e, c=code: self.open_fund_detail(c)),
                            style=ft.ButtonStyle(
                                padding=ft.Padding(12, 8, 12, 8),
                                shape=ft.RoundedRectangleBorder(radius=999),
                                color={ft.ControlState.DEFAULT: ACCENT},
                                overlay_color={ft.ControlState.HOVERED: "#142196F3"},
                            ),
                        ),
                        ft.TextButton(
                            holding_action_label,
                            on_click=(lambda e, c=code, n=name: self.open_holding_dialog(c, n)),
                            style=ft.ButtonStyle(
                                padding=ft.Padding(12, 8, 12, 8),
                                shape=ft.RoundedRectangleBorder(radius=999),
                                color={ft.ControlState.DEFAULT: ACCENT},
                                bgcolor={ft.ControlState.DEFAULT: "#102196F3"},
                                overlay_color={ft.ControlState.HOVERED: "#162196F3"},
                            ),
                        ),
                        ft.IconButton(
                            ft.Icons.DELETE_OUTLINE,
                            on_click=(lambda e, c=code, n=name: self.open_delete_fund_confirm_dialog(c, n)),
                            icon_color=DOWN,
                            tooltip="删除基金",
                        ),
                    ],
                    spacing=6,
                )
                if code
                else ft.Text("", color=SUBTEXT)
            )

            metric_controls = []
            for metric in metrics:
                metric_controls.append(
                    ft.Container(
                        expand=True,
                        padding=12,
                        bgcolor="#F8FAFC",
                        border_radius=16,
                        border=ft.Border.all(1, "#120F172A"),
                        content=ft.Column(
                            [
                                ft.Text(metric["label"], color=SUBTEXT, size=11),
                                ft.Text(metric["primary"], color=metric["color"], size=16, weight=ft.FontWeight.W_700, font_family=FONT_MONO),
                                ft.Text(metric["secondary"], color=SUBTEXT, size=11, no_wrap=True),
                            ],
                            spacing=6,
                        ),
                    )
                )

            card = ft.Column(
                [
                    ft.Text(title, color=name_color, size=17, weight=ft.FontWeight.W_700, no_wrap=True),
                    tags,
                    actions,
                    ft.Row(metric_controls, spacing=10),
                ],
                spacing=12,
            )
            cards.append(self._module_card(card, padding=16))

        self.fund_list_list.controls = cards
        self.page.update()

    async def _set_fund_list_loading(self, loading: bool):
        self.prg_fund_list_loading.visible = loading
        self.btn_fund_list_refresh.disabled = loading
        if loading:
            last = self._fund_list_cache.get("last_fetch_time")
            self.txt_fund_list_page_info.value = f"第 1/1 页 · 拉取中... | 上次更新 {last}" if last else "第 1/1 页 · 拉取中..."
        if self.active_tab == "fund_list":
            self.page.update()

    def _set_metric_spans(self, control: ft.Text, label: str, value: str, value_color: str = VALUE_TEXT):
        control.spans = [
            ft.TextSpan(f"{label}: ", style=ft.TextStyle(color=SUBTEXT)),
            ft.TextSpan(value, style=ft.TextStyle(color=value_color, weight=ft.FontWeight.W_600)),
        ]

    def _create_metric_tile(self, label: str, *, width: int = 220) -> dict:
        label_text = ft.Text(label, color=SUBTEXT, size=11)
        value_text = ft.Text("--", color=VALUE_TEXT, size=17, weight=ft.FontWeight.W_700, font_family=FONT_MONO)
        subtitle_text = ft.Text("", color=SUBTEXT, size=11)
        card = self._module_card(ft.Column([label_text, value_text, subtitle_text], spacing=6), padding=12)
        return {
            "wrapper": ft.Container(width=width, content=card),
            "label": label_text,
            "value": value_text,
            "subtitle": subtitle_text,
        }

    def _build_metric_wrap_row(self, controls: list[ft.Control]) -> ft.Row:
        return ft.Row(
            controls,
            spacing=12,
            wrap=True,
            run_spacing=12,
            vertical_alignment=ft.CrossAxisAlignment.START,
        )

    def _apply_metric_tile(self, tile: dict, *, label: str, value: str, subtitle: str = "", color: str = VALUE_TEXT):
        tile["label"].value = label
        tile["value"].value = value
        tile["value"].color = color
        tile["subtitle"].value = subtitle

    def _format_pct_value(self, raw_value, *, signed: bool = True) -> str:
        if raw_value is None:
            return "--"
        try:
            value = float(raw_value)
        except (TypeError, ValueError):
            return "--"
        if signed:
            return f"{'+' if value > 0 else ''}{value:.2f}%"
        return f"{value:.2f}%"

    def _format_number_value(self, raw_value, *, digits: int = 2, suffix: str = "") -> str:
        if raw_value is None:
            return "--"
        try:
            value = float(raw_value)
        except (TypeError, ValueError):
            return "--"
        return f"{value:.{digits}f}{suffix}"

    def _format_money_value(self, raw_value, *, signed: bool = False) -> str:
        if raw_value is None:
            return "--"
        try:
            value = float(raw_value)
        except (TypeError, ValueError):
            return "--"
        if signed:
            return f"+¥{value:.2f}" if value > 0 else f"-¥{abs(value):.2f}" if value < 0 else f"¥{value:.2f}"
        return f"¥{value:.2f}"

    def _metric_color(self, raw_value, default: str = VALUE_TEXT) -> str:
        if raw_value is None:
            return SUBTEXT
        try:
            value = float(raw_value)
        except (TypeError, ValueError):
            return SUBTEXT
        return UP if value > 0 else DOWN if value < 0 else default

    def _build_market_overview_card_data(self, item: dict) -> dict:
        code = str(item.get("code") or "").strip()
        return {
            "title": (item.get("name") or "").strip() or "--",
            "subtitle": f"代码 {code}" if code else "指数",
            "metrics": [
                {"label": "最新价", "value": FletApp._format_number_value(self, item.get("price")), "color": VALUE_TEXT},
                {"label": "涨跌", "value": FletApp._format_number_value(self, item.get("chg")), "color": FletApp._metric_color(self, item.get("chg"))},
                {"label": "涨跌幅", "value": FletApp._format_pct_value(self, item.get("pct")), "color": FletApp._metric_color(self, item.get("pct"))},
            ],
        }

    def _build_fund_detail_holding_metrics(self, item: dict) -> list[dict]:
        return [
            {
                "label": "持仓份额",
                "value": FletApp._format_number_value(self, item.get("holding_units"), suffix="份"),
                "subtitle": "当前持有份额",
                "color": VALUE_TEXT if item.get("holding_units") is not None else SUBTEXT,
            },
            {
                "label": "持仓成本",
                "value": FletApp._format_money_value(self, item.get("holding_cost_amount")),
                "subtitle": "当前总持仓成本",
                "color": VALUE_TEXT if item.get("holding_cost_amount") is not None else SUBTEXT,
            },
            {
                "label": "当日盈亏",
                "value": FletApp._format_money_value(self, item.get("daily_profit"), signed=True),
                "subtitle": "按估值与昨收净值计算",
                "color": FletApp._metric_color(self, item.get("daily_profit")),
            },
            {
                "label": "累计盈亏",
                "value": FletApp._format_money_value(self, item.get("total_profit"), signed=True),
                "subtitle": "当前市值 - 持仓成本",
                "color": FletApp._metric_color(self, item.get("total_profit")),
            },
        ]

    def _build_fund_detail_return_metrics(self, res: dict) -> list[dict]:
        return [
            {"label": "近3日", "value": self._format_pct_value(res.get("chg3")), "subtitle": "短线表现", "color": self._metric_color(res.get("chg3"))},
            {"label": "近7日", "value": self._format_pct_value(res.get("chg7")), "subtitle": "一周趋势", "color": self._metric_color(res.get("chg7"))},
            {"label": "近15日", "value": self._format_pct_value(res.get("chg15")), "subtitle": "半月趋势", "color": self._metric_color(res.get("chg15"))},
            {"label": "近30日", "value": self._format_pct_value(res.get("chg30")), "subtitle": "月度表现", "color": self._metric_color(res.get("chg30"))},
        ]

    def _build_fund_detail_ma_metrics(self, res: dict) -> list[dict]:
        metrics = [
            {"label": "估值分位", "value": self._format_pct_value(res.get("percentile"), signed=False), "subtitle": "近历史区间位置", "color": VALUE_TEXT},
        ]
        for label, ma_key, dist_key in [
            ("MA5", "ma5", "dist_ma5"),
            ("MA10", "ma10", "dist_ma10"),
            ("MA20", "ma20", "dist_ma20"),
            ("MA250", "ma250", "dist_ma250"),
        ]:
            metrics.append(
                {
                    "label": label,
                    "value": self._format_number_value(res.get(ma_key), digits=4),
                    "subtitle": f"偏离 {self._format_pct_value(res.get(dist_key))}",
                    "color": self._metric_color(res.get(dist_key), VALUE_TEXT),
                }
            )
        return metrics

    def _apply_metric_group(self, tiles: list[dict], metrics: list[dict]):
        for index, tile in enumerate(tiles):
            metric = metrics[index] if index < len(metrics) else {"label": "--", "value": "--", "subtitle": "", "color": SUBTEXT}
            self._apply_metric_tile(
                tile,
                label=metric.get("label", "--"),
                value=metric.get("value", "--"),
                subtitle=metric.get("subtitle", ""),
                color=metric.get("color", VALUE_TEXT),
            )

    def _build_fund_overview_metrics(self, item: dict, prev_nav_label: str) -> list[dict]:
        def pct_text(raw_value):
            if raw_value is None:
                return "--"
            try:
                value = float(raw_value)
            except (TypeError, ValueError):
                return "--"
            return f"{'+' if value > 0 else ''}{value:.2f}%"

        def number_text(raw_value, suffix=""):
            if raw_value is None:
                return "--"
            try:
                value = float(raw_value)
            except (TypeError, ValueError):
                return "--"
            return f"{value:.2f}{suffix}"

        def money_text(raw_value, *, signed=False):
            if raw_value is None:
                return "--"
            try:
                value = float(raw_value)
            except (TypeError, ValueError):
                return "--"
            if signed:
                return f"+¥{value:.2f}" if value > 0 else f"-¥{abs(value):.2f}" if value < 0 else f"¥{value:.2f}"
            return f"¥{value:.2f}"

        return [
            {
                "label": "行情",
                "primary": pct_text(item.get("est_pct")),
                "secondary": f"{prev_nav_label} {pct_text(item.get('prev_day_pct'))}",
                "color": (UP if (item.get("est_pct") or 0) > 0 else DOWN if (item.get("est_pct") or 0) < 0 else VALUE_TEXT)
                if item.get("est_pct") is not None
                else SUBTEXT,
            },
            {
                "label": "持仓",
                "primary": number_text(item.get("holding_units"), "份"),
                "secondary": f"持仓成本 {money_text(item.get('holding_cost_amount'))}",
                "color": VALUE_TEXT if item.get("holding_units") is not None else SUBTEXT,
            },
            {
                "label": "当日盈亏",
                "primary": money_text(item.get("daily_profit"), signed=True),
                "secondary": "根据当日估值计算" if item.get("daily_profit") is not None else "录入持仓后显示",
                "color": (UP if (item.get("daily_profit") or 0) > 0 else DOWN if (item.get("daily_profit") or 0) < 0 else VALUE_TEXT)
                if item.get("daily_profit") is not None
                else SUBTEXT,
            },
            {
                "label": "累计盈亏",
                "primary": money_text(item.get("total_profit"), signed=True),
                "secondary": "当前市值 - 持仓成本" if item.get("total_profit") is not None else "录入持仓后显示",
                "color": (UP if (item.get("total_profit") or 0) > 0 else DOWN if (item.get("total_profit") or 0) < 0 else VALUE_TEXT)
                if item.get("total_profit") is not None
                else SUBTEXT,
            },
        ]

    def _pct_cell(self, raw_value) -> ft.DataCell:
        return ft.DataCell(self._pct_text(raw_value))

    def _pct_text(self, raw_value) -> ft.Text:
        if raw_value is None:
            return ft.Text("--", color=SUBTEXT, font_family=FONT_MONO, text_align=ft.TextAlign.CENTER)

        try:
            v = float(raw_value)
        except Exception:
            return ft.Text("--", color=SUBTEXT, font_family=FONT_MONO, text_align=ft.TextAlign.CENTER)

        color = UP if v > 0 else DOWN if v < 0 else VALUE_TEXT
        sign = "+" if v > 0 else ""
        return ft.Text(
            f"{sign}{v:.2f}%",
            color=color,
            weight=ft.FontWeight.W_600,
            font_family=FONT_MONO,
            text_align=ft.TextAlign.CENTER,
        )

    def _number_text(self, raw_value, *, digits: int = 2, suffix: str = "") -> ft.Text:
        if raw_value is None:
            return ft.Text("--", color=SUBTEXT, font_family=FONT_MONO, text_align=ft.TextAlign.CENTER)

        try:
            value = float(raw_value)
        except (TypeError, ValueError):
            return ft.Text("--", color=SUBTEXT, font_family=FONT_MONO, text_align=ft.TextAlign.CENTER)

        return ft.Text(
            f"{value:.{digits}f}{suffix}",
            color=VALUE_TEXT,
            weight=ft.FontWeight.W_600,
            font_family=FONT_MONO,
            text_align=ft.TextAlign.CENTER,
        )

    def _money_text(self, raw_value, *, colorize: bool = False) -> ft.Text:
        if raw_value is None:
            return ft.Text("--", color=SUBTEXT, font_family=FONT_MONO, text_align=ft.TextAlign.CENTER)

        try:
            value = float(raw_value)
        except (TypeError, ValueError):
            return ft.Text("--", color=SUBTEXT, font_family=FONT_MONO, text_align=ft.TextAlign.CENTER)

        if colorize:
            color = UP if value > 0 else DOWN if value < 0 else VALUE_TEXT
            text = f"+¥{value:.2f}" if value > 0 else f"-¥{abs(value):.2f}" if value < 0 else f"¥{value:.2f}"
        else:
            color = VALUE_TEXT
            text = f"¥{value:.2f}"

        return ft.Text(
            text,
            color=color,
            weight=ft.FontWeight.W_600,
            font_family=FONT_MONO,
            text_align=ft.TextAlign.CENTER,
        )

    def _module_card(self, content: ft.Control, *, padding: int = 14, expand: bool | int | None = None) -> ft.Container:
        return ft.Container(
            content=content,
            padding=padding,
            bgcolor=SURFACE_VARIANT,
            border_radius=14,
            border=ft.Border.all(1, "#14000000"),
            shadow=ft.BoxShadow(
                spread_radius=0,
                blur_radius=10,
                color="#18000000",
                offset=ft.Offset(0, 6),
            ),
            expand=expand,
        )

    def _fund_list_right_cell(self, content: ft.Control) -> ft.Container:
        return ft.Container(
            width=getattr(self, "_fund_list_pct_width", 110),
            alignment=ft.Alignment(0, 0),
            content=ft.Row([content], alignment=ft.MainAxisAlignment.CENTER, expand=True),
            padding=0,
        )

    def _fund_list_action_cell(self, content: ft.Control) -> ft.Container:
        return ft.Container(
            width=getattr(self, "_fund_list_action_width", 70),
            content=ft.Row([content], alignment=ft.MainAxisAlignment.CENTER),
            padding=0,
        )

    def _txt_cell(
        self,
        text: str,
        color: str = VALUE_TEXT,
        *,
        weight: str | None = None,
        monospace: bool = False,
    ) -> ft.DataCell:
        return ft.DataCell(
            ft.Text(
                text,
                color=color,
                weight=weight or ft.FontWeight.W_600,
                font_family=(FONT_MONO if monospace else FONT_SANS),
            )
        )

    def _set_returns_table(self, chg3_raw, chg7_raw, chg15_raw, chg30_raw):
        self.tbl_returns.rows = [
            ft.DataRow(cells=[self._txt_cell("近3日", SUBTEXT, weight=ft.FontWeight.W_500), self._pct_cell(chg3_raw)]),
            ft.DataRow(cells=[self._txt_cell("近7日", SUBTEXT, weight=ft.FontWeight.W_500), self._pct_cell(chg7_raw)]),
            ft.DataRow(cells=[self._txt_cell("近15日", SUBTEXT, weight=ft.FontWeight.W_500), self._pct_cell(chg15_raw)]),
            ft.DataRow(cells=[self._txt_cell("近30日", SUBTEXT, weight=ft.FontWeight.W_500), self._pct_cell(chg30_raw)]),
        ]

    def _set_ma_table(
        self,
        ma5: str,
        ma10: str,
        ma20: str,
        ma250: str,
        dist5: str,
        dist10: str,
        dist20: str,
        dist250: str,
        dist5_color: str,
        dist10_color: str,
        dist20_color: str,
        dist250_color: str,
    ):
        self.tbl_ma.rows = [
            ft.DataRow(
                cells=[
                    self._txt_cell("MA5", SUBTEXT, weight=ft.FontWeight.W_500),
                    self._txt_cell(ma5, VALUE_TEXT, monospace=True),
                    self._txt_cell(dist5, dist5_color, monospace=True),
                ]
            ),
            ft.DataRow(
                cells=[
                    self._txt_cell("MA10", SUBTEXT, weight=ft.FontWeight.W_500),
                    self._txt_cell(ma10, VALUE_TEXT, monospace=True),
                    self._txt_cell(dist10, dist10_color, monospace=True),
                ]
            ),
            ft.DataRow(
                cells=[
                    self._txt_cell("MA20", SUBTEXT, weight=ft.FontWeight.W_500),
                    self._txt_cell(ma20, VALUE_TEXT, monospace=True),
                    self._txt_cell(dist20, dist20_color, monospace=True),
                ]
            ),
            ft.DataRow(
                cells=[
                    self._txt_cell("MA250", SUBTEXT, weight=ft.FontWeight.W_500),
                    self._txt_cell(ma250, VALUE_TEXT, monospace=True),
                    self._txt_cell(dist250, dist250_color, monospace=True),
                ]
            ),
        ]

    def _cache_key(self, tgt: dict) -> str:
        return str(tgt.get("key") or tgt.get("code") or "")

    def _clear_view_state(self):
        self.txt_header_title.value = self.current_target_data().get("label", "")
        self.txt_header_time.value = ""
        self.txt_price.value = "--"
        self.txt_change.value = ""
        self.txt_change.color = SUBTEXT
        self._apply_metric_group(
            self.detail_holding_tiles,
            self._build_fund_detail_holding_metrics(
                {"holding_units": None, "holding_cost_amount": None, "daily_profit": None, "total_profit": None}
            ),
        )
        self._apply_metric_group(
            self.detail_return_tiles,
            self._build_fund_detail_return_metrics({"chg3": None, "chg7": None, "chg15": None, "chg30": None}),
        )
        self._apply_metric_group(
            self.detail_ma_tiles,
            self._build_fund_detail_ma_metrics(
                {"percentile": None, "ma5": None, "ma10": None, "ma20": None, "ma250": None, "dist_ma5": None, "dist_ma10": None, "dist_ma20": None, "dist_ma250": None}
            ),
        )

        self.chart_img.visible = False
        self.chart_img.src = b""
        self.chart_loading_hint.visible = True

    def _apply_cached_state(self, cache_key: str):
        st = self._cache.get(cache_key)
        if not st:
            return

        self.txt_header_title.value = st.get("txt_title", self.current_target_data().get("label", ""))
        self.txt_header_time.value = st.get("txt_header_time", "")
        self.txt_price.value = st.get("txt_price", "--")
        self.txt_change.value = st.get("txt_change", "")
        self.txt_change.color = st.get("txt_change_color", SUBTEXT)
        self._apply_metric_group(
            self.detail_holding_tiles,
            self._build_fund_detail_holding_metrics(st.get("detail_holding_raw") or {}),
        )
        self._apply_metric_group(
            self.detail_return_tiles,
            self._build_fund_detail_return_metrics(st.get("detail_return_raw") or {}),
        )
        self._apply_metric_group(
            self.detail_ma_tiles,
            self._build_fund_detail_ma_metrics(st.get("detail_ma_raw") or {}),
        )

        png = st.get("chart_png")
        if isinstance(png, (bytes, bytearray)) and len(png) > 0:
            self.chart_img.src = bytes(png)
            self.chart_img.visible = True
            self.chart_loading_hint.visible = False
        else:
            self.chart_img.visible = False
            self.chart_img.src = b""
            self.chart_loading_hint.visible = True

    def _build_targets(self):
        targets = []

        funds = self.funds or DEFAULT_FUND_CONFIG["funds"]
        for item in funds:
            code = str(item.get("code") or "").strip()
            if not code:
                continue

            cfg_name = (item.get("name") or "").strip()
            label_name = cfg_name or self._fund_name_cache.get(code, "").strip() or code
            targets.append({"key": f"fund:{code}", "label": f"{label_name} ({code})", "type": "fund", "code": code})
        return targets

    def current_target_data(self):
        if not self.targets:
            return {}
        code = str(self.dd_target.value or "").strip()
        for t in self.targets:
            if str(t.get("code")) == code:
                return t
        return self.targets[0] if self.targets else {}

    def _hydrate_fund_names_async(self):
        # Fetch fund names by code and update dropdown/targets without requiring names in funds.json
        def worker():
            mapping: dict[str, str] = {}
            for t in self.targets:
                code = str(t.get("code") or "").strip()
                if not code:
                    continue
                cached_name = self._fund_name_cache.get(code, "").strip()
                if cached_name:
                    mapping[code] = cached_name
                    continue
                try:
                    est = fetch_fund_estimate(code)
                    name = (est.get("name") or "").strip()
                    if name:
                        mapping[code] = name
                except Exception:
                    continue

            if not mapping:
                return

            self._fund_name_cache.update(mapping)
            self._safe_run_task(self._apply_fund_name_mapping, mapping)

        threading.Thread(target=worker, daemon=True).start()

    async def _apply_fund_name_mapping(self, mapping: dict[str, str]):
        # Update targets labels
        for t in self.targets:
            code = str(t.get("code") or "").strip()
            if code in mapping:
                t["label"] = f"{mapping[code]} ({code})"

        # Update dropdown option texts (keep value stable as code)
        if self.dd_target.options:
            for opt in self.dd_target.options:
                try:
                    k = str(getattr(opt, "key", "") or "").strip()
                    if k in mapping:
                        opt.text = f"{mapping[k]} ({k})"
                except Exception:
                    continue

        # If currently on fund detail view, refresh title to new label
        if self.active_tab == "fund":
            cur = self.current_target_data()
            self.txt_header_title.value = cur.get("label", "")

        self.page.update()

    def on_target_change(self, e):
        tgt = self.current_target_data()
        if not tgt:
            return
        cache_key = self._cache_key(tgt)
        self.current_chart_code = None  # Reset chart

        self._clear_view_state()
        if cache_key in self._cache:
            self._apply_cached_state(cache_key)

        self._safe_run_task(self._set_loading, cache_key, True)
        self.page.update()
        self.manual_refresh()

    def open_dynamic_kline(self, e):
        tgt = self.current_target_data()
        if not tgt:
            self._show_message("暂无基金")
            return
        path = write_dynamic_chart_html(tgt)
        webbrowser.open(path.resolve().as_uri())

    def manual_refresh(self):
        # We can run fetch in thread to avoid blocking UI
        import threading
        tgt = self.current_target_data()
        if not tgt or not str(tgt.get("code") or "").strip():
            return
        cache_key = self._cache_key(tgt)

        if self._refreshing:
            self._pending_refresh_key = cache_key
            self._safe_run_task(self._set_loading, cache_key, True)
            return

        self._refreshing = True
        self._safe_run_task(self._set_loading, cache_key, True)
        threading.Thread(target=self._fetch_data, args=(tgt,), daemon=True).start()

    def _fetch_data(self, tgt: dict):
        cache_key = self._cache_key(tgt)
        try:
            res = None
            rate_res = None
            rate_err = None

            if tgt["type"] == "gold":
                res = fetch_gold()
                try:
                    rate_res = fetch_usdcny()
                except Exception as ex:
                    rate_err = ex
            elif tgt["type"] == "fund":
                res = fetch_fund(tgt["code"])

            # Post updates to UI
            fetch_time = datetime.now().strftime("%H:%M:%S")
            self._safe_run_task(self._update_ui, cache_key, tgt, res, rate_res, rate_err, fetch_time)

            # Update Chart if needed
            if tgt["code"] != self.current_chart_code:
                self.current_chart_code = tgt["code"]
                self._start_chart_render(cache_key, tgt)

        except Exception as e:
            LOGGER.exception("Fetch error: %s", self._cache_key(tgt))
            try:
                self._safe_run_task(self._show_fetch_error, cache_key, str(e))
            except Exception:
                pass
        finally:
            self._refreshing = False
            self._safe_run_task(self._set_loading, cache_key, False)

            if self._pending_refresh_key is not None:
                self._pending_refresh_key = None
                self.manual_refresh()

    async def _show_fetch_error(self, cache_key: str, msg: str):
        if cache_key != self._cache_key(self.current_target_data()):
            return
        safe = (msg or "获取失败").strip().replace("\n", " ")
        if len(safe) > 160:
            safe = safe[:160] + "..."
        self.txt_price.value = "获取失败"
        self.txt_change.value = safe
        self.txt_change.color = DOWN
        self.chart_img.visible = False
        self.chart_loading_hint.visible = False
        self.page.update()

    async def _set_loading(self, cache_key: str, loading: bool):
        tgt = self.current_target_data()
        if cache_key != self._cache_key(tgt):
            return

        self.prg_loading.visible = loading
        if loading:
            prev = self._cache.get(cache_key, {}).get("last_fetch_time")
            self.txt_header_time.value = f"拉取中... | 上次更新 {prev}" if prev else "拉取中..."
        self.page.update()

    async def _update_ui(self, cache_key: str, tgt, res, rate_res, rate_err, fetch_time):
        if not res:
            self._cache.setdefault(cache_key, {})["last_fetch_time"] = fetch_time
            if cache_key == self._cache_key(self.current_target_data()):
                self.txt_price.value = "获取失败"
                self.txt_header_time.value = f"更新于 {fetch_time}"
                self.page.update()
            return

        sign = "+" if res["change"] > 0 else ""
        change_color = UP if res["change"] > 0 else DOWN if res["change"] < 0 else TEXT

        price_text = f"{res['current']:.4f}"
        change_text = f"{sign}{res['change']:.4f}  ({sign}{res['pct']:.2f}%)"

        # Header time prefers source timestamp
        header_time = res.get("ts") or fetch_time

        def fmt_pct_plain(v):
            return "--" if v is None else f"{float(v):.2f}%"

        def fmt_pct_signed(v):
            if v is None:
                return "--"
            fv = float(v)
            return f"+{fv:.2f}%" if fv > 0 else f"{fv:.2f}%"

        def fmt_num(v):
            return "--" if v is None else f"{float(v):.4f}"

        chg3_raw = res.get("chg3")
        chg7_raw = res.get("chg7")
        chg15_raw = res.get("chg15")
        chg30_raw = res.get("chg30")

        pctile = fmt_pct_plain(res.get("percentile"))
        ma5 = fmt_num(res.get("ma5"))
        ma10 = fmt_num(res.get("ma10"))
        ma20 = fmt_num(res.get("ma20"))
        ma250 = fmt_num(res.get("ma250"))

        dist5_raw = res.get("dist_ma5")
        dist5 = fmt_pct_signed(dist5_raw)
        dist5_color = SUBTEXT
        if dist5_raw is not None:
            dist5_color = UP if float(dist5_raw) > 0 else DOWN if float(dist5_raw) < 0 else TEXT

        dist10_raw = res.get("dist_ma10")
        dist10 = fmt_pct_signed(dist10_raw)
        dist10_color = SUBTEXT
        if dist10_raw is not None:
            dist10_color = UP if float(dist10_raw) > 0 else DOWN if float(dist10_raw) < 0 else TEXT

        dist20_raw = res.get("dist_ma20")
        dist20 = fmt_pct_signed(dist20_raw)
        dist20_color = SUBTEXT
        if dist20_raw is not None:
            dist20_color = UP if float(dist20_raw) > 0 else DOWN if float(dist20_raw) < 0 else TEXT

        dist250_raw = res.get("dist_ma250")
        dist250 = fmt_pct_signed(dist250_raw)
        dist250_color = SUBTEXT
        if dist250_raw is not None:
            dist250_color = UP if float(dist250_raw) > 0 else DOWN if float(dist250_raw) < 0 else TEXT

        holding_item = {"holding_units": None, "holding_cost_amount": None, "daily_profit": None, "total_profit": None}
        if tgt.get("type") == "fund":
            fund_cfg = self._get_fund_config_item(tgt.get("code"))
            holding = fund_cfg.get("holding") if isinstance(fund_cfg, dict) else None
            if isinstance(holding, dict):
                holding_item["holding_units"] = holding.get("units")
                holding_item["holding_cost_amount"] = holding.get("cost_amount")
            holding_item.update(
                calculate_holding_metrics(
                    units=holding_item.get("holding_units"),
                    cost_amount=holding_item.get("holding_cost_amount"),
                    current_nav=res.get("current"),
                    previous_nav=res.get("prev_close"),
                )
            )

        detail_return_raw = {
            "chg3": chg3_raw,
            "chg7": chg7_raw,
            "chg15": chg15_raw,
            "chg30": chg30_raw,
        }
        detail_ma_raw = {
            "percentile": res.get("percentile"),
            "ma5": res.get("ma5"),
            "ma10": res.get("ma10"),
            "ma20": res.get("ma20"),
            "ma250": res.get("ma250"),
            "dist_ma5": dist5_raw,
            "dist_ma10": dist10_raw,
            "dist_ma20": dist20_raw,
            "dist_ma250": dist250_raw,
        }

        st = self._cache.setdefault(cache_key, {})
        st.update(
            {
                "txt_title": tgt.get("label", ""),
                "txt_header_time": f"更新于 {fetch_time}",
                "txt_price": price_text,
                "txt_change": change_text,
                "txt_change_color": change_color,
                "chg3_raw": chg3_raw,
                "chg7_raw": chg7_raw,
                "chg15_raw": chg15_raw,
                "chg30_raw": chg30_raw,
                "percentile": pctile,
                "ma5": ma5,
                "ma10": ma10,
                "ma20": ma20,
                "ma250": ma250,
                "dist_ma5": dist5,
                "dist_ma5_color": dist5_color,
                "dist_ma10": dist10,
                "dist_ma10_color": dist10_color,
                "dist_ma20": dist20,
                "dist_ma20_color": dist20_color,
                "dist_ma250": dist250,
                "dist_ma250_color": dist250_color,
                "detail_holding_raw": holding_item,
                "detail_return_raw": detail_return_raw,
                "detail_ma_raw": detail_ma_raw,
                "last_fetch_time": fetch_time,
            }
        )

        if cache_key != self._cache_key(self.current_target_data()):
            return

        self.txt_header_title.value = tgt.get("label", "")
        self.txt_header_time.value = header_time
        self.txt_price.value = price_text
        self.txt_change.value = change_text
        self.txt_change.color = change_color
        self._apply_metric_group(self.detail_holding_tiles, self._build_fund_detail_holding_metrics(holding_item))
        self._apply_metric_group(self.detail_return_tiles, self._build_fund_detail_return_metrics(detail_return_raw))
        self._apply_metric_group(self.detail_ma_tiles, self._build_fund_detail_ma_metrics(detail_ma_raw))
        self.page.update()

    def _start_chart_render(self, cache_key: str, tgt: dict):
        self._safe_run_task(self._set_chart_loading, cache_key, True)
        threading.Thread(target=self._render_chart_worker, args=(cache_key, tgt), daemon=True).start()

    def _render_chart_worker(self, cache_key: str, tgt: dict):
        try:
            if tgt["type"] == "gold":
                png_bytes = render_gold_kline_png_bytes({"range": "6mo", "interval": "1d"})
            else:
                png_bytes = render_fund_nav_png_bytes(tgt["code"])
        except Exception as exc:
            LOGGER.exception("Chart render failed: %s", self._cache_key(tgt))
            self._safe_run_task(self._apply_chart_result, cache_key, None, str(exc))
            return

        self._safe_run_task(self._apply_chart_result, cache_key, png_bytes, None)

    async def _set_chart_loading(self, cache_key: str, loading: bool):
        if cache_key != self._cache_key(self.current_target_data()):
            return
        self.chart_loading_hint.visible = loading
        if loading:
            self.chart_img.visible = False
        self.page.update()

    async def _apply_chart_result(self, cache_key: str, png_bytes: bytes | None, error_msg: str | None):
        self._cache.setdefault(cache_key, {})["chart_png"] = png_bytes or b""

        if cache_key != self._cache_key(self.current_target_data()):
            return

        if isinstance(png_bytes, (bytes, bytearray)) and len(png_bytes) > 0:
            self.chart_img.src = bytes(png_bytes)
            self.chart_img.visible = True
            self.chart_loading_hint.visible = False
            self.page.update()
            return

        self.chart_img.visible = False
        self.chart_loading_hint.visible = False
        if error_msg:
            safe = error_msg.replace("\n", " ").strip()
            if len(safe) > 120:
                safe = safe[:120] + "..."
            self.txt_header_time.value = f"图表加载失败 · {safe}"
        self.page.update()

    def start_timer(self):
        def loop():
            import time as tm
            while self.running:
                tm.sleep(REFRESH_MS / 1000)
                if self.active_tab == "fund_list":
                    self.refresh_fund_list()
                elif self.active_tab == "market":
                    self.refresh_market_indices()
                else:
                    self.manual_refresh()
        threading.Thread(target=loop, daemon=True).start()

        # Countdown loop
        def cd_loop():
            import time as tm
            while self.running:
                # Reuse next_*_open logic
                now = datetime.now()
                tgt = self.current_target_data()
                msg = "--"
                if tgt["type"] == "gold":
                    target, is_open = next_gold_open(now)
                    if is_open:
                        msg = "交易中"
                    elif target:
                        d = target - now
                        msg = f"距开盘 {d}"
                else:
                    msg = "基金收盘"

                # We can't update UI directly from thread easily without page.run_task or similar mechanism if async not set up for pure loop
                # Simpler: just ignore countdown for this snippet or implement simpler
                pass
                tm.sleep(1)
        # Ignoring countdown update for brevity/stability in this refactor


def main(page: ft.Page):
    page.window_resizable = True
    page.window.resizable = True
    # Default window size tuned to match the screenshot-like proportions
    page.window.width = 750
    page.window.height = 980
    page.theme_mode = ft.ThemeMode.LIGHT
    page.bgcolor = BG

    try:
        icon_path = (Path(__file__).parent / "assets" / "icon.png").resolve()
        if icon_path.exists():
            page.window.icon = str(icon_path)
    except Exception:
        pass
    app = FletApp(page)

if __name__ == "__main__":
    ft.run(main, view=ft.AppView.FLET_APP)

