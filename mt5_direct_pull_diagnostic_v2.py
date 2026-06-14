# mt5_direct_pull_diagnostic_v2.py
# ------------------------------------------------------------
# MT5 Direct Pull Diagnostic System - V2
# يسحب سجل الصفقات مباشرة من منصة MetaTrader 5 عبر Python
# بدون Save Report / بدون طباعة التقرير من المنصة
#
# الجديد في V2:
# 1) Discipline Score
# 2) Risk Behavior Score
# 3) Performance Quality Score
# 4) Client Diagnosis
# 5) Main Problem
# 6) Root Cause Hypothesis
# 7) 7-Day Correction Plan
#
# المتطلبات:
# 1) Windows
# 2) منصة MT5 مفتوحة ومثبتة على الجهاز
# 3) الحساب مسجل دخول داخل MT5 أو تمرر بيانات الدخول للسكريبت
#
# التثبيت:
# python -m pip install -r requirements_mt5_direct.txt
#
# تشغيل بسيط، إذا MT5 مفتوح والحساب داخل المنصة:
# python mt5_direct_pull_diagnostic_v2.py --days 90
#
# تشغيل بتحديد فترة:
# python mt5_direct_pull_diagnostic_v2.py --from 2026-01-01 --to 2026-06-14
#
# تشغيل مع مسار المنصة إذا لم يجدها تلقائياً:
# python mt5_direct_pull_diagnostic_v2.py --terminal "C:\Program Files\MetaTrader 5\terminal64.exe" --days 90
#
# تشغيل مع تسجيل دخول:
# python mt5_direct_pull_diagnostic_v2.py --login 12345678 --password "YOUR_PASSWORD" --server "Broker-Server" --days 90
#
# المخرجات داخل مجلد:
# mt5_direct_output_v2
# ------------------------------------------------------------

import argparse
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

try:
    import MetaTrader5 as mt5
except ImportError:
    raise SystemExit(
        "لم يتم تثبيت مكتبة MetaTrader5.\n"
        "شغل الأمر التالي:\n"
        "python -m pip install MetaTrader5"
    )


OUTPUT_DIR = "mt5_direct_output_v2"

RISK_RULES = {
    "max_trades_per_day_warning": 8,
    "hard_trades_per_day_limit": 12,
    "revenge_trade_minutes": 30,
    "large_lot_increase_ratio": 1.5,
    "bad_loss_streak": 3,
    "critical_loss_streak": 5,
    "minimum_trades_for_good_confidence": 50,
    "minimum_trades_for_strong_confidence": 100,
}


# =========================
# الاتصال مع MT5
# =========================

def connect_mt5(
    terminal_path: Optional[str] = None,
    login: Optional[int] = None,
    password: Optional[str] = None,
    server: Optional[str] = None,
    timeout: int = 60000,
) -> Dict[str, object]:
    """
    يتصل بمنصة MT5.
    إذا لم ترسل بيانات login، سيستخدم الحساب المفتوح حالياً داخل المنصة.
    """

    if terminal_path:
        ok = mt5.initialize(path=terminal_path, timeout=timeout)
    else:
        ok = mt5.initialize(timeout=timeout)

    if not ok:
        raise RuntimeError(f"فشل الاتصال بمنصة MT5. last_error={mt5.last_error()}")

    if login is not None:
        if not password or not server:
            raise ValueError("إذا استخدمت --login يجب تمرير --password و --server أيضاً.")

        authorized = mt5.login(
            login=int(login),
            password=password,
            server=server,
            timeout=timeout
        )

        if not authorized:
            raise RuntimeError(f"فشل تسجيل الدخول. last_error={mt5.last_error()}")

    account = mt5.account_info()
    if account is None:
        raise RuntimeError(f"تم الاتصال بالمنصة لكن لم نستطع قراءة الحساب. last_error={mt5.last_error()}")

    account_data = {
        "login": account.login,
        "server": account.server,
        "name": account.name,
        "balance": account.balance,
        "equity": account.equity,
        "currency": account.currency,
        "company": getattr(account, "company", ""),
        "leverage": getattr(account, "leverage", ""),
    }

    print("تم الاتصال بنجاح ✅")
    print(f"Account: {account_data['login']}")
    print(f"Server: {account_data['server']}")
    print(f"Name: {account_data['name']}")
    print(f"Balance: {account_data['balance']}")
    print(f"Equity: {account_data['equity']}")
    print(f"Currency: {account_data['currency']}")

    return account_data


# =========================
# سحب البيانات
# =========================

def get_date_range(args) -> tuple[datetime, datetime]:
    if args.from_date:
        date_from = datetime.strptime(args.from_date, "%Y-%m-%d")
    else:
        date_from = datetime.now() - timedelta(days=args.days)

    if args.to_date:
        date_to = datetime.strptime(args.to_date, "%Y-%m-%d") + timedelta(days=1) - timedelta(seconds=1)
    else:
        date_to = datetime.now()

    if date_from >= date_to:
        raise ValueError("تاريخ البداية يجب أن يكون قبل تاريخ النهاية.")

    return date_from, date_to


def pull_deals(date_from: datetime, date_to: datetime, group: Optional[str] = None) -> pd.DataFrame:
    """
    يسحب Deals من MT5.
    Deals هي العمليات المنفذة فعلياً، وهي الأفضل للتحليل.
    """

    if group:
        deals = mt5.history_deals_get(date_from, date_to, group=group)
    else:
        deals = mt5.history_deals_get(date_from, date_to)

    if deals is None:
        raise RuntimeError(f"history_deals_get رجعت None. last_error={mt5.last_error()}")

    if len(deals) == 0:
        return pd.DataFrame()

    df = pd.DataFrame(list(deals), columns=deals[0]._asdict().keys())

    if "time" in df.columns:
        df["time"] = pd.to_datetime(df["time"], unit="s", errors="coerce")

    return df


def pull_orders(date_from: datetime, date_to: datetime, group: Optional[str] = None) -> pd.DataFrame:
    """
    اختياري: يسحب Orders أيضاً للرجوع لها عند الحاجة.
    التحليل الأساسي سيكون على Deals.
    """

    if group:
        orders = mt5.history_orders_get(date_from, date_to, group=group)
    else:
        orders = mt5.history_orders_get(date_from, date_to)

    if orders is None:
        print(f"تحذير: history_orders_get رجعت None. last_error={mt5.last_error()}")
        return pd.DataFrame()

    if len(orders) == 0:
        return pd.DataFrame()

    df = pd.DataFrame(list(orders), columns=orders[0]._asdict().keys())

    if "time_setup" in df.columns:
        df["time_setup"] = pd.to_datetime(df["time_setup"], unit="s", errors="coerce")

    if "time_done" in df.columns:
        df["time_done"] = pd.to_datetime(df["time_done"], unit="s", errors="coerce")

    return df


# =========================
# تنظيف وتحويل البيانات
# =========================

def map_deal_type(x) -> str:
    mapping = {
        getattr(mt5, "DEAL_TYPE_BUY", 0): "BUY",
        getattr(mt5, "DEAL_TYPE_SELL", 1): "SELL",
        getattr(mt5, "DEAL_TYPE_BALANCE", 2): "BALANCE",
        getattr(mt5, "DEAL_TYPE_CREDIT", 3): "CREDIT",
        getattr(mt5, "DEAL_TYPE_CHARGE", 4): "CHARGE",
        getattr(mt5, "DEAL_TYPE_CORRECTION", 5): "CORRECTION",
        getattr(mt5, "DEAL_TYPE_BONUS", 6): "BONUS",
        getattr(mt5, "DEAL_TYPE_COMMISSION", 7): "COMMISSION",
        getattr(mt5, "DEAL_TYPE_COMMISSION_DAILY", 8): "COMMISSION_DAILY",
        getattr(mt5, "DEAL_TYPE_COMMISSION_MONTHLY", 9): "COMMISSION_MONTHLY",
        getattr(mt5, "DEAL_TYPE_INTEREST", 10): "INTEREST",
        getattr(mt5, "DEAL_TYPE_BUY_CANCELED", 11): "BUY_CANCELED",
        getattr(mt5, "DEAL_TYPE_SELL_CANCELED", 12): "SELL_CANCELED",
    }
    return mapping.get(x, str(x))


def map_deal_entry(x) -> str:
    mapping = {
        getattr(mt5, "DEAL_ENTRY_IN", 0): "IN",
        getattr(mt5, "DEAL_ENTRY_OUT", 1): "OUT",
        getattr(mt5, "DEAL_ENTRY_INOUT", 2): "INOUT",
        getattr(mt5, "DEAL_ENTRY_OUT_BY", 3): "OUT_BY",
    }
    return mapping.get(x, str(x))


def prepare_trade_deals(deals_df: pd.DataFrame) -> pd.DataFrame:
    """
    يحول Deals الخام إلى جدول تداول نظيف.
    نحتفظ بصفقات BUY/SELL فقط، ونستبعد Balance/Deposit/Credit.
    """

    if deals_df.empty:
        return deals_df.copy()

    df = deals_df.copy()

    if "type" in df.columns:
        df["deal_type_name"] = df["type"].apply(map_deal_type)
    else:
        df["deal_type_name"] = ""

    if "entry" in df.columns:
        df["entry_name"] = df["entry"].apply(map_deal_entry)
    else:
        df["entry_name"] = ""

    trade_types = ["BUY", "SELL", "BUY_CANCELED", "SELL_CANCELED"]
    df = df[df["deal_type_name"].isin(trade_types)].copy()

    numeric_cols = ["volume", "price", "profit", "commission", "swap", "fee"]
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    df["net_profit"] = 0.0
    if "profit" in df.columns:
        df["net_profit"] += df["profit"]
    if "commission" in df.columns:
        df["net_profit"] += df["commission"]
    if "swap" in df.columns:
        df["net_profit"] += df["swap"]
    if "fee" in df.columns:
        df["net_profit"] += df["fee"]

    if "symbol" in df.columns:
        df["symbol"] = df["symbol"].astype(str).str.upper().str.strip()

    if "time" in df.columns:
        df = df.sort_values("time")
        df["date"] = df["time"].dt.date
        df["hour"] = df["time"].dt.hour
        df["weekday"] = df["time"].dt.day_name()

    df["result"] = np.where(df["net_profit"] > 0, "Win", np.where(df["net_profit"] < 0, "Loss", "Breakeven"))
    df["trade_number"] = np.arange(1, len(df) + 1)
    df["equity_curve"] = df["net_profit"].cumsum()

    return df


def build_position_summary(trade_deals: pd.DataFrame) -> pd.DataFrame:
    """
    يلخص الصفقات حسب position_id إن كان موجوداً.
    هذا مفيد لأن MT5 قد يسجل أكثر من deal للصفقة الواحدة.
    """

    if trade_deals.empty or "position_id" not in trade_deals.columns:
        return pd.DataFrame()

    df = trade_deals.copy()

    agg_dict = {
        "time": ["min", "max"],
        "symbol": "first",
        "deal_type_name": "first",
        "volume": "sum",
        "net_profit": "sum",
    }

    optional_cols = ["profit", "commission", "swap", "fee", "price"]
    for col in optional_cols:
        if col in df.columns and col not in agg_dict:
            agg_dict[col] = "sum"

    grouped = df.groupby("position_id").agg(agg_dict)

    grouped.columns = [
        "_".join([str(x) for x in col if str(x) != ""]).strip("_")
        for col in grouped.columns.values
    ]

    grouped = grouped.reset_index()

    rename = {
        "time_min": "open_time",
        "time_max": "close_time",
        "symbol_first": "symbol",
        "deal_type_name_first": "first_side",
        "volume_sum": "total_volume",
        "net_profit_sum": "net_profit",
    }
    grouped = grouped.rename(columns=rename)

    grouped["result"] = np.where(grouped["net_profit"] > 0, "Win", np.where(grouped["net_profit"] < 0, "Loss", "Breakeven"))
    grouped["trade_number"] = np.arange(1, len(grouped) + 1)
    grouped["equity_curve"] = grouped["net_profit"].cumsum()

    if "open_time" in grouped.columns:
        grouped["date"] = grouped["open_time"].dt.date
        grouped["hour"] = grouped["open_time"].dt.hour
        grouped["weekday"] = grouped["open_time"].dt.day_name()

    return grouped.sort_values("open_time") if "open_time" in grouped.columns else grouped


# =========================
# المقاييس والتحليلات
# =========================

def calculate_metrics(df: pd.DataFrame, profit_col: str = "net_profit") -> Dict[str, object]:
    if df.empty or profit_col not in df.columns:
        return {
            "total_trades": 0,
            "error": "لا توجد صفقات قابلة للتحليل في الفترة المحددة."
        }

    profits = pd.to_numeric(df[profit_col], errors="coerce").dropna()

    total_trades = len(profits)
    wins = profits[profits > 0]
    losses = profits[profits < 0]

    gross_profit = wins.sum()
    gross_loss = losses.sum()
    net_profit = profits.sum()

    metrics = {}
    metrics["total_trades"] = int(total_trades)
    metrics["wins"] = int(len(wins))
    metrics["losses"] = int(len(losses))
    metrics["breakeven"] = int((profits == 0).sum())
    metrics["win_rate"] = round((len(wins) / total_trades) * 100, 2) if total_trades else 0
    metrics["net_profit"] = round(float(net_profit), 2)
    metrics["gross_profit"] = round(float(gross_profit), 2)
    metrics["gross_loss"] = round(float(gross_loss), 2)
    metrics["profit_factor"] = round(float(gross_profit / abs(gross_loss)), 2) if gross_loss < 0 else "Infinity"
    metrics["avg_win"] = round(float(wins.mean()), 2) if len(wins) else 0
    metrics["avg_loss"] = round(float(losses.mean()), 2) if len(losses) else 0
    metrics["best_trade"] = round(float(profits.max()), 2) if len(profits) else 0
    metrics["worst_trade"] = round(float(profits.min()), 2) if len(profits) else 0
    metrics["expectancy"] = round(float(profits.mean()), 2) if len(profits) else 0

    equity = profits.cumsum()
    running_max = equity.cummax()
    drawdown = equity - running_max
    metrics["max_drawdown"] = round(float(drawdown.min()), 2) if len(drawdown) else 0

    loss_streak = 0
    max_loss_streak = 0
    for p in profits:
        if p < 0:
            loss_streak += 1
            max_loss_streak = max(max_loss_streak, loss_streak)
        else:
            loss_streak = 0

    metrics["max_loss_streak"] = int(max_loss_streak)

    return metrics


def group_insights(df: pd.DataFrame, profit_col: str = "net_profit") -> Dict[str, pd.DataFrame]:
    insights = {}

    if df.empty or profit_col not in df.columns:
        return insights

    if "symbol" in df.columns:
        by_symbol = df.groupby("symbol").agg(
            trades=(profit_col, "count"),
            net_profit=(profit_col, "sum"),
            avg_profit=(profit_col, "mean"),
            win_rate=(profit_col, lambda x: (x > 0).mean() * 100),
        ).reset_index()
        by_symbol["net_profit"] = by_symbol["net_profit"].round(2)
        by_symbol["avg_profit"] = by_symbol["avg_profit"].round(2)
        by_symbol["win_rate"] = by_symbol["win_rate"].round(2)
        insights["by_symbol"] = by_symbol.sort_values("net_profit")

    if "hour" in df.columns:
        by_hour = df.groupby("hour").agg(
            trades=(profit_col, "count"),
            net_profit=(profit_col, "sum"),
            avg_profit=(profit_col, "mean"),
            win_rate=(profit_col, lambda x: (x > 0).mean() * 100),
        ).reset_index()
        by_hour["net_profit"] = by_hour["net_profit"].round(2)
        by_hour["avg_profit"] = by_hour["avg_profit"].round(2)
        by_hour["win_rate"] = by_hour["win_rate"].round(2)
        insights["by_hour"] = by_hour.sort_values("hour")

    if "weekday" in df.columns:
        order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        by_weekday = df.groupby("weekday").agg(
            trades=(profit_col, "count"),
            net_profit=(profit_col, "sum"),
            avg_profit=(profit_col, "mean"),
            win_rate=(profit_col, lambda x: (x > 0).mean() * 100),
        ).reset_index()
        by_weekday["weekday"] = pd.Categorical(by_weekday["weekday"], categories=order, ordered=True)
        by_weekday["net_profit"] = by_weekday["net_profit"].round(2)
        by_weekday["avg_profit"] = by_weekday["avg_profit"].round(2)
        by_weekday["win_rate"] = by_weekday["win_rate"].round(2)
        insights["by_weekday"] = by_weekday.sort_values("weekday")

    side_col = "first_side" if "first_side" in df.columns else "deal_type_name"
    if side_col in df.columns:
        by_side = df.groupby(side_col).agg(
            trades=(profit_col, "count"),
            net_profit=(profit_col, "sum"),
            avg_profit=(profit_col, "mean"),
            win_rate=(profit_col, lambda x: (x > 0).mean() * 100),
        ).reset_index()
        by_side["net_profit"] = by_side["net_profit"].round(2)
        by_side["avg_profit"] = by_side["avg_profit"].round(2)
        by_side["win_rate"] = by_side["win_rate"].round(2)
        insights["by_side"] = by_side.sort_values("net_profit")

    return insights


def detect_behavioral_flags(df: pd.DataFrame, profit_col: str = "net_profit") -> List[Dict[str, object]]:
    flags = []

    if df.empty or profit_col not in df.columns:
        return flags

    # كثرة التداول في اليوم
    if "date" in df.columns:
        trades_per_day = df.groupby("date").size()
        high_days = trades_per_day[trades_per_day >= RISK_RULES["max_trades_per_day_warning"]]
        for date, count in high_days.items():
            severity = "High" if count >= RISK_RULES["hard_trades_per_day_limit"] else "Medium"
            flags.append({
                "type": "Overtrading",
                "severity": severity,
                "message": f"عدد صفقات مرتفع في يوم {date}: {int(count)} صفقات.",
                "suggestion": "ضع حد أقصى يومي للصفقات، مثلاً 3 إلى 5 صفقات فقط."
            })

    # سلسلة خسائر
    losses_in_row = 0
    for _, row in df.iterrows():
        p = row.get(profit_col, 0)
        if p < 0:
            losses_in_row += 1
            if losses_in_row == RISK_RULES["bad_loss_streak"]:
                flags.append({
                    "type": "Loss Streak",
                    "severity": "High",
                    "message": f"ظهرت سلسلة خسائر متتالية وصلت إلى {losses_in_row} صفقات.",
                    "suggestion": "بعد خسارتين متتاليتين، أوقف التداول مؤقتاً وراجع سبب الدخول."
                })
            elif losses_in_row >= RISK_RULES["critical_loss_streak"]:
                flags.append({
                    "type": "Critical Loss Streak",
                    "severity": "Critical",
                    "message": f"سلسلة خسائر حرجة وصلت إلى {losses_in_row} صفقات.",
                    "suggestion": "أوقف التداول فوراً لبقية اليوم وراجع خطة الدخول وإدارة المخاطر."
                })
        else:
            losses_in_row = 0

    # رفع الحجم بعد خسارة
    volume_col = "total_volume" if "total_volume" in df.columns else "volume"
    if volume_col in df.columns:
        df2 = df.reset_index(drop=True).copy()
        for i in range(1, len(df2)):
            prev_profit = df2.loc[i - 1, profit_col]
            prev_vol = df2.loc[i - 1, volume_col]
            cur_vol = df2.loc[i, volume_col]

            if pd.notna(prev_profit) and pd.notna(prev_vol) and pd.notna(cur_vol):
                if prev_profit < 0 and prev_vol > 0 and cur_vol >= prev_vol * RISK_RULES["large_lot_increase_ratio"]:
                    flags.append({
                        "type": "Possible Revenge Trading",
                        "severity": "High",
                        "message": f"بعد خسارة، تم رفع الحجم من {round(prev_vol, 2)} إلى {round(cur_vol, 2)}.",
                        "suggestion": "امنع زيادة حجم الصفقة بعد الخسارة. المخاطرة يجب أن تكون ثابتة قبل الدخول."
                    })

    # دخول سريع بعد خسارة
    time_col = "open_time" if "open_time" in df.columns else "time"
    if time_col in df.columns:
        df3 = df.reset_index(drop=True).copy()
        for i in range(1, len(df3)):
            prev_profit = df3.loc[i - 1, profit_col]
            prev_time = df3.loc[i - 1, time_col]
            cur_time = df3.loc[i, time_col]

            if pd.notna(prev_profit) and prev_profit < 0 and pd.notna(prev_time) and pd.notna(cur_time):
                minutes_diff = (cur_time - prev_time).total_seconds() / 60
                if 0 <= minutes_diff <= RISK_RULES["revenge_trade_minutes"]:
                    severity = "High" if minutes_diff <= 5 else "Medium"
                    flags.append({
                        "type": "Fast Re-entry After Loss",
                        "severity": severity,
                        "message": f"تم الدخول بعد خسارة خلال {round(minutes_diff, 1)} دقيقة.",
                        "suggestion": "بعد أي خسارة، انتظر 15 إلى 30 دقيقة على الأقل قبل صفقة جديدة."
                    })

    # إزالة التكرار
    unique = []
    seen = set()
    for f in flags:
        key = (f["type"], f["message"])
        if key not in seen:
            unique.append(f)
            seen.add(key)

    return unique


# =========================
# التشخيص والدرجات - V2
# =========================

def count_flags(flags: List[Dict[str, object]], flag_type: str) -> int:
    return sum(1 for f in flags if f.get("type") == flag_type)


def count_severity(flags: List[Dict[str, object]], severity: str) -> int:
    return sum(1 for f in flags if f.get("severity") == severity)


def clamp_score(score: float) -> int:
    return int(max(0, min(100, round(score))))


def calculate_scores(metrics: Dict[str, object], flags: List[Dict[str, object]]) -> pd.DataFrame:
    """
    يحوّل النتائج إلى درجات مفهومة للعميل.
    هذه ليست حقيقة مطلقة، بل scoring rule قابلة للتعديل.
    """

    total_trades = metrics.get("total_trades", 0) or 0
    win_rate = metrics.get("win_rate", 0) or 0
    expectancy = metrics.get("expectancy", 0) or 0
    max_loss_streak = metrics.get("max_loss_streak", 0) or 0
    profit_factor = metrics.get("profit_factor", 0)

    fast_reentry = count_flags(flags, "Fast Re-entry After Loss")
    revenge = count_flags(flags, "Possible Revenge Trading")
    overtrading = count_flags(flags, "Overtrading")
    high_flags = count_severity(flags, "High")
    critical_flags = count_severity(flags, "Critical")

    # Discipline Score
    discipline = 100
    discipline -= overtrading * 10
    discipline -= fast_reentry * 7
    discipline -= revenge * 15
    discipline -= max(0, max_loss_streak - 2) * 8
    discipline -= critical_flags * 20
    discipline = clamp_score(discipline)

    # Risk Behavior Score
    risk_behavior = 100
    risk_behavior -= revenge * 25
    risk_behavior -= fast_reentry * 8
    risk_behavior -= max(0, max_loss_streak - 2) * 10
    risk_behavior -= high_flags * 4
    risk_behavior -= critical_flags * 20
    risk_behavior = clamp_score(risk_behavior)

    # Performance Quality Score
    performance = 50
    if isinstance(profit_factor, (int, float)):
        if profit_factor >= 2:
            performance += 30
        elif profit_factor >= 1.5:
            performance += 20
        elif profit_factor >= 1:
            performance += 10
        else:
            performance -= 20
    elif profit_factor == "Infinity":
        performance += 15

    if expectancy > 0:
        performance += 15
    else:
        performance -= 15

    if win_rate >= 50:
        performance += 5
    elif win_rate < 40:
        performance -= 5

    performance = clamp_score(performance)

    # Confidence Score based on sample size
    if total_trades >= RISK_RULES["minimum_trades_for_strong_confidence"]:
        confidence = 90
        confidence_label = "Strong"
    elif total_trades >= RISK_RULES["minimum_trades_for_good_confidence"]:
        confidence = 70
        confidence_label = "Good"
    elif total_trades >= 20:
        confidence = 45
        confidence_label = "Initial"
    else:
        confidence = 25
        confidence_label = "Weak"

    overall = clamp_score((discipline * 0.35) + (risk_behavior * 0.30) + (performance * 0.25) + (confidence * 0.10))

    rows = [
        {
            "score_name": "Overall Trading Health Score",
            "score": overall,
            "level": score_level(overall),
            "meaning_ar": "التقييم العام لصحة الحساب بناءً على الأداء والسلوك وحجم العينة."
        },
        {
            "score_name": "Discipline Score",
            "score": discipline,
            "level": score_level(discipline),
            "meaning_ar": "يقيس الانضباط: كثرة التداول، الدخول السريع بعد الخسارة، وسلاسل الخسائر."
        },
        {
            "score_name": "Risk Behavior Score",
            "score": risk_behavior,
            "level": score_level(risk_behavior),
            "meaning_ar": "يقيس سلوك المخاطرة بعد الخسارة، خصوصاً رفع الحجم أو محاولة الاسترجاع."
        },
        {
            "score_name": "Performance Quality Score",
            "score": performance,
            "level": score_level(performance),
            "meaning_ar": "يقيس جودة الأداء المالي من Profit Factor، التوقع الحسابي، ونسبة الربح."
        },
        {
            "score_name": "Data Confidence Score",
            "score": confidence,
            "level": confidence_label,
            "meaning_ar": "يقيس قوة الثقة في التشخيص حسب عدد الصفقات المتاحة للتحليل."
        },
    ]

    return pd.DataFrame(rows)


def score_level(score: int) -> str:
    if score >= 80:
        return "Strong"
    if score >= 65:
        return "Good"
    if score >= 50:
        return "Needs Attention"
    if score >= 35:
        return "Weak"
    return "Critical"


def detect_main_problem(metrics: Dict[str, object], flags: List[Dict[str, object]]) -> Dict[str, str]:
    fast_reentry = count_flags(flags, "Fast Re-entry After Loss")
    revenge = count_flags(flags, "Possible Revenge Trading")
    overtrading = count_flags(flags, "Overtrading")
    loss_streak = count_flags(flags, "Loss Streak") + count_flags(flags, "Critical Loss Streak")

    if revenge > 0 and fast_reentry >= 2:
        return {
            "main_problem": "التداول الانتقامي بعد الخسارة",
            "evidence": "ظهر رفع في حجم الصفقة بعد خسارة، مع عدة دخولات سريعة خلال أقل من 30 دقيقة بعد الخسارة.",
            "risk": "هذا السلوك قد يحول حساباً رابحاً إلى حساب عالي المخاطر عند أول يوم ضغط قوي.",
            "priority": "High"
        }

    if fast_reentry >= 3:
        return {
            "main_problem": "الدخول السريع بعد الخسارة",
            "evidence": "تكرر الدخول بعد خسارة خلال فترة قصيرة، ما يدل على ضعف فترة التقييم بعد الخطأ.",
            "risk": "يزيد احتمال تكرار القرار العاطفي بدل انتظار فرصة واضحة.",
            "priority": "High"
        }

    if overtrading > 0 and loss_streak > 0:
        return {
            "main_problem": "كثرة التداول وقت الضغط",
            "evidence": "ظهر يوم بعدد صفقات مرتفع مع سلسلة خسائر متتالية.",
            "risk": "كثرة التداول قد تضاعف أثر الأخطاء الصغيرة وتحولها إلى خسارة يومية كبيرة.",
            "priority": "Medium"
        }

    pf = metrics.get("profit_factor", 0)
    expectancy = metrics.get("expectancy", 0)
    if (isinstance(pf, (int, float)) and pf < 1) or expectancy < 0:
        return {
            "main_problem": "جودة الأداء المالي ضعيفة",
            "evidence": "Profit Factor أو متوسط العائد لكل صفقة يشير إلى أن الحساب لا يملك أفضلية إحصائية كافية.",
            "risk": "الاستمرار بنفس الطريقة قد يؤدي إلى تآكل الحساب تدريجياً.",
            "priority": "High"
        }

    return {
        "main_problem": "لا توجد مشكلة واحدة حرجة واضحة",
        "evidence": "الأداء العام لا يظهر مشكلة مهيمنة بالقواعد الحالية، لكن يجب مراقبة السلوك بعد الخسارة.",
        "risk": "الخطر الحالي منخفض إلى متوسط، ويحتاج بيانات أكثر لتأكيد التشخيص.",
        "priority": "Low"
    }


def root_cause_hypothesis(main_problem: Dict[str, str]) -> str:
    problem = main_problem.get("main_problem", "")

    if "الانتقامي" in problem:
        return (
            "الفرضية الأقرب: المتداول بعد الخسارة يدخل في وضع استرجاع سريع. "
            "بدلاً من إعادة تقييم السوق، يحاول تعويض الخسارة بصفقة جديدة أو حجم أكبر. "
            "هذا لا يعني أن الاستراتيجية سيئة، بل يعني أن نقطة الضعف تظهر تحت الضغط."
        )

    if "الدخول السريع" in problem:
        return (
            "الفرضية الأقرب: لا توجد فترة تهدئة واضحة بعد الخسارة. "
            "المتداول ينتقل مباشرة من خسارة إلى قرار جديد، وهذا يقلل جودة القرار ويزيد التفاعل العاطفي."
        )

    if "كثرة التداول" in problem:
        return (
            "الفرضية الأقرب: غياب حد يومي واضح للصفقات. "
            "عندما يزداد عدد الفرص أو التوتر، يصبح القرار أكثر تكراراً وأقل انتقائية."
        )

    if "الأداء المالي" in problem:
        return (
            "الفرضية الأقرب: قواعد الدخول أو الخروج أو إدارة المخاطر لا تعطي أفضلية كافية. "
            "يجب فحص متوسط الخسارة، أماكن الدخول، ونسبة العائد إلى المخاطرة."
        )

    return (
        "الفرضية الحالية غير حاسمة بسبب محدودية البيانات أو غياب نمط خطر واضح. "
        "يفضل جمع عدد صفقات أكبر قبل إصدار حكم قوي."
    )


def build_client_diagnosis(metrics: Dict[str, object], flags: List[Dict[str, object]], scores_df: pd.DataFrame) -> pd.DataFrame:
    main = detect_main_problem(metrics, flags)
    root = root_cause_hypothesis(main)

    total_trades = metrics.get("total_trades", 0)
    pf = metrics.get("profit_factor", "")
    net_profit = metrics.get("net_profit", 0)
    win_rate = metrics.get("win_rate", 0)
    avg_win = metrics.get("avg_win", 0)
    avg_loss = metrics.get("avg_loss", 0)
    max_loss_streak = metrics.get("max_loss_streak", 0)

    overall_score = int(scores_df.loc[scores_df["score_name"] == "Overall Trading Health Score", "score"].iloc[0])
    discipline_score = int(scores_df.loc[scores_df["score_name"] == "Discipline Score", "score"].iloc[0])
    risk_score = int(scores_df.loc[scores_df["score_name"] == "Risk Behavior Score", "score"].iloc[0])
    confidence_score = int(scores_df.loc[scores_df["score_name"] == "Data Confidence Score", "score"].iloc[0])

    sample_note = ""
    if total_trades < RISK_RULES["minimum_trades_for_good_confidence"]:
        sample_note = (
            f"ملاحظة مهمة: عدد الصفقات المتاحة للتحليل هو {total_trades} فقط. "
            "هذا يكفي لتشخيص أولي، لكنه لا يكفي لإصدار حكم نهائي قوي. "
            "الأفضل للتحليل الاحترافي هو 50 صفقة أو أكثر، و100 صفقة تعطي ثقة أعلى."
        )
    else:
        sample_note = (
            f"عدد الصفقات المتاحة للتحليل هو {total_trades}. "
            "هذا يعطي قراءة أفضل من العينة الصغيرة، مع ضرورة مقارنة النتائج بفترات مختلفة."
        )

    summary = (
        f"الحساب حقق صافي نتيجة {net_profit} مع نسبة ربح {win_rate}% و Profit Factor بقيمة {pf}. "
        f"متوسط الربح {avg_win} مقابل متوسط خسارة {avg_loss}. "
        f"أطول سلسلة خسائر وصلت إلى {max_loss_streak} صفقات. "
        f"التقييم العام للحساب هو {overall_score}/100، والانضباط {discipline_score}/100، "
        f"وسلوك المخاطرة {risk_score}/100."
    )

    diagnosis = (
        f"المشكلة الرئيسية المكتشفة: {main['main_problem']}. "
        f"الدليل: {main['evidence']} "
        f"الخطر: {main['risk']}"
    )

    recommendation = (
        "التوصية التنفيذية: لا تبدأ بتغيير الاستراتيجية فوراً. "
        "ابدأ أولاً بضبط السلوك بعد الخسارة: أوقف التداول بعد خسارتين، "
        "امنع زيادة الحجم بعد الخسارة، واجعل هناك فترة انتظار إجبارية قبل الصفقة التالية. "
        "بعد أسبوع من الالتزام بهذه القواعد، أعد التحليل وقارن النتائج."
    )

    rows = [
        {"section": "Executive Summary", "content_ar": summary},
        {"section": "Main Problem", "content_ar": diagnosis},
        {"section": "Root Cause Hypothesis", "content_ar": root},
        {"section": "Data Confidence", "content_ar": sample_note},
        {"section": "Primary Recommendation", "content_ar": recommendation},
    ]

    return pd.DataFrame(rows)


def build_action_plan(flags: List[Dict[str, object]]) -> pd.DataFrame:
    """
    خطة 7 أيام قابلة للتطبيق.
    """

    has_revenge = count_flags(flags, "Possible Revenge Trading") > 0
    has_fast = count_flags(flags, "Fast Re-entry After Loss") > 0
    has_over = count_flags(flags, "Overtrading") > 0
    has_streak = count_flags(flags, "Loss Streak") > 0 or count_flags(flags, "Critical Loss Streak") > 0

    rules = []

    rules.append({
        "day": "Day 1",
        "focus": "قاعدة التوقف بعد الخسارة",
        "task": "اكتب قاعدة واضحة: بعد خسارتين متتاليتين أتوقف عن التداول حتى الجلسة التالية.",
        "success_measure": "عدم فتح أي صفقة بعد خسارتين متتاليتين."
    })

    rules.append({
        "day": "Day 2",
        "focus": "فترة تهدئة إجبارية",
        "task": "بعد أي خسارة، انتظر 30 دقيقة قبل التفكير في صفقة جديدة.",
        "success_measure": "لا توجد صفقة جديدة خلال أول 30 دقيقة بعد الخسارة."
    })

    rules.append({
        "day": "Day 3",
        "focus": "ثبات حجم الصفقة",
        "task": "حدد حجم صفقة ثابت أو مخاطرة ثابتة قبل بداية اليوم، وممنوع زيادتها بعد خسارة.",
        "success_measure": "لا توجد زيادة في الحجم بعد صفقة خاسرة."
    })

    rules.append({
        "day": "Day 4",
        "focus": "منع كثرة التداول",
        "task": "ضع حد يومي أقصى: 5 صفقات فقط. الصفقة السادسة ممنوعة إلا إذا كانت A+ Setup موثقة.",
        "success_measure": "عدد الصفقات اليومية لا يتجاوز 5 إلا بسبب واضح ومكتوب."
    })

    rules.append({
        "day": "Day 5",
        "focus": "فلتر الدخول",
        "task": "قبل كل صفقة أجب كتابة: من المسيطر؟ أين الإبطال؟ أين الهدف؟ هل العائد يستحق؟",
        "success_measure": "كل صفقة لها سبب دخول مكتوب قبل التنفيذ."
    })

    rules.append({
        "day": "Day 6",
        "focus": "مراجعة أسوأ توقيت/رمز",
        "task": "راجع صفحة by_hour و by_symbol، وامنع التداول في أسوأ ساعة أو أسوأ رمز لمدة أسبوع.",
        "success_measure": "عدم التداول في المنطقة الزمنية أو الرمز الأسوأ حسب التقرير."
    })

    rules.append({
        "day": "Day 7",
        "focus": "إعادة التحليل",
        "task": "شغل السكربت مرة أخرى وقارن: عدد Flags، صافي الربح، وسلوك الحجم بعد الخسارة.",
        "success_measure": "انخفاض إشارات Fast Re-entry و Revenge Trading."
    })

    # نضيف ملاحظات مخصصة حسب flags
    notes = []
    if has_revenge:
        notes.append("يوجد رفع حجم بعد خسارة، لذلك قاعدة Day 3 مهمة جداً ولا يجب تجاوزها.")
    if has_fast:
        notes.append("يوجد دخول سريع بعد الخسارة، لذلك قاعدة Day 2 هي أهم قاعدة في الأسبوع.")
    if has_over:
        notes.append("يوجد Overtrading، لذلك الحد اليومي للصفقات يجب أن يكون صارماً.")
    if has_streak:
        notes.append("توجد سلسلة خسائر، لذلك قاعدة التوقف بعد خسارتين ضرورية لحماية الحساب.")

    df = pd.DataFrame(rules)
    df["custom_note"] = " | ".join(notes) if notes else "لا توجد ملاحظات مخصصة قوية بناءً على القواعد الحالية."
    return df


# =========================
# الرسوم والتصدير
# =========================

def create_charts(df: pd.DataFrame, out_dir: Path, profit_col: str = "net_profit") -> List[Path]:
    chart_paths = []

    if df.empty or profit_col not in df.columns:
        return chart_paths

    if "equity_curve" in df.columns and "trade_number" in df.columns:
        plt.figure(figsize=(10, 5))
        plt.plot(df["trade_number"], df["equity_curve"], marker="o")
        plt.title("Equity Curve / منحنى الأداء")
        plt.xlabel("Trade Number")
        plt.ylabel("Cumulative Net Profit")
        plt.grid(True, alpha=0.3)
        path = out_dir / "equity_curve.png"
        plt.tight_layout()
        plt.savefig(path, dpi=150)
        plt.close()
        chart_paths.append(path)

    if "symbol" in df.columns:
        by_symbol = df.groupby("symbol")[profit_col].sum().sort_values()
        plt.figure(figsize=(10, 5))
        by_symbol.plot(kind="bar")
        plt.title("Net Profit by Symbol / صافي الربح حسب الرمز")
        plt.xlabel("Symbol")
        plt.ylabel("Net Profit")
        plt.grid(True, axis="y", alpha=0.3)
        path = out_dir / "profit_by_symbol.png"
        plt.tight_layout()
        plt.savefig(path, dpi=150)
        plt.close()
        chart_paths.append(path)

    if "hour" in df.columns:
        by_hour = df.groupby("hour")[profit_col].sum()
        plt.figure(figsize=(10, 5))
        by_hour.plot(kind="bar")
        plt.title("Net Profit by Hour / صافي الربح حسب الساعة")
        plt.xlabel("Hour")
        plt.ylabel("Net Profit")
        plt.grid(True, axis="y", alpha=0.3)
        path = out_dir / "profit_by_hour.png"
        plt.tight_layout()
        plt.savefig(path, dpi=150)
        plt.close()
        chart_paths.append(path)

    return chart_paths


def write_text_report(
    metrics: Dict[str, object],
    flags: List[Dict[str, object]],
    insights: Dict[str, pd.DataFrame],
    scores_df: pd.DataFrame,
    client_diagnosis_df: pd.DataFrame,
    action_plan_df: pd.DataFrame,
    out_dir: Path
) -> Path:
    report_path = out_dir / "diagnostic_report_ar_v2.txt"

    lines = []
    lines.append("تقرير تشخيص حساب التداول - MT5 Direct Pull V2")
    lines.append("=" * 70)
    lines.append("")

    if metrics.get("error"):
        lines.append(str(metrics["error"]))
        report_path.write_text("\n".join(lines), encoding="utf-8")
        return report_path

    lines.append("ملخص الأداء:")
    lines.append(f"- عدد الصفقات/المراكز المحللة: {metrics.get('total_trades')}")
    lines.append(f"- الرابحة: {metrics.get('wins')}")
    lines.append(f"- الخاسرة: {metrics.get('losses')}")
    lines.append(f"- التعادل: {metrics.get('breakeven')}")
    lines.append(f"- نسبة الربح: {metrics.get('win_rate')}%")
    lines.append(f"- صافي الربح/الخسارة: {metrics.get('net_profit')}")
    lines.append(f"- Profit Factor: {metrics.get('profit_factor')}")
    lines.append(f"- متوسط الربح: {metrics.get('avg_win')}")
    lines.append(f"- متوسط الخسارة: {metrics.get('avg_loss')}")
    lines.append(f"- أفضل صفقة: {metrics.get('best_trade')}")
    lines.append(f"- أسوأ صفقة: {metrics.get('worst_trade')}")
    lines.append(f"- التوقع الحسابي لكل صفقة: {metrics.get('expectancy')}")
    lines.append(f"- أكبر تراجع تقريبي: {metrics.get('max_drawdown')}")
    lines.append(f"- أطول سلسلة خسائر: {metrics.get('max_loss_streak')}")
    lines.append("")

    lines.append("Scores:")
    for _, row in scores_df.iterrows():
        lines.append(f"- {row['score_name']}: {row['score']}/100 ({row['level']})")
    lines.append("")

    lines.append("تشخيص العميل:")
    for _, row in client_diagnosis_df.iterrows():
        lines.append(f"[{row['section']}]")
        lines.append(row["content_ar"])
        lines.append("")

    lines.append("الأعلام السلوكية المكتشفة:")
    if flags:
        for i, f in enumerate(flags[:30], start=1):
            lines.append(f"{i}) [{f['severity']}] {f['type']}: {f['message']}")
            lines.append(f"   التعديل المقترح: {f['suggestion']}")
    else:
        lines.append("- لم يتم اكتشاف أعلام سلوكية واضحة بالقواعد الحالية.")

    lines.append("")

    if "by_symbol" in insights and not insights["by_symbol"].empty:
        lines.append("أسوأ الرموز حسب صافي الربح:")
        for _, row in insights["by_symbol"].head(5).iterrows():
            lines.append(f"- {row['symbol']}: صافي {row['net_profit']} من {int(row['trades'])} صفقات")
        lines.append("")

    if "by_hour" in insights and not insights["by_hour"].empty:
        lines.append("أسوأ ساعات التداول حسب صافي الربح:")
        worst_hours = insights["by_hour"].sort_values("net_profit").head(5)
        for _, row in worst_hours.iterrows():
            lines.append(f"- الساعة {int(row['hour'])}: صافي {row['net_profit']} من {int(row['trades'])} صفقات")
        lines.append("")

    lines.append("خطة تعديل 7 أيام:")
    for _, row in action_plan_df.iterrows():
        lines.append(f"- {row['day']} | {row['focus']}: {row['task']}")
        lines.append(f"  قياس النجاح: {row['success_measure']}")
    lines.append("")
    lines.append("تحذير: هذا التقرير تحليل بيانات فقط وليس توصية تداول. التداول يحمل مخاطرة حقيقية، والقرار النهائي مسؤولية المتداول.")

    report_path.write_text("\n".join(lines), encoding="utf-8")
    return report_path


def write_excel_report(
    raw_deals: pd.DataFrame,
    trade_deals: pd.DataFrame,
    position_summary: pd.DataFrame,
    raw_orders: pd.DataFrame,
    metrics: Dict[str, object],
    flags: List[Dict[str, object]],
    insights: Dict[str, pd.DataFrame],
    scores_df: pd.DataFrame,
    client_diagnosis_df: pd.DataFrame,
    action_plan_df: pd.DataFrame,
    account_data: Dict[str, object],
    date_from: datetime,
    date_to: datetime,
    out_dir: Path
) -> Path:
    excel_path = out_dir / "mt5_direct_diagnostic_report_v2.xlsx"

    metrics_df = pd.DataFrame(list(metrics.items()), columns=["Metric", "Value"])
    flags_df = pd.DataFrame(flags) if flags else pd.DataFrame(columns=["type", "severity", "message", "suggestion"])

    account_df = pd.DataFrame([
        {"field": "login", "value": account_data.get("login")},
        {"field": "server", "value": account_data.get("server")},
        {"field": "name", "value": account_data.get("name")},
        {"field": "balance", "value": account_data.get("balance")},
        {"field": "equity", "value": account_data.get("equity")},
        {"field": "currency", "value": account_data.get("currency")},
        {"field": "company", "value": account_data.get("company")},
        {"field": "leverage", "value": account_data.get("leverage")},
        {"field": "analysis_from", "value": str(date_from)},
        {"field": "analysis_to", "value": str(date_to)},
    ])

    with pd.ExcelWriter(excel_path, engine="openpyxl") as writer:
        account_df.to_excel(writer, index=False, sheet_name="Account Info")
        scores_df.to_excel(writer, index=False, sheet_name="Scores")
        client_diagnosis_df.to_excel(writer, index=False, sheet_name="Client Diagnosis")
        action_plan_df.to_excel(writer, index=False, sheet_name="Action Plan")
        metrics_df.to_excel(writer, index=False, sheet_name="Summary")
        flags_df.to_excel(writer, index=False, sheet_name="Behavior Flags")

        if not position_summary.empty:
            position_summary.to_excel(writer, index=False, sheet_name="Position Summary")

        trade_deals.to_excel(writer, index=False, sheet_name="Trade Deals")
        raw_deals.to_excel(writer, index=False, sheet_name="Raw Deals")

        if not raw_orders.empty:
            raw_orders.to_excel(writer, index=False, sheet_name="Raw Orders")

        for name, table in insights.items():
            sheet_name = name[:31]
            table.to_excel(writer, index=False, sheet_name=sheet_name)

    return excel_path


# =========================
# Main
# =========================

def run(args):
    out_dir = Path(OUTPUT_DIR)
    out_dir.mkdir(exist_ok=True)

    account_data = connect_mt5(
        terminal_path=args.terminal,
        login=args.login,
        password=args.password,
        server=args.server,
        timeout=args.timeout
    )

    date_from, date_to = get_date_range(args)
    print(f"\nسحب البيانات من: {date_from}")
    print(f"إلى: {date_to}")

    raw_deals = pull_deals(date_from, date_to, group=args.group)
    raw_orders = pull_orders(date_from, date_to, group=args.group)

    if raw_deals.empty:
        print("\nلم يتم العثور على Deals في هذه الفترة.")
        print("جرّب تكبير الفترة مثل: --days 365")
        print("وتأكد أن الحساب المفتوح في MT5 هو الحساب الصحيح.")
        mt5.shutdown()
        return

    trade_deals = prepare_trade_deals(raw_deals)
    position_summary = build_position_summary(trade_deals)

    analysis_df = position_summary if not position_summary.empty else trade_deals
    profit_col = "net_profit"

    metrics = calculate_metrics(analysis_df, profit_col=profit_col)
    insights = group_insights(analysis_df, profit_col=profit_col)
    flags = detect_behavioral_flags(analysis_df, profit_col=profit_col)

    scores_df = calculate_scores(metrics, flags)
    client_diagnosis_df = build_client_diagnosis(metrics, flags, scores_df)
    action_plan_df = build_action_plan(flags)

    chart_paths = create_charts(analysis_df, out_dir, profit_col=profit_col)

    txt_report = write_text_report(
        metrics=metrics,
        flags=flags,
        insights=insights,
        scores_df=scores_df,
        client_diagnosis_df=client_diagnosis_df,
        action_plan_df=action_plan_df,
        out_dir=out_dir
    )

    excel_report = write_excel_report(
        raw_deals=raw_deals,
        trade_deals=trade_deals,
        position_summary=position_summary,
        raw_orders=raw_orders,
        metrics=metrics,
        flags=flags,
        insights=insights,
        scores_df=scores_df,
        client_diagnosis_df=client_diagnosis_df,
        action_plan_df=action_plan_df,
        account_data=account_data,
        date_from=date_from,
        date_to=date_to,
        out_dir=out_dir
    )

    raw_deals.to_csv(out_dir / "raw_deals.csv", index=False, encoding="utf-8-sig")
    trade_deals.to_csv(out_dir / "trade_deals_clean.csv", index=False, encoding="utf-8-sig")
    if not position_summary.empty:
        position_summary.to_csv(out_dir / "position_summary.csv", index=False, encoding="utf-8-sig")

    scores_df.to_csv(out_dir / "scores.csv", index=False, encoding="utf-8-sig")
    client_diagnosis_df.to_csv(out_dir / "client_diagnosis.csv", index=False, encoding="utf-8-sig")
    action_plan_df.to_csv(out_dir / "action_plan.csv", index=False, encoding="utf-8-sig")

    mt5.shutdown()

    print("\nتم الانتهاء بنجاح ✅")
    print(f"المجلد: {out_dir.resolve()}")
    print(f"التقرير النصي: {txt_report.resolve()}")
    print(f"تقرير Excel: {excel_report.resolve()}")

    if chart_paths:
        print("الرسوم:")
        for p in chart_paths:
            print(f"- {p.resolve()}")

    print("\nملخص سريع:")
    for k, v in metrics.items():
        print(f"{k}: {v}")

    print("\nScores:")
    for _, row in scores_df.iterrows():
        print(f"{row['score_name']}: {row['score']}/100 ({row['level']})")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Pull MT5 trading history directly and generate V2 diagnostic report.")

    parser.add_argument("--terminal", default=None, help="مسار terminal64.exe إذا لم يتم العثور على MT5 تلقائياً.")
    parser.add_argument("--login", type=int, default=None, help="رقم حساب التداول. اختياري إذا الحساب مفتوح داخل MT5.")
    parser.add_argument("--password", default=None, help="كلمة مرور حساب التداول.")
    parser.add_argument("--server", default=None, help="اسم سيرفر البروكر كما يظهر في MT5.")
    parser.add_argument("--timeout", type=int, default=60000, help="مهلة الاتصال بالمللي ثانية.")

    parser.add_argument("--days", type=int, default=90, help="عدد الأيام السابقة للسحب إذا لم تحدد --from.")
    parser.add_argument("--from", dest="from_date", default=None, help="تاريخ البداية بصيغة YYYY-MM-DD")
    parser.add_argument("--to", dest="to_date", default=None, help="تاريخ النهاية بصيغة YYYY-MM-DD")

    parser.add_argument("--group", default=None, help='فلتر الرموز مثل: "XAUUSD*" حسب قواعد MT5. اختياري.')

    args = parser.parse_args()

    run(args)
