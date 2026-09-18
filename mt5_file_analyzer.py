# mt5_file_analyzer.py
# ------------------------------------------------------------
# MT5 File Analyzer + Smart Solutions Engine
#
# يقرأ ملفات كشف MT5 بصيغ:
# CSV / TXT / HTML / HTM / XLS / XLSX
#
# ثم ينشئ:
# - Excel Diagnostic Report
# - Arabic Text Report
# - Behavior Flags
# - Smart Solutions Sheet
#
# الاستخدام من الداشبورد:
# from mt5_file_analyzer import analyze_mt5_file
# result = analyze_mt5_file(input_file, output_dir)
# ------------------------------------------------------------

from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, List, Tuple, Any

import numpy as np
import pandas as pd


# =========================
# General Helpers
# =========================

def clean_text(x) -> str:
    if pd.isna(x):
        return ""
    return str(x).strip()


def clean_col_name(col) -> str:
    col = str(col).strip()
    col = re.sub(r"\s+", " ", col)
    col = col.replace("\n", " ").replace("\r", " ")
    return col.strip()


def make_unique_columns(columns) -> List[str]:
    counts = {}
    new_cols = []

    for col in columns:
        base = clean_col_name(col)
        if base in counts:
            counts[base] += 1
            new_cols.append(f"{base}.{counts[base]}")
        else:
            counts[base] = 0
            new_cols.append(base)

    return new_cols


def parse_number(x):
    if pd.isna(x):
        return np.nan

    s = str(x).strip()

    if s == "":
        return np.nan

    s = s.replace(",", "")
    s = s.replace(" ", "")
    s = s.replace("$", "")
    s = s.replace("USD", "")
    s = s.replace("usd", "")
    s = s.replace("−", "-")

    # Handle parentheses as negative values: (123.45)
    if s.startswith("(") and s.endswith(")"):
        s = "-" + s[1:-1]

    try:
        return float(s)
    except Exception:
        return np.nan


def parse_datetime_series(s: pd.Series) -> pd.Series:
    """
    Parse MT5 datetime safely across different pandas versions.
    Important: do not use deprecated_datetime_parser_option because it is not supported
    in some pandas versions and causes TypeError.
    """

    s_clean = s.astype(str).str.strip()

    # Common MT5 / broker statement datetime formats
    formats = [
        "%Y-%m-%d %H:%M:%S",
        "%Y.%m.%d %H:%M:%S",
        "%d.%m.%Y %H:%M:%S",
        "%d/%m/%Y %H:%M:%S",
        "%m/%d/%Y %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y.%m.%d %H:%M",
        "%d.%m.%Y %H:%M",
        "%d/%m/%Y %H:%M",
        "%m/%d/%Y %H:%M",
    ]

    best_parsed = pd.to_datetime(s_clean, errors="coerce")
    best_missing = best_parsed.isna().mean()

    # Try dayfirst general parsing
    parsed_dayfirst = pd.to_datetime(s_clean, errors="coerce", dayfirst=True)
    dayfirst_missing = parsed_dayfirst.isna().mean()

    if dayfirst_missing < best_missing:
        best_parsed = parsed_dayfirst
        best_missing = dayfirst_missing

    # Try explicit known formats
    for fmt in formats:
        parsed_try = pd.to_datetime(s_clean, errors="coerce", format=fmt)
        missing = parsed_try.isna().mean()

        if missing < best_missing:
            best_parsed = parsed_try
            best_missing = missing

        if best_missing == 0:
            break

    return best_parsed


def safe_div(a, b):
    try:
        if b == 0 or pd.isna(b):
            return 0
        return a / b
    except Exception:
        return 0


def safe_float(x, default=0.0):
    """
    Convert any value to float safely.
    يستخدم داخل حساب الدرجات والتشخيص حتى لا يتوقف التحليل إذا كانت القيمة نصية أو فارغة.
    """
    try:
        if pd.isna(x):
            return default
        return float(x)
    except Exception:
        return default


def money_value(x):
    try:
        return f"${float(x):,.2f}"
    except Exception:
        return str(x)


# =========================
# File Reader
# =========================

def choose_best_table(tables: List[pd.DataFrame]) -> pd.DataFrame:
    if not tables:
        raise ValueError("No tables found in file.")

    best_score = -1
    best_df = tables[0]

    keywords = [
        "time", "symbol", "ticket", "type", "volume", "profit",
        "price", "s / l", "t / p", "commission", "swap"
    ]

    for df in tables:
        if df is None or df.empty:
            continue

        cols = " ".join([clean_col_name(c).lower() for c in df.columns])
        score = sum(1 for k in keywords if k in cols)

        # prefer bigger tables if keyword score is similar
        score += min(len(df) / 1000, 2)

        if score > best_score:
            best_score = score
            best_df = df

    return best_df


def read_mt5_file(input_file: str | Path) -> pd.DataFrame:
    input_file = Path(input_file)
    suffix = input_file.suffix.lower()

    if suffix in [".html", ".htm"]:
        tables = pd.read_html(str(input_file))
        return choose_best_table(tables)

    if suffix in [".xls", ".xlsx"]:
        try:
            return pd.read_excel(input_file)
        except Exception:
            tables = pd.read_html(str(input_file))
            return choose_best_table(tables)

    if suffix in [".csv", ".txt"]:
        encodings = ["utf-8-sig", "utf-8", "utf-16", "cp1256", "cp1252", "latin1"]

        last_error = None
        for enc in encodings:
            try:
                return pd.read_csv(
                    input_file,
                    encoding=enc,
                    sep=None,
                    engine="python",
                    on_bad_lines="skip"
                )
            except Exception as e:
                last_error = e

        raise ValueError(f"Could not read CSV/TXT file. Last error: {last_error}")

    raise ValueError(f"Unsupported file type: {suffix}")


# =========================
# Column Normalization
# =========================

COLUMN_ALIASES = {
    "time": [
        "Time", "Open Time", "Date", "Datetime", "Date Time",
        "Time Open", "OpenTime"
    ],
    "close_time": [
        "Close Time", "CloseTime", "Time Close", "Exit Time"
    ],
    "symbol": [
        "Symbol", "Item", "Instrument", "Market", "Pair"
    ],
    "ticket": [
        "Ticket", "Deal", "Order", "ID", "Order ID", "Deal ID"
    ],
    "position_id": [
        "Position", "Position ID", "PositionID", "Position Id"
    ],
    "type": [
        "Type", "Action", "Side", "Operation", "Direction"
    ],
    "volume": [
        "Volume", "Size", "Lots", "Lot", "Quantity"
    ],
    "price": [
        "Price", "Open Price", "Entry Price", "Open"
    ],
    "close_price": [
        "Close Price", "Price.1", "Close", "Exit Price"
    ],
    "sl": [
        "S / L", "SL", "Stop Loss", "StopLoss"
    ],
    "tp": [
        "T / P", "TP", "Take Profit", "TakeProfit"
    ],
    "profit": [
        "Profit", "P/L", "PnL", "P&L", "Net Profit", "Profit/Loss"
    ],
    "commission": [
        "Commission", "Comm"
    ],
    "swap": [
        "Swap", "Storage"
    ],
    "fee": [
        "Fee", "Fees", "Charges"
    ],
}


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    df.columns = make_unique_columns(df.columns)

    rename_map = {}
    lower_map = {clean_col_name(c).lower(): c for c in df.columns}

    for canonical, aliases in COLUMN_ALIASES.items():
        for alias in aliases:
            alias_clean = clean_col_name(alias).lower()
            if alias_clean in lower_map:
                rename_map[lower_map[alias_clean]] = canonical
                break

    df = df.rename(columns=rename_map)

    return df


def prepare_trades(raw_df: pd.DataFrame) -> pd.DataFrame:
    df = raw_df.copy()
    df = df.dropna(how="all")
    df = normalize_columns(df)

    # Remove fully repeated header rows
    if "time" in df.columns:
        df = df[df["time"].astype(str).str.lower() != "time"]

    required_any = ["symbol", "type", "profit"]
    existing = [c for c in required_any if c in df.columns]

    if not existing:
        raise ValueError(
            "Could not identify MT5 trade columns. Required at least Symbol/Type/Profit-like columns."
        )

    # Numeric columns
    numeric_cols = ["volume", "price", "close_price", "sl", "tp", "profit", "commission", "swap", "fee"]

    for col in numeric_cols:
        if col in df.columns:
            df[col] = df[col].apply(parse_number)
        else:
            df[col] = 0.0

    # Time
    if "time" in df.columns:
        df["time"] = parse_datetime_series(df["time"])
    else:
        df["time"] = pd.NaT

    if "close_time" in df.columns:
        df["close_time"] = parse_datetime_series(df["close_time"])
    else:
        df["close_time"] = pd.NaT

    # Symbol
    if "symbol" not in df.columns:
        df["symbol"] = ""

    df["symbol"] = df["symbol"].astype(str).str.strip().str.upper()

    # Type
    if "type" not in df.columns:
        df["type"] = ""

    df["type"] = df["type"].astype(str).str.strip().str.lower()

    # Exclude account transactions, not trades
    non_trade_keywords = [
        "balance", "deposit", "withdraw", "withdrawal", "credit",
        "charge", "correction", "bonus", "fee", "commission", "transfer"
    ]

    non_trade_pattern = "|".join(non_trade_keywords)
    df = df[~df["type"].str.contains(non_trade_pattern, case=False, na=False)]

    # Keep rows with profit and symbol
    df = df[df["profit"].notna()]
    df = df[df["symbol"].astype(str).str.strip() != ""]
    df = df[df["symbol"].astype(str).str.lower() != "nan"]

    # Normalize side
    def normalize_side(t):
        t = str(t).lower()
        if "buy" in t:
            return "BUY"
        if "sell" in t:
            return "SELL"
        return str(t).upper()

    df["side"] = df["type"].apply(normalize_side)

    # Net profit
    for col in ["commission", "swap", "fee"]:
        if col not in df.columns:
            df[col] = 0.0
        df[col] = df[col].fillna(0.0)

    df["net_profit"] = (
        df["profit"].fillna(0.0)
        + df["commission"].fillna(0.0)
        + df["swap"].fillna(0.0)
        + df["fee"].fillna(0.0)
    )

    df = df.sort_values("time", na_position="last").reset_index(drop=True)

    df["trade_number"] = np.arange(1, len(df) + 1)
    df["date"] = df["time"].dt.date
    df["hour"] = df["time"].dt.hour
    df["weekday"] = df["time"].dt.day_name()

    df["result"] = np.where(
        df["net_profit"] > 0,
        "Win",
        np.where(df["net_profit"] < 0, "Loss", "Breakeven")
    )

    df["equity_curve"] = df["net_profit"].cumsum()

    return df


def extract_initial_balance(raw_df: pd.DataFrame) -> float:
    """Return explicit starting deposits/balance operations when present.

    Credit and bonus rows are intentionally excluded because they are not cash
    equity. The value is used only to express drawdown as a percentage; it is
    not mixed into trading P/L.
    """
    df = normalize_columns(raw_df.dropna(how="all").copy())
    if "type" not in df.columns or "profit" not in df.columns:
        return 0.0

    operation = df["type"].astype(str).str.strip().str.lower()
    funding_mask = operation.str.contains(r"\bbalance\b|\bdeposit\b", regex=True, na=False)
    if not funding_mask.any():
        return 0.0

    values = df.loc[funding_mask, "profit"].apply(parse_number).dropna()
    positive_values = values[values > 0]
    return float(positive_values.sum()) if not positive_values.empty else 0.0


def build_position_summary(trade_deals_df: pd.DataFrame) -> pd.DataFrame:
    """Consolidate deal-level MT5 exports into closed-position rows when possible.

    Many broker exports already contain one row per closed trade. Those files
    are returned unchanged. A real Position/Position ID column is the signal
    that several deal rows may belong to one position.
    """
    if trade_deals_df.empty or "position_id" not in trade_deals_df.columns:
        return trade_deals_df.copy()

    df = trade_deals_df.copy()
    position_key = df["position_id"].astype(str).str.strip()
    usable = position_key.ne("") & position_key.ne("nan") & position_key.ne("0")
    if not usable.any() or not position_key[usable].duplicated().any():
        return df

    def first_nonempty(series, default=""):
        values = series.dropna()
        values = values[values.astype(str).str.strip().ne("")]
        return values.iloc[0] if not values.empty else default

    grouped_rows = []
    for position_id, group in df[usable].groupby("position_id", sort=False):
        group = group.sort_values("time", na_position="last")
        open_time = group["time"].min()
        explicit_close = group["close_time"].dropna() if "close_time" in group.columns else pd.Series(dtype="datetime64[ns]")
        close_time = explicit_close.max() if not explicit_close.empty else group["time"].max()

        grouped_rows.append({
            "position_id": position_id,
            "ticket": first_nonempty(group["ticket"]) if "ticket" in group.columns else "",
            "time": open_time,
            "close_time": close_time,
            "symbol": first_nonempty(group["symbol"]),
            "type": first_nonempty(group["type"]),
            "side": first_nonempty(group["side"]),
            "volume": float(group["volume"].abs().max()),
            "price": float(group["price"].replace(0, np.nan).dropna().iloc[0]) if group["price"].replace(0, np.nan).notna().any() else 0.0,
            "close_price": float(group["close_price"].replace(0, np.nan).dropna().iloc[-1]) if group["close_price"].replace(0, np.nan).notna().any() else 0.0,
            "sl": float(group["sl"].replace(0, np.nan).dropna().iloc[0]) if group["sl"].replace(0, np.nan).notna().any() else 0.0,
            "tp": float(group["tp"].replace(0, np.nan).dropna().iloc[0]) if group["tp"].replace(0, np.nan).notna().any() else 0.0,
            "profit": float(group["profit"].sum()),
            "commission": float(group["commission"].sum()),
            "swap": float(group["swap"].sum()),
            "fee": float(group["fee"].sum()),
            "net_profit": float(group["net_profit"].sum()),
            "deal_count": int(len(group)),
        })

    # Preserve rows that had no usable position identifier as standalone trades.
    if (~usable).any():
        standalone = df[~usable].copy()
        standalone["deal_count"] = 1
        grouped_rows.extend(standalone.to_dict("records"))

    positions = pd.DataFrame(grouped_rows).sort_values("time", na_position="last").reset_index(drop=True)
    positions["trade_number"] = np.arange(1, len(positions) + 1)
    positions["date"] = positions["time"].dt.date
    positions["hour"] = positions["time"].dt.hour
    positions["weekday"] = positions["time"].dt.day_name()
    positions["result"] = np.select(
        [positions["net_profit"] > 0, positions["net_profit"] < 0],
        ["Win", "Loss"],
        default="Breakeven",
    )
    positions["equity_curve"] = positions["net_profit"].cumsum()
    return positions


# =========================
# Metrics
# =========================

def calculate_max_drawdown(equity_series: pd.Series, initial_balance: float = 0.0) -> Tuple[float, float]:
    if equity_series.empty:
        return 0.0, 0.0

    base = max(float(initial_balance), 0.0)
    curve = pd.concat([
        pd.Series([base], dtype=float),
        base + pd.to_numeric(equity_series, errors="coerce").fillna(0.0),
    ], ignore_index=True)
    running_max = curve.cummax()
    drawdown = curve - running_max
    drawdown_pct = (drawdown / running_max.replace(0, np.nan) * 100).fillna(0.0)
    return float(drawdown.min()), float(drawdown_pct.min())


def calculate_max_loss_streak(df: pd.DataFrame) -> int:
    max_streak = 0
    current = 0

    for val in df["net_profit"].fillna(0):
        if val < 0:
            current += 1
            max_streak = max(max_streak, current)
        else:
            current = 0

    return int(max_streak)


def build_summary(df: pd.DataFrame, initial_balance: float = 0.0) -> pd.DataFrame:
    total_trades = len(df)
    wins = int((df["net_profit"] > 0).sum())
    losses = int((df["net_profit"] < 0).sum())
    breakeven = int((df["net_profit"] == 0).sum())

    gross_profit = float(df.loc[df["net_profit"] > 0, "net_profit"].sum())
    gross_loss = float(df.loc[df["net_profit"] < 0, "net_profit"].sum())
    net_profit = float(df["net_profit"].sum())

    win_rate = safe_div(wins, total_trades) * 100
    loss_rate = safe_div(losses, total_trades) * 100

    profit_factor = safe_div(gross_profit, abs(gross_loss))
    avg_win = safe_div(gross_profit, wins)
    avg_loss = safe_div(gross_loss, losses)
    expectancy = safe_div(net_profit, total_trades)

    best_trade = float(df["net_profit"].max()) if total_trades else 0
    worst_trade = float(df["net_profit"].min()) if total_trades else 0

    max_drawdown, max_drawdown_pct = calculate_max_drawdown(
        df["equity_curve"], initial_balance=initial_balance
    )
    max_loss_streak = calculate_max_loss_streak(df)

    metrics = {
        "total_trades": total_trades,
        "wins": wins,
        "losses": losses,
        "breakeven": breakeven,
        "win_rate": round(win_rate, 2),
        "loss_rate": round(loss_rate, 2),
        "gross_profit": round(gross_profit, 2),
        "gross_loss": round(gross_loss, 2),
        "net_profit": round(net_profit, 2),
        "profit_factor": round(profit_factor, 2),
        "avg_win": round(avg_win, 2),
        "avg_loss": round(avg_loss, 2),
        "expectancy": round(expectancy, 2),
        "best_trade": round(best_trade, 2),
        "worst_trade": round(worst_trade, 2),
        "max_drawdown": round(max_drawdown, 2),
        "max_drawdown_pct": round(max_drawdown_pct, 2),
        "max_loss_streak": max_loss_streak,
    }

    return pd.DataFrame(
        [{"Metric": k, "Value": v} for k, v in metrics.items()]
    )


def get_summary_value(summary_df: pd.DataFrame, key: str, default=0):
    try:
        row = summary_df[summary_df["Metric"] == key]
        if row.empty:
            return default
        return row["Value"].iloc[0]
    except Exception:
        return default


# =========================
# Aggregations
# =========================

def build_aggregations(df: pd.DataFrame) -> Dict[str, pd.DataFrame]:
    aggs = {}

    if not df.empty:
        aggs["by_symbol"] = (
            df.groupby("symbol", dropna=False)
            .agg(
                trades=("net_profit", "count"),
                net_profit=("net_profit", "sum"),
                win_rate=("net_profit", lambda x: round((x > 0).mean() * 100, 2)),
                avg_profit=("net_profit", "mean"),
                worst_trade=("net_profit", "min"),
                best_trade=("net_profit", "max"),
            )
            .reset_index()
            .sort_values("net_profit", ascending=False)
        )

        aggs["by_hour"] = (
            df.dropna(subset=["hour"])
            .groupby("hour", dropna=False)
            .agg(
                trades=("net_profit", "count"),
                net_profit=("net_profit", "sum"),
                win_rate=("net_profit", lambda x: round((x > 0).mean() * 100, 2)),
                avg_profit=("net_profit", "mean"),
            )
            .reset_index()
            .sort_values("hour")
        )

        aggs["by_weekday"] = (
            df.dropna(subset=["weekday"])
            .groupby("weekday", dropna=False)
            .agg(
                trades=("net_profit", "count"),
                net_profit=("net_profit", "sum"),
                win_rate=("net_profit", lambda x: round((x > 0).mean() * 100, 2)),
                avg_profit=("net_profit", "mean"),
            )
            .reset_index()
        )

        weekday_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        if not aggs["by_weekday"].empty:
            aggs["by_weekday"]["weekday"] = pd.Categorical(
                aggs["by_weekday"]["weekday"],
                categories=weekday_order,
                ordered=True
            )
            aggs["by_weekday"] = aggs["by_weekday"].sort_values("weekday")

        aggs["by_side"] = (
            df.groupby("side", dropna=False)
            .agg(
                trades=("net_profit", "count"),
                net_profit=("net_profit", "sum"),
                win_rate=("net_profit", lambda x: round((x > 0).mean() * 100, 2)),
                avg_profit=("net_profit", "mean"),
            )
            .reset_index()
            .sort_values("net_profit", ascending=False)
        )

    else:
        aggs["by_symbol"] = pd.DataFrame()
        aggs["by_hour"] = pd.DataFrame()
        aggs["by_weekday"] = pd.DataFrame()
        aggs["by_side"] = pd.DataFrame()

    return aggs


# =========================
# Behavior Flags
# =========================

def build_behavior_flags(df: pd.DataFrame, summary_df: pd.DataFrame) -> pd.DataFrame:
    flags = []

    if df.empty:
        return pd.DataFrame(columns=["type", "severity", "message", "suggestion", "evidence_value"])

    # Overtrading
    if "date" in df.columns:
        daily_counts = df.groupby("date")["net_profit"].count()
        if not daily_counts.empty:
            max_daily_trades = int(daily_counts.max())
            max_day = daily_counts.idxmax()

            if max_daily_trades >= 12:
                flags.append({
                    "type": "Overtrading",
                    "severity": "High",
                    "message": f"تم اكتشاف يوم تداول مكثف جداً: {max_daily_trades} صفقة في يوم واحد ({max_day}).",
                    "suggestion": "ضع حد يومي للصفقات. بعد الوصول للحد، توقف أو راجع جودة قراراتك.",
                    "evidence_value": max_daily_trades
                })
            elif max_daily_trades >= 8:
                flags.append({
                    "type": "Overtrading",
                    "severity": "Medium",
                    "message": f"تم اكتشاف كثافة تداول مرتفعة: {max_daily_trades} صفقات في يوم واحد ({max_day}).",
                    "suggestion": "قلل عدد الصفقات وركز على الصفقات الأعلى جودة فقط.",
                    "evidence_value": max_daily_trades
                })

    # Loss streak
    max_loss_streak = int(get_summary_value(summary_df, "max_loss_streak", 0))
    if max_loss_streak >= 5:
        flags.append({
            "type": "Loss Streak",
            "severity": "High",
            "message": f"أطول سلسلة خسائر وصلت إلى {max_loss_streak} صفقات متتالية.",
            "suggestion": "فعّل قاعدة توقف بعد خسارتين أو ثلاث خسائر متتالية.",
            "evidence_value": max_loss_streak
        })
    elif max_loss_streak >= 3:
        flags.append({
            "type": "Loss Streak",
            "severity": "Medium",
            "message": f"تم اكتشاف سلسلة خسائر وصلت إلى {max_loss_streak} صفقات متتالية.",
            "suggestion": "راجع آخر الخسائر قبل الدخول مجدداً، ولا تكمل التداول بنفس الحالة النفسية.",
            "evidence_value": max_loss_streak
        })

    # Fast re-entry after loss
    fast_count = 0
    fast_examples = []

    if "time" in df.columns and df["time"].notna().sum() >= 2:
        ordered = df.sort_values("time").reset_index(drop=True)

        for i in range(1, len(ordered)):
            prev = ordered.iloc[i - 1]
            cur = ordered.iloc[i]

            prev_event_time = prev.get("close_time", pd.NaT)
            if pd.isna(prev_event_time):
                prev_event_time = prev["time"]

            if pd.isna(prev_event_time) or pd.isna(cur["time"]):
                continue

            if float(prev["net_profit"]) < 0:
                diff_minutes = (cur["time"] - prev_event_time).total_seconds() / 60
                if 0 <= diff_minutes <= 30:
                    fast_count += 1
                    if len(fast_examples) < 3:
                        fast_examples.append(round(diff_minutes, 1))

        if fast_count >= 5:
            flags.append({
                "type": "Fast Re-entry After Loss",
                "severity": "High",
                "message": f"تم اكتشاف {fast_count} حالات دخول سريع بعد صفقة خاسرة خلال أقل من 30 دقيقة.",
                "suggestion": "طبّق قاعدة تهدئة بعد الخسارة لمدة 30 دقيقة قبل أي دخول جديد.",
                "evidence_value": fast_count
            })
        elif fast_count >= 2:
            flags.append({
                "type": "Fast Re-entry After Loss",
                "severity": "Medium",
                "message": f"تم اكتشاف {fast_count} حالات دخول سريع بعد الخسارة.",
                "suggestion": "لا تدخل صفقة جديدة بعد الخسارة حتى تراجع سبب الخسارة.",
                "evidence_value": fast_count
            })

    # Revenge lot increase after loss
    revenge_count = 0

    if "volume" in df.columns:
        ordered = df.sort_values("time").reset_index(drop=True)

        for i in range(1, len(ordered)):
            prev = ordered.iloc[i - 1]
            cur = ordered.iloc[i]

            prev_loss = float(prev["net_profit"]) < 0
            prev_vol = parse_number(prev.get("volume", 0))
            cur_vol = parse_number(cur.get("volume", 0))

            if prev_loss and prev_vol and cur_vol:
                if cur_vol >= prev_vol * 1.5:
                    revenge_count += 1

        if revenge_count >= 3:
            flags.append({
                "type": "Possible Revenge Trading",
                "severity": "High",
                "message": f"تم اكتشاف {revenge_count} حالات رفع حجم الصفقة بعد خسارة.",
                "suggestion": "امنع زيادة اللوت بعد أي صفقة خاسرة لمدة جلسة كاملة.",
                "evidence_value": revenge_count
            })
        elif revenge_count >= 1:
            flags.append({
                "type": "Possible Revenge Trading",
                "severity": "Medium",
                "message": f"تم اكتشاف {revenge_count} حالة محتملة لرفع اللوت بعد الخسارة.",
                "suggestion": "راجع قاعدة حجم الصفقة وثبّت اللوت بعد الخسارة.",
                "evidence_value": revenge_count
            })

    # Missing SL / TP
    if "sl" in df.columns:
        missing_sl_rate = float(((df["sl"].isna()) | (df["sl"] == 0)).mean() * 100)
        if missing_sl_rate >= 50:
            flags.append({
                "type": "Missing Stop Loss",
                "severity": "High",
                "message": f"نسبة كبيرة من الصفقات لا يظهر فيها وقف خسارة واضح: {missing_sl_rate:.1f}%.",
                "suggestion": "لا تدخل صفقة بدون تحديد الإبطال ووقف الخسارة مسبقاً.",
                "evidence_value": round(missing_sl_rate, 2)
            })
        elif missing_sl_rate >= 25:
            flags.append({
                "type": "Missing Stop Loss",
                "severity": "Medium",
                "message": f"بعض الصفقات لا يظهر فيها وقف خسارة واضح: {missing_sl_rate:.1f}%.",
                "suggestion": "اجعل وقف الخسارة جزءاً إلزامياً من قرار الدخول.",
                "evidence_value": round(missing_sl_rate, 2)
            })

    return pd.DataFrame(flags)


# =========================
# Scores
# =========================

def calculate_scores(summary_df: pd.DataFrame, flags_df: pd.DataFrame, total_rows: int) -> pd.DataFrame:
    win_rate = safe_float(get_summary_value(summary_df, "win_rate", 0), 0)
    profit_factor = safe_float(get_summary_value(summary_df, "profit_factor", 0), 0)
    expectancy = safe_float(get_summary_value(summary_df, "expectancy", 0), 0)
    max_loss_streak = safe_float(get_summary_value(summary_df, "max_loss_streak", 0), 0)
    total_trades = safe_float(get_summary_value(summary_df, "total_trades", 0), 0)

    high_flags = 0
    medium_flags = 0

    if not flags_df.empty and "severity" in flags_df.columns:
        sev = flags_df["severity"].astype(str).str.lower()
        high_flags = int(sev.isin(["high", "critical"]).sum())
        medium_flags = int((sev == "medium").sum())

    # Performance score
    performance = 50

    if profit_factor >= 2:
        performance += 25
    elif profit_factor >= 1.3:
        performance += 15
    elif profit_factor < 1:
        performance -= 20

    if expectancy > 0:
        performance += 15
    else:
        performance -= 15

    if win_rate >= 55:
        performance += 10
    elif win_rate < 40:
        performance -= 10

    performance = max(0, min(100, performance))

    # Discipline score
    discipline = 90
    discipline -= high_flags * 18
    discipline -= medium_flags * 9
    discipline -= max(0, max_loss_streak - 2) * 4
    discipline = max(0, min(100, discipline))

    # Risk behavior score
    risk_behavior = 90
    risk_behavior -= high_flags * 20
    risk_behavior -= medium_flags * 10
    risk_behavior = max(0, min(100, risk_behavior))

    # Data confidence
    data_confidence = 50
    if total_trades >= 100:
        data_confidence = 90
    elif total_trades >= 50:
        data_confidence = 80
    elif total_trades >= 20:
        data_confidence = 65
    elif total_trades >= 10:
        data_confidence = 50
    else:
        data_confidence = 35

    # Overall
    overall = round(
        performance * 0.35
        + discipline * 0.30
        + risk_behavior * 0.25
        + data_confidence * 0.10,
        1
    )

    scores = [
        {"score_name": "Overall Trading Health Score", "score": overall},
        {"score_name": "Discipline Score", "score": round(discipline, 1)},
        {"score_name": "Risk Behavior Score", "score": round(risk_behavior, 1)},
        {"score_name": "Performance Quality Score", "score": round(performance, 1)},
        {"score_name": "Data Confidence Score", "score": round(data_confidence, 1)},
    ]

    return pd.DataFrame(scores)


# =========================
# Diagnosis
# =========================

def build_client_diagnosis(summary_df: pd.DataFrame, flags_df: pd.DataFrame) -> pd.DataFrame:
    net_profit = safe_float(get_summary_value(summary_df, "net_profit", 0), 0)
    profit_factor = safe_float(get_summary_value(summary_df, "profit_factor", 0), 0)
    expectancy = safe_float(get_summary_value(summary_df, "expectancy", 0), 0)
    total_trades = int(safe_float(get_summary_value(summary_df, "total_trades", 0), 0))
    max_loss_streak = int(safe_float(get_summary_value(summary_df, "max_loss_streak", 0), 0))

    flag_types = []
    if not flags_df.empty and "type" in flags_df.columns:
        flag_types = flags_df["type"].astype(str).tolist()

    main_problem = "لا توجد مشكلة حرجة واضحة من البيانات الحالية."
    root_cause = "الأداء يحتاج متابعة على عينة أكبر أو ربط النتائج بسياق الاستراتيجية."
    recommendation = "استمر في قياس الأداء، وركّز على جودة الصفقات وليس عددها فقط."

    if "Possible Revenge Trading" in flag_types and "Fast Re-entry After Loss" in flag_types:
        main_problem = "السلوك الأقرب هو التداول الانتقامي بعد الخسارة."
        root_cause = "البيانات تشير إلى عودة سريعة للسوق بعد الخسارة وربما زيادة حجم الصفقة لتعويض الخسارة."
        recommendation = "طبّق نظام تهدئة بعد الخسارة، وثبّت حجم الصفقة، وامنع الدخول الجديد قبل مراجعة سبب الخسارة."

    elif "Fast Re-entry After Loss" in flag_types:
        main_problem = "المشكلة الأوضح هي الدخول السريع بعد الخسارة."
        root_cause = "المتداول يعود للسوق بسرعة قبل استعادة الهدوء أو مراجعة سبب الخسارة."
        recommendation = "طبّق قاعدة توقف 30 دقيقة بعد أي صفقة خاسرة."

    elif "Overtrading" in flag_types:
        main_problem = "المشكلة الأوضح هي كثرة التداول."
        root_cause = "عدد الصفقات المرتفع قد يعني البحث عن فرص كثيرة بدلاً من انتظار الفرص عالية الجودة."
        recommendation = "ضع حد يومي للصفقات وركز على أفضل إعدادات فقط."

    elif "Loss Streak" in flag_types:
        main_problem = "المشكلة الأوضح هي الاستمرار أثناء سلسلة الخسائر."
        root_cause = "المتداول قد يستمر في التداول رغم أن ظروف السوق أو حالته الذهنية غير مناسبة."
        recommendation = "فعّل قاعدة توقف بعد خسارتين أو ثلاث خسائر متتالية."

    elif "Missing Stop Loss" in flag_types:
        main_problem = "المشكلة الأوضح هي ضعف تحديد الإبطال ووقف الخسارة."
        root_cause = "بعض الصفقات لا يظهر فيها وقف خسارة واضح، وهذا يزيد خطر الخسائر الكبيرة."
        recommendation = "اجعل وقف الخسارة وقاعدة الإبطال شرطاً قبل أي دخول."

    elif net_profit < 0 and profit_factor < 1:
        main_problem = "الأداء العام ضعيف والربحية غير مستقرة."
        root_cause = "Profit Factor أقل من 1 ومتوسط العائد لا يدعم الاستمرارية."
        recommendation = "أعد تقييم الاستراتيجية وإدارة المخاطر قبل زيادة حجم التداول."

    executive_summary = (
        f"تم تحليل {total_trades} صفقة. صافي النتيجة {money_value(net_profit)}، "
        f"Profit Factor = {profit_factor}، Expectancy = {money_value(expectancy)}، "
        f"وأطول سلسلة خسائر = {max_loss_streak}."
    )

    if total_trades < 20:
        data_confidence = "حجم العينة منخفض، لذلك يجب اعتبار التشخيص أولياً وليس نهائياً."
    elif total_trades < 50:
        data_confidence = "حجم العينة متوسط، ويمكن استخدام التشخيص كبداية جيدة للتحسين."
    else:
        data_confidence = "حجم العينة جيد نسبياً، ويمكن الاعتماد على الأنماط المتكررة بدرجة أعلى."

    rows = [
        {"section": "Executive Summary", "content_ar": executive_summary},
        {"section": "Main Problem", "content_ar": main_problem},
        {"section": "Root Cause Hypothesis", "content_ar": root_cause},
        {"section": "Primary Recommendation", "content_ar": recommendation},
        {"section": "Data Confidence", "content_ar": data_confidence},
    ]

    return pd.DataFrame(rows)


# =========================
# Action Plan
# =========================

def build_action_plan(flags_df: pd.DataFrame) -> pd.DataFrame:
    flag_types = []
    if not flags_df.empty and "type" in flags_df.columns:
        flag_types = flags_df["type"].astype(str).tolist()

    plan = [
        {
            "day": "Day 1",
            "focus": "فهم المشكلة الرئيسية",
            "task": "راجع التقرير وحدد أكبر مشكلة متكررة في بياناتك.",
            "success_measure": "كتابة المشكلة الأولى بوضوح في جملة واحدة.",
        },
        {
            "day": "Day 2",
            "focus": "مراجعة أسوأ الصفقات",
            "task": "راجع أسوأ 5 صفقات واكتب سبب الدخول وسبب الخروج لكل صفقة.",
            "success_measure": "اكتشاف نمط واحد متكرر على الأقل.",
        },
        {
            "day": "Day 3",
            "focus": "قاعدة التوقف بعد الخسارة",
            "task": "طبّق توقف 30 دقيقة بعد أي صفقة خاسرة.",
            "success_measure": "عدم فتح أي صفقة مباشرة بعد الخسارة.",
        },
        {
            "day": "Day 4",
            "focus": "تثبيت حجم الصفقة",
            "task": "لا ترفع اللوت بعد الخسارة نهائياً خلال هذا اليوم.",
            "success_measure": "كل الصفقات بعد الخسارة تكون بنفس اللوت أو أقل.",
        },
        {
            "day": "Day 5",
            "focus": "تحديد أفضل وقت تداول",
            "task": "تداول فقط في الأوقات الأفضل حسب التقرير أو تجنب أسوأ ساعة.",
            "success_measure": "عدم التداول في أسوأ ساعة مذكورة في التقرير.",
        },
        {
            "day": "Day 6",
            "focus": "فلترة جودة الصفقة",
            "task": "قبل كل صفقة، اكتب سبب الدخول، وقف الخسارة، الهدف، ولماذا الصفقة تستحق.",
            "success_measure": "عدم دخول أي صفقة بدون خطة مكتوبة.",
        },
        {
            "day": "Day 7",
            "focus": "مراجعة أسبوعية",
            "task": "قارن نتائج الأسبوع الجديد مع التشخيص القديم.",
            "success_measure": "انخفاض عدد الأخطاء السلوكية أو تحسن جودة الصفقات.",
        },
    ]

    if "Overtrading" in flag_types:
        plan[2]["task"] = "ضع حداً يومياً للصفقات لا يتجاوز 5 صفقات، وتوقف بعد الوصول للحد."
        plan[2]["success_measure"] = "عدم تجاوز الحد اليومي للصفقات."

    if "Loss Streak" in flag_types:
        plan[3]["task"] = "توقف عن التداول بعد خسارتين متتاليتين خلال نفس اليوم."
        plan[3]["success_measure"] = "عدم الاستمرار بعد خسارتين متتاليتين."

    return pd.DataFrame(plan)


# =========================
# Smart Solutions Engine
# =========================

def add_solution(
    rows: List[Dict[str, Any]],
    problem: str,
    evidence: str,
    solution_name: str,
    solution_category: str,
    requires_mt5: str,
    requires_coding: str,
    priority: str,
    client_friendly_description: str,
    implementation_options: str,
    expected_impact: str,
    learning_task: str,
    next_step: str,
):
    rows.append({
        "problem": problem,
        "evidence": evidence,
        "solution_name": solution_name,
        "solution_category": solution_category,
        "requires_mt5": requires_mt5,
        "requires_coding": requires_coding,
        "priority": priority,
        "client_friendly_description": client_friendly_description,
        "implementation_options": implementation_options,
        "expected_impact": expected_impact,
        "learning_task": learning_task,
        "next_step": next_step,
    })


def build_smart_solutions(
    summary_df: pd.DataFrame,
    flags_df: pd.DataFrame,
    by_symbol_df: pd.DataFrame,
    by_hour_df: pd.DataFrame,
    by_weekday_df: pd.DataFrame,
    by_side_df: pd.DataFrame,
) -> pd.DataFrame:
    rows = []

    flag_types = []
    flag_map = {}

    if not flags_df.empty:
        for _, row in flags_df.iterrows():
            ftype = clean_text(row.get("type", ""))
            flag_types.append(ftype)
            flag_map[ftype] = row

    total_trades = get_summary_value(summary_df, "total_trades", 0)
    net_profit = get_summary_value(summary_df, "net_profit", 0)
    profit_factor = get_summary_value(summary_df, "profit_factor", 0)
    expectancy = get_summary_value(summary_df, "expectancy", 0)
    max_loss_streak = get_summary_value(summary_df, "max_loss_streak", 0)

    # 1) Fast Re-entry After Loss
    if "Fast Re-entry After Loss" in flag_types:
        row = flag_map.get("Fast Re-entry After Loss", {})
        evidence = clean_text(row.get("message", "تم اكتشاف دخول سريع بعد الخسارة."))

        add_solution(
            rows,
            problem="الدخول السريع بعد الخسارة",
            evidence=evidence,
            solution_name="نظام التهدئة بعد الخسارة",
            solution_category="No-Code + AI Coach + Automation",
            requires_mt5="No",
            requires_coding="No",
            priority="High",
            client_friendly_description=(
                "مشكلتك ليست فقط في اختيار الصفقة، بل في العودة السريعة للسوق بعد الخسارة. "
                "هذا السلوك غالباً يحول القرار من تحليل إلى محاولة تعويض."
            ),
            implementation_options="Trading Rule Card | Custom GPT | Telegram Coach Bot | MT5 Guard Optional",
            expected_impact="تقليل قرارات التعويض وتحسين جودة الصفقة التي تأتي بعد الخسارة.",
            learning_task="راجع آخر 3 صفقات خاسرة واكتب هل دخلت الصفقة التالية بهدوء أم رغبة في التعويض.",
            next_step="طبّق قاعدة توقف 30 دقيقة بعد أي خسارة لمدة 7 أيام."
        )

    # 2) Revenge Trading / Lot Increase
    if "Possible Revenge Trading" in flag_types:
        row = flag_map.get("Possible Revenge Trading", {})
        evidence = clean_text(row.get("message", "تم اكتشاف احتمال رفع اللوت بعد الخسارة."))

        add_solution(
            rows,
            problem="رفع حجم الصفقة بعد الخسارة",
            evidence=evidence,
            solution_name="حارس منع الانتقام باللوت",
            solution_category="No-Code + AI Coach + Automation",
            requires_mt5="No",
            requires_coding="No",
            priority="High",
            client_friendly_description=(
                "رفع اللوت بعد الخسارة يجعل الصفقة التالية عاطفية وخطرة. "
                "الحل هو وجود قاعدة أو مدرب ذكي يمنع زيادة حجم الصفقة بعد أي خسارة."
            ),
            implementation_options="Fixed Lot Rule | Custom GPT Lot Check | Telegram Bot | MT5 Lot Guard Optional",
            expected_impact="منع تضخم الخسائر وتقليل أثر التداول الانتقامي.",
            learning_task="قارن آخر 5 صفقات خاسرة مع الصفقة التي بعدها، هل زاد اللوت؟ ولماذا؟",
            next_step="ثبّت حجم الصفقة لمدة أسبوع كامل، ولا ترفع اللوت بعد الخسارة."
        )

    # 3) Overtrading
    if "Overtrading" in flag_types:
        row = flag_map.get("Overtrading", {})
        evidence = clean_text(row.get("message", "تم اكتشاف كثرة تداول."))

        add_solution(
            rows,
            problem="كثرة التداول",
            evidence=evidence,
            solution_name="حد يومي للصفقات",
            solution_category="No-Code + AI Coach + Dashboard Alert",
            requires_mt5="No",
            requires_coding="No",
            priority="High",
            client_friendly_description=(
                "كثرة التداول تجعل المتداول يبحث عن فرص كثيرة بدلاً من انتظار الفرص الأفضل. "
                "الحل هو تقليل عدد الصفقات ورفع جودة القرار."
            ),
            implementation_options="Daily Trade Limit | Custom GPT Checklist | Telegram Daily Counter | Dashboard Alert",
            expected_impact="تقليل الصفقات الضعيفة وتحسين الانضباط اليومي.",
            learning_task="راجع اليوم الذي يحتوي على أكبر عدد صفقات واكتب كم صفقة منها كانت فعلاً عالية الجودة.",
            next_step="ضع حداً يومياً لا يتجاوز 5 صفقات لمدة 7 أيام."
        )

    # 4) Loss Streak
    if "Loss Streak" in flag_types:
        row = flag_map.get("Loss Streak", {})
        evidence = clean_text(row.get("message", "تم اكتشاف سلسلة خسائر."))

        add_solution(
            rows,
            problem="الاستمرار أثناء سلسلة خسائر",
            evidence=evidence,
            solution_name="قاعدة الإيقاف بعد الخسائر المتتالية",
            solution_category="No-Code + AI Coach + Automation",
            requires_mt5="No",
            requires_coding="No",
            priority="High",
            client_friendly_description=(
                "الاستمرار بعد خسائر متتالية غالباً يعني أن السوق أو الحالة النفسية غير مناسبة. "
                "الحل هو قاعدة توقف واضحة قبل أن تتحول الخسارة الصغيرة إلى يوم سيئ."
            ),
            implementation_options="Stop Rule Card | Custom GPT Review | Telegram Alert | MT5 Guard Optional",
            expected_impact="حماية الحساب من أيام الانهيار وتقليل الخسائر المتراكمة.",
            learning_task="راجع أطول سلسلة خسائر واكتب ما الذي كان يجب أن يوقفك مبكراً.",
            next_step="توقف عن التداول بعد خسارتين متتاليتين خلال نفس اليوم."
        )

    # 5) Missing Stop Loss
    if "Missing Stop Loss" in flag_types:
        row = flag_map.get("Missing Stop Loss", {})
        evidence = clean_text(row.get("message", "بعض الصفقات لا يظهر فيها وقف خسارة واضح."))

        add_solution(
            rows,
            problem="الدخول بدون وقف خسارة واضح",
            evidence=evidence,
            solution_name="قاعدة الإبطال قبل الدخول",
            solution_category="Education + AI Coach + Rule Card",
            requires_mt5="No",
            requires_coding="No",
            priority="High",
            client_friendly_description=(
                "أي صفقة بدون نقطة إبطال واضحة تجعل الخسارة مفتوحة وغير محددة. "
                "الحل هو عدم الدخول قبل تحديد أين تكون فكرة الصفقة خاطئة."
            ),
            implementation_options="Pre-Trade Checklist | Custom GPT Risk Check | Trading Rule Card",
            expected_impact="تقليل الخسائر الكبيرة وتحسين وضوح القرار قبل الدخول.",
            learning_task="لكل صفقة جديدة، اكتب: أين يكون تحليلي خطأ؟ قبل كتابة الهدف.",
            next_step="لا تدخل أي صفقة لمدة أسبوع بدون وقف خسارة أو نقطة إبطال مكتوبة."
        )

    # 6) Bad Hour Filter
    if not by_hour_df.empty and "hour" in by_hour_df.columns and "net_profit" in by_hour_df.columns:
        worst_hour_row = by_hour_df.sort_values("net_profit", ascending=True).iloc[0]
        best_hour_row = by_hour_df.sort_values("net_profit", ascending=False).iloc[0]

        worst_hour = int(worst_hour_row["hour"])
        worst_hour_profit = float(worst_hour_row["net_profit"])
        best_hour = int(best_hour_row["hour"])
        best_hour_profit = float(best_hour_row["net_profit"])

        if worst_hour_profit < 0:
            add_solution(
                rows,
                problem="ضعف الأداء في وقت محدد",
                evidence=(
                    f"أسوأ ساعة تداول كانت {worst_hour}:00 بصافي {money_value(worst_hour_profit)}، "
                    f"بينما أفضل ساعة كانت {best_hour}:00 بصافي {money_value(best_hour_profit)}."
                ),
                solution_name="فلتر أسوأ ساعة تداول",
                solution_category="Strategy + No-Code + AI Coach",
                requires_mt5="No",
                requires_coding="No",
                priority="Medium",
                client_friendly_description=(
                    "بعض الخسائر لا تأتي من الاستراتيجية فقط، بل من توقيت التداول. "
                    "إذا كان هناك وقت يتكرر فيه الضعف، يجب تقليل التداول فيه أو منعه مؤقتاً."
                ),
                implementation_options="Time Filter Rule | Session Strategy | Telegram Reminder | MT5 Time Filter Optional",
                expected_impact="تقليل التداول في الأوقات التي تظهر فيها قرارات أضعف أو ظروف سوق أصعب.",
                learning_task=f"راجع آخر الصفقات التي تمت في الساعة {worst_hour}:00 واكتب هل كانت ظروف السوق مناسبة.",
                next_step=f"تجنب التداول في الساعة {worst_hour}:00 لمدة أسبوع، ثم قارن النتائج."
            )

    # 7) Weak Symbol Restriction
    if not by_symbol_df.empty and "symbol" in by_symbol_df.columns and "net_profit" in by_symbol_df.columns:
        worst_symbol_row = by_symbol_df.sort_values("net_profit", ascending=True).iloc[0]
        best_symbol_row = by_symbol_df.sort_values("net_profit", ascending=False).iloc[0]

        worst_symbol = worst_symbol_row["symbol"]
        worst_symbol_profit = float(worst_symbol_row["net_profit"])
        best_symbol = best_symbol_row["symbol"]
        best_symbol_profit = float(best_symbol_row["net_profit"])

        if worst_symbol_profit < 0:
            add_solution(
                rows,
                problem="ضعف الأداء على رمز محدد",
                evidence=(
                    f"أسوأ رمز كان {worst_symbol} بصافي {money_value(worst_symbol_profit)}، "
                    f"بينما أفضل رمز كان {best_symbol} بصافي {money_value(best_symbol_profit)}."
                ),
                solution_name="تقييد الرمز الضعيف مؤقتاً",
                solution_category="Strategy + Education + AI Coach",
                requires_mt5="No",
                requires_coding="No",
                priority="Medium",
                client_friendly_description=(
                    "ليس كل رمز يناسب نفس المتداول أو نفس الاستراتيجية. "
                    "إذا كان رمز معين يسحب أغلب الخسائر، يجب إيقافه مؤقتاً أو بناء قواعد خاصة له."
                ),
                implementation_options="Symbol Restriction Rule | Custom GPT Symbol Review | Strategy Adjustment",
                expected_impact="تقليل الخسائر الناتجة من الرموز التي لا تناسب أسلوب المتداول حالياً.",
                learning_task=f"راجع أسوأ 5 صفقات على {worst_symbol} واكتب هل كانت المشكلة في الرمز أم في توقيت الدخول.",
                next_step=f"أوقف التداول على {worst_symbol} لمدة أسبوع أو خفّض المخاطرة عليه."
            )

    # 8) Direction Bias
    if not by_side_df.empty and "net_profit" in by_side_df.columns:
        side_col = "side" if "side" in by_side_df.columns else by_side_df.columns[0]
        if side_col in by_side_df.columns:
            best_side_row = by_side_df.sort_values("net_profit", ascending=False).iloc[0]
            worst_side_row = by_side_df.sort_values("net_profit", ascending=True).iloc[0]

            best_side = best_side_row[side_col]
            worst_side = worst_side_row[side_col]
            best_side_profit = float(best_side_row["net_profit"])
            worst_side_profit = float(worst_side_row["net_profit"])

            if worst_side_profit < 0 and abs(worst_side_profit) > 0:
                add_solution(
                    rows,
                    problem="ضعف في اتجاه تداول محدد",
                    evidence=(
                        f"أفضل اتجاه كان {best_side} بصافي {money_value(best_side_profit)}، "
                        f"بينما أضعف اتجاه كان {worst_side} بصافي {money_value(worst_side_profit)}."
                    ),
                    solution_name="فلتر اتجاه قبل الدخول",
                    solution_category="Education + Strategy + AI Coach",
                    requires_mt5="No",
                    requires_coding="No",
                    priority="Medium",
                    client_friendly_description=(
                        "إذا كان المتداول يربح في اتجاه ويخسر في اتجاه آخر، فقد تكون المشكلة في قراءة السيطرة والاتجاه. "
                        "الحل هو إضافة فلتر اتجاه قبل أي صفقة."
                    ),
                    implementation_options="Trend Bias Checklist | Custom GPT Direction Review | Strategy Filter",
                    expected_impact="تقليل الصفقات عكس الاتجاه أو الصفقات التي لا يوجد فيها وضوح كافٍ.",
                    learning_task="قبل كل صفقة اكتب: من المسيطر؟ المشترون أم البائعون؟ وما الدليل؟",
                    next_step=f"خفّف تداول {worst_side} حتى تضيف فلتر اتجاه واضح."
                )

    # 9) Weak Performance / Strategy Redesign
    try:
        pf = float(profit_factor)
    except Exception:
        pf = 0

    try:
        exp = float(expectancy)
    except Exception:
        exp = 0

    try:
        npf = float(net_profit)
    except Exception:
        npf = 0

    if pf < 1 or exp < 0 or npf < 0:
        add_solution(
            rows,
            problem="ضعف الربحية العامة",
            evidence=(
                f"صافي النتيجة {money_value(net_profit)}، Profit Factor = {profit_factor}، "
                f"Expectancy = {money_value(expectancy)}."
            ),
            solution_name="إعادة تصميم الاستراتيجية وإدارة المخاطر",
            solution_category="Strategy + Education + AI Coach",
            requires_mt5="No",
            requires_coding="No",
            priority="High",
            client_friendly_description=(
                "عندما تكون الربحية العامة ضعيفة، فالحل ليس زيادة عدد الصفقات. "
                "الحل هو تقليل الصفقات الضعيفة، تحسين نسبة العائد إلى المخاطرة، وبناء قواعد دخول وخروج أوضح."
            ),
            implementation_options="Strategy Redesign | Risk Plan | Custom GPT Strategy Coach | Lessons",
            expected_impact="تحسين جودة الصفقات وتقليل القرارات التي لا تستحق المخاطرة.",
            learning_task="راجع 10 صفقات عشوائية واكتب لكل صفقة: هل كانت تستحق المخاطرة؟ ولماذا؟",
            next_step="ابنِ استراتيجية منخفضة التكرار تعتمد على فلتر اتجاه + منطقة دخول + وقف واضح + هدف منطقي."
        )

    # 10) Custom GPT baseline solution always recommended
    add_solution(
        rows,
        problem="الحاجة إلى متابعة شخصية بعد التقرير",
        evidence=f"تم تحليل {total_trades} صفقة، والتقرير كشف أنماط تحتاج متابعة يومية وليس قراءة واحدة فقط.",
        solution_name="Custom GPT مدرب تداول شخصي",
        solution_category="AI Coach",
        requires_mt5="No",
        requires_coding="No",
        priority="Medium",
        client_friendly_description=(
            "بدلاً من أن يقرأ العميل التقرير مرة واحدة ثم ينساه، يتم بناء مدرب GPT خاص به يعرف مشاكله، "
            "مستواه، قواعده، أسوأ أوقاته، وأهم ما يجب أن يراجعه قبل كل صفقة."
        ),
        implementation_options="Custom GPT | Telegram Coach Bot | Pre-Trade Checklist",
        expected_impact="تحويل التقرير إلى متابعة يومية تساعد المتداول قبل اتخاذ القرار.",
        learning_task="اكتب 5 أسئلة يجب أن يجيب عنها المتداول قبل كل صفقة بناءً على مشاكله.",
        next_step="بناء ملف تعليمات Custom GPT يحتوي على التشخيص والقواعد الشخصية وخطة التدريب."
    )

    # If no rows for some reason
    if not rows:
        add_solution(
            rows,
            problem="لا توجد مشكلة حرجة واضحة",
            evidence="لم يتم اكتشاف Flags خطيرة بناءً على القواعد الحالية.",
            solution_name="نظام متابعة وتحسين مستمر",
            solution_category="Dashboard + AI Coach",
            requires_mt5="No",
            requires_coding="No",
            priority="Low",
            client_friendly_description=(
                "حتى لو لم تظهر مشكلة حرجة، الأفضل متابعة الأداء أسبوعياً لاكتشاف أي نمط جديد مبكراً."
            ),
            implementation_options="Weekly Review | Custom GPT | Dashboard Monitoring",
            expected_impact="الحفاظ على الانضباط واكتشاف المشاكل قبل أن تكبر.",
            learning_task="راجع نتائجك نهاية كل أسبوع واكتب أفضل قرار وأسوأ قرار.",
            next_step="أعد رفع كشف جديد بعد أسبوعين للمقارنة."
        )

    smart_df = pd.DataFrame(rows)

    priority_order = {"High": 1, "Medium": 2, "Low": 3}
    smart_df["priority_order"] = smart_df["priority"].map(priority_order).fillna(9)
    smart_df = smart_df.sort_values(["priority_order", "problem"]).drop(columns=["priority_order"])

    return smart_df.reset_index(drop=True)


# =========================
# Reports
# =========================

def build_arabic_text_report(
    summary_df: pd.DataFrame,
    diagnosis_df: pd.DataFrame,
    flags_df: pd.DataFrame,
    smart_solutions_df: pd.DataFrame,
) -> str:
    lines = []

    lines.append("تقرير تشخيص حساب التداول")
    lines.append("=" * 50)
    lines.append("")

    lines.append("الملخص الرقمي:")
    for _, row in summary_df.iterrows():
        lines.append(f"- {row['Metric']}: {row['Value']}")

    lines.append("")
    lines.append("التشخيص:")
    for _, row in diagnosis_df.iterrows():
        lines.append(f"- {row['section']}: {row['content_ar']}")

    lines.append("")
    lines.append("الأعلام السلوكية:")
    if flags_df.empty:
        lines.append("- لا توجد أعلام سلوكية واضحة.")
    else:
        for _, row in flags_df.iterrows():
            lines.append(f"- {row.get('type', '')} [{row.get('severity', '')}]: {row.get('message', '')}")
            lines.append(f"  التعديل المقترح: {row.get('suggestion', '')}")

    lines.append("")
    lines.append("الحلول الذكية المقترحة:")
    if smart_solutions_df.empty:
        lines.append("- لا توجد حلول ذكية مقترحة.")
    else:
        for _, row in smart_solutions_df.iterrows():
            lines.append(f"- المشكلة: {row.get('problem', '')}")
            lines.append(f"  الحل: {row.get('solution_name', '')}")
            lines.append(f"  الأولوية: {row.get('priority', '')}")
            lines.append(f"  النوع: {row.get('solution_category', '')}")
            lines.append(f"  الوصف: {row.get('client_friendly_description', '')}")
            lines.append(f"  الخطوة التالية: {row.get('next_step', '')}")
            lines.append("")

    lines.append("")
    lines.append("تحذير:")
    lines.append("هذا التقرير مخصص لتحليل بيانات التداول وليس توصية تداول. التداول يحمل مخاطرة حقيقية والقرار النهائي مسؤولية المتداول.")

    return "\n".join(lines)


def write_excel_report(
    output_path: Path,
    account_info_df: pd.DataFrame,
    summary_df: pd.DataFrame,
    scores_df: pd.DataFrame,
    diagnosis_df: pd.DataFrame,
    action_plan_df: pd.DataFrame,
    flags_df: pd.DataFrame,
    smart_solutions_df: pd.DataFrame,
    position_df: pd.DataFrame,
    trade_deals_df: pd.DataFrame,
    aggs: Dict[str, pd.DataFrame],
):
    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        account_info_df.to_excel(writer, sheet_name="Account Info", index=False)
        summary_df.to_excel(writer, sheet_name="Summary", index=False)
        scores_df.to_excel(writer, sheet_name="Scores", index=False)
        diagnosis_df.to_excel(writer, sheet_name="Client Diagnosis", index=False)
        action_plan_df.to_excel(writer, sheet_name="Action Plan", index=False)
        flags_df.to_excel(writer, sheet_name="Behavior Flags", index=False)
        smart_solutions_df.to_excel(writer, sheet_name="Smart Solutions", index=False)

        position_df.to_excel(writer, sheet_name="Position Summary", index=False)
        trade_deals_df.to_excel(writer, sheet_name="Trade Deals", index=False)

        for name, df in aggs.items():
            safe_name = name[:31]
            df.to_excel(writer, sheet_name=safe_name, index=False)


# =========================
# Main Function
# =========================

def analyze_mt5_file(input_file: str | Path, output_dir: str | Path = "mt5_file_output") -> Dict[str, Any]:
    input_file = Path(input_file)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    raw_df = read_mt5_file(input_file)
    raw_rows = len(raw_df)
    initial_balance = extract_initial_balance(raw_df)

    trade_deals_df = prepare_trades(raw_df)
    position_df = build_position_summary(trade_deals_df)
    clean_rows = len(position_df)

    if position_df.empty:
        raise ValueError("No trade rows found after cleaning the file.")

    summary_df = build_summary(position_df, initial_balance=initial_balance)
    aggs = build_aggregations(position_df)
    flags_df = build_behavior_flags(position_df, summary_df)
    scores_df = calculate_scores(summary_df, flags_df, raw_rows)
    diagnosis_df = build_client_diagnosis(summary_df, flags_df)
    action_plan_df = build_action_plan(flags_df)

    smart_solutions_df = build_smart_solutions(
        summary_df=summary_df,
        flags_df=flags_df,
        by_symbol_df=aggs.get("by_symbol", pd.DataFrame()),
        by_hour_df=aggs.get("by_hour", pd.DataFrame()),
        by_weekday_df=aggs.get("by_weekday", pd.DataFrame()),
        by_side_df=aggs.get("by_side", pd.DataFrame()),
    )

    account_info_df = pd.DataFrame([
        {"field": "source_file", "value": input_file.name},
        {"field": "total_rows_raw", "value": raw_rows},
        {"field": "total_rows_clean", "value": clean_rows},
        {"field": "deal_rows_clean", "value": len(trade_deals_df)},
        {"field": "initial_balance_detected", "value": round(initial_balance, 2)},
        {"field": "generated_by", "value": "MT5 File Analyzer + Smart Solutions Engine"},
    ])

    excel_path = output_dir / "mt5_file_diagnostic_report_v2.xlsx"
    txt_path = output_dir / "diagnostic_report_ar_v2.txt"

    write_excel_report(
        output_path=excel_path,
        account_info_df=account_info_df,
        summary_df=summary_df,
        scores_df=scores_df,
        diagnosis_df=diagnosis_df,
        action_plan_df=action_plan_df,
        flags_df=flags_df,
        smart_solutions_df=smart_solutions_df,
        position_df=position_df,
        trade_deals_df=trade_deals_df,
        aggs=aggs,
    )

    text_report = build_arabic_text_report(
        summary_df=summary_df,
        diagnosis_df=diagnosis_df,
        flags_df=flags_df,
        smart_solutions_df=smart_solutions_df,
    )

    txt_path.write_text(text_report, encoding="utf-8")

    return {
        "input_file": str(input_file),
        "output_dir": str(output_dir),
        "excel_report": str(excel_path),
        "text_report": str(txt_path),
        "raw_rows": raw_rows,
        "clean_rows": clean_rows,
        "smart_solutions_count": len(smart_solutions_df),
    }


# =========================
# CLI Test
# =========================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Analyze MT5 statement file and generate diagnostic report.")
    parser.add_argument("input_file", help="Path to CSV / HTML / XLS / XLSX file")
    parser.add_argument("--output-dir", default="mt5_file_output", help="Output directory")

    args = parser.parse_args()

    result = analyze_mt5_file(args.input_file, args.output_dir)

    print("Analysis completed.")
    for k, v in result.items():
        print(f"{k}: {v}")
