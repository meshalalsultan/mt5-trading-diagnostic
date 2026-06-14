# mt5_file_analyzer.py
# ------------------------------------------------------------
# MT5 File Analyzer
# يحلل كشف MT5 من ملف CSV / HTML / XLS / XLSX
# بدون الحاجة إلى وجود منصة MT5 أو حساب العميل
#
# الاستخدام البرمجي:
# from mt5_file_analyzer import analyze_mt5_file
# analyze_mt5_file("statement.html", output_dir="mt5_file_output")
#
# الاستخدام من Command Prompt:
# python mt5_file_analyzer.py "statement.html"
# ------------------------------------------------------------

import argparse
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt


OUTPUT_DIR = "mt5_file_output"

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
# قراءة الملف
# =========================

def clean_col_name(col) -> str:
    col = str(col).strip()
    col = re.sub(r"\s+", " ", col)
    return col


def read_mt5_file(file_path: str | Path) -> pd.DataFrame:
    file_path = Path(file_path)
    suffix = file_path.suffix.lower()

    if not file_path.exists():
        raise FileNotFoundError(f"الملف غير موجود: {file_path}")

    if suffix in [".csv", ".txt"]:
        # نحاول أكثر من encoding لأن ملفات MT5 قد تختلف
        for enc in ["utf-8-sig", "utf-16", "cp1256", "cp1252", "latin1"]:
            try:
                return pd.read_csv(file_path, sep=None, engine="python", encoding=enc)
            except Exception:
                continue
        return pd.read_csv(file_path, sep=None, engine="python")

    if suffix in [".xlsx", ".xlsm", ".xls"]:
        try:
            return pd.read_excel(file_path)
        except Exception:
            tables = pd.read_html(file_path)
            return choose_best_table(tables)

    if suffix in [".html", ".htm"]:
        tables = pd.read_html(file_path)
        return choose_best_table(tables)

    raise ValueError(f"نوع الملف غير مدعوم: {suffix}. استخدم CSV أو HTML أو Excel.")


def choose_best_table(tables: List[pd.DataFrame]) -> pd.DataFrame:
    if not tables:
        raise ValueError("لم يتم العثور على جداول داخل الملف.")

    best_df = None
    best_score = -1

    keywords = [
        "time", "symbol", "type", "volume", "profit", "price",
        "commission", "swap", "deal", "order", "position",
        "ticket", "item", "size", "p/l"
    ]

    for table in tables:
        table = table.copy()
        table.columns = [clean_col_name(c) for c in table.columns]
        col_text = " ".join([str(c).lower() for c in table.columns])
        score = sum(1 for k in keywords if k in col_text)
        score += min(len(table), 1000) / 1000

        if score > best_score:
            best_score = score
            best_df = table

    if best_df is None:
        raise ValueError("تعذر اختيار جدول مناسب من التقرير.")

    return best_df


# =========================
# تنظيف البيانات
# =========================

def parse_number(x):
    if pd.isna(x):
        return np.nan

    if isinstance(x, (int, float, np.integer, np.floating)):
        return float(x)

    s = str(x).strip()
    if s == "":
        return np.nan

    # بعض التقارير تضع المسافات أو فواصل آلاف
    s = s.replace(",", "")
    s = s.replace(" ", "")
    s = re.sub(r"[^\d\.\-\+]", "", s)

    if s in ["", "-", "+", ".", "-.", "+."]:
        return np.nan

    try:
        return float(s)
    except ValueError:
        return np.nan


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [clean_col_name(c) for c in df.columns]

    aliases = {
        "time": [
            "Time", "Open Time", "Close Time", "Date", "Datetime", "Time Open",
            "OpenTime", "CloseTime"
        ],
        "symbol": [
            "Symbol", "Item", "Instrument", "Market"
        ],
        "type": [
            "Type", "Action", "Side", "Operation"
        ],
        "volume": [
            "Volume", "Size", "Lots", "Lot"
        ],
        "price": [
            "Price", "Open Price", "Close Price"
        ],
        "profit": [
            "Profit", "P/L", "Net Profit", "PnL", "P&L", "Profit/Loss"
        ],
        "commission": [
            "Commission", "Comm"
        ],
        "swap": [
            "Swap", "Storage"
        ],
        "fee": [
            "Fee", "Fees"
        ],
        "ticket": [
            "Ticket", "Deal", "Order", "Position", "ID"
        ],
    }

    rename = {}
    lower_cols = {str(c).lower().strip(): c for c in df.columns}

    for target, possible in aliases.items():
        for p in possible:
            key = p.lower().strip()
            if key in lower_cols:
                rename[lower_cols[key]] = target
                break

    df = df.rename(columns=rename)

    # إذا لا توجد أسماء واضحة، نحاول اكتشاف صف العناوين داخل الجدول
    expected = {"time", "symbol", "type", "volume", "profit"}
    if len(expected.intersection(set(df.columns))) < 2:
        for idx in range(min(10, len(df))):
            row_values = [str(x).strip() for x in df.iloc[idx].tolist()]
            row_text = " ".join(row_values).lower()
            hits = sum(1 for k in ["time", "symbol", "type", "volume", "profit", "price"] if k in row_text)
            if hits >= 3:
                new_cols = [clean_col_name(x) for x in row_values]
                df = df.iloc[idx + 1:].copy()
                df.columns = new_cols
                return normalize_columns(df)

    return df


def prepare_trades(raw_df: pd.DataFrame) -> pd.DataFrame:
    df = raw_df.copy()
    df = df.dropna(how="all")
    df = normalize_columns(df)

    # حذف صفوف العناوين المكررة داخل الجدول
    for col in df.columns:
        df[col] = df[col].replace("", np.nan)

    for col in ["profit", "volume", "price", "commission", "swap", "fee"]:
        if col in df.columns:
            df[col] = df[col].apply(parse_number)

    if "time" in df.columns:
        df["time"] = pd.to_datetime(df["time"], errors="coerce")

    # استبعاد صفوف balance/deposit/withdraw قدر الإمكان
    if "type" in df.columns:
        type_str = df["type"].astype(str).str.lower()
        exclude_words = [
            "balance", "deposit", "withdraw", "credit", "charge",
            "correction", "bonus", "commission", "fee"
        ]
        for word in exclude_words:
            df = df[~type_str.str.contains(word, na=False)].copy()
            type_str = df["type"].astype(str).str.lower()

    # يجب وجود profit للصفقة المغلقة
    if "profit" in df.columns:
        df = df[df["profit"].notna()].copy()

    # لو التقرير يحتوي صفقات مفتوحة أو صفوف ملخص، نحذف غير المفيد قدر الإمكان
    if "symbol" in df.columns:
        df = df[df["symbol"].notna()].copy()
        df["symbol"] = df["symbol"].astype(str).str.upper().str.strip()

    if "type" in df.columns:
        df["type"] = df["type"].astype(str).str.upper().str.strip()

    # صافي الربح
    df["net_profit"] = 0.0
    if "profit" in df.columns:
        df["net_profit"] += pd.to_numeric(df["profit"], errors="coerce").fillna(0)
    if "commission" in df.columns:
        df["net_profit"] += pd.to_numeric(df["commission"], errors="coerce").fillna(0)
    if "swap" in df.columns:
        df["net_profit"] += pd.to_numeric(df["swap"], errors="coerce").fillna(0)
    if "fee" in df.columns:
        df["net_profit"] += pd.to_numeric(df["fee"], errors="coerce").fillna(0)

    if "time" in df.columns:
        df = df.sort_values("time")
        df["date"] = df["time"].dt.date
        df["hour"] = df["time"].dt.hour
        df["weekday"] = df["time"].dt.day_name()

    df["result"] = np.where(df["net_profit"] > 0, "Win", np.where(df["net_profit"] < 0, "Loss", "Breakeven"))
    df["trade_number"] = np.arange(1, len(df) + 1)
    df["equity_curve"] = df["net_profit"].cumsum()

    return df


# =========================
# المقاييس والتحليل
# =========================

def calculate_metrics(df: pd.DataFrame, profit_col: str = "net_profit") -> Dict[str, object]:
    if df.empty or profit_col not in df.columns:
        return {
            "total_trades": 0,
            "error": "لا توجد صفقات قابلة للتحليل أو لا يوجد عمود Profit."
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

    side_col = "type" if "type" in df.columns else None
    if side_col:
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

    volume_col = "volume" if "volume" in df.columns else None
    if volume_col:
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

    if "time" in df.columns:
        df3 = df.reset_index(drop=True).copy()
        for i in range(1, len(df3)):
            prev_profit = df3.loc[i - 1, profit_col]
            prev_time = df3.loc[i - 1, "time"]
            cur_time = df3.loc[i, "time"]

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

    unique = []
    seen = set()
    for f in flags:
        key = (f["type"], f["message"])
        if key not in seen:
            unique.append(f)
            seen.add(key)

    return unique


# =========================
# Scores / Diagnosis
# =========================

def count_flags(flags: List[Dict[str, object]], flag_type: str) -> int:
    return sum(1 for f in flags if f.get("type") == flag_type)


def count_severity(flags: List[Dict[str, object]], severity: str) -> int:
    return sum(1 for f in flags if f.get("severity") == severity)


def clamp_score(score: float) -> int:
    return int(max(0, min(100, round(score))))


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


def calculate_scores(metrics: Dict[str, object], flags: List[Dict[str, object]]) -> pd.DataFrame:
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

    discipline = 100
    discipline -= overtrading * 10
    discipline -= fast_reentry * 7
    discipline -= revenge * 15
    discipline -= max(0, max_loss_streak - 2) * 8
    discipline -= critical_flags * 20
    discipline = clamp_score(discipline)

    risk_behavior = 100
    risk_behavior -= revenge * 25
    risk_behavior -= fast_reentry * 8
    risk_behavior -= max(0, max_loss_streak - 2) * 10
    risk_behavior -= high_flags * 4
    risk_behavior -= critical_flags * 20
    risk_behavior = clamp_score(risk_behavior)

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
    has_revenge = count_flags(flags, "Possible Revenge Trading") > 0
    has_fast = count_flags(flags, "Fast Re-entry After Loss") > 0
    has_over = count_flags(flags, "Overtrading") > 0
    has_streak = count_flags(flags, "Loss Streak") > 0 or count_flags(flags, "Critical Loss Streak") > 0

    rules = [
        {
            "day": "Day 1",
            "focus": "قاعدة التوقف بعد الخسارة",
            "task": "اكتب قاعدة واضحة: بعد خسارتين متتاليتين أتوقف عن التداول حتى الجلسة التالية.",
            "success_measure": "عدم فتح أي صفقة بعد خسارتين متتاليتين."
        },
        {
            "day": "Day 2",
            "focus": "فترة تهدئة إجبارية",
            "task": "بعد أي خسارة، انتظر 30 دقيقة قبل التفكير في صفقة جديدة.",
            "success_measure": "لا توجد صفقة جديدة خلال أول 30 دقيقة بعد الخسارة."
        },
        {
            "day": "Day 3",
            "focus": "ثبات حجم الصفقة",
            "task": "حدد حجم صفقة ثابت أو مخاطرة ثابتة قبل بداية اليوم، وممنوع زيادتها بعد خسارة.",
            "success_measure": "لا توجد زيادة في الحجم بعد صفقة خاسرة."
        },
        {
            "day": "Day 4",
            "focus": "منع كثرة التداول",
            "task": "ضع حد يومي أقصى: 5 صفقات فقط. الصفقة السادسة ممنوعة إلا إذا كانت A+ Setup موثقة.",
            "success_measure": "عدد الصفقات اليومية لا يتجاوز 5 إلا بسبب واضح ومكتوب."
        },
        {
            "day": "Day 5",
            "focus": "فلتر الدخول",
            "task": "قبل كل صفقة أجب كتابة: من المسيطر؟ أين الإبطال؟ أين الهدف؟ هل العائد يستحق؟",
            "success_measure": "كل صفقة لها سبب دخول مكتوب قبل التنفيذ."
        },
        {
            "day": "Day 6",
            "focus": "مراجعة أسوأ توقيت/رمز",
            "task": "راجع صفحة by_hour و by_symbol، وامنع التداول في أسوأ ساعة أو أسوأ رمز لمدة أسبوع.",
            "success_measure": "عدم التداول في المنطقة الزمنية أو الرمز الأسوأ حسب التقرير."
        },
        {
            "day": "Day 7",
            "focus": "إعادة التحليل",
            "task": "شغل التحليل مرة أخرى وقارن: عدد Flags، صافي الربح، وسلوك الحجم بعد الخسارة.",
            "success_measure": "انخفاض إشارات Fast Re-entry و Revenge Trading."
        },
    ]

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
# التصدير
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
    lines.append("تقرير تشخيص حساب التداول - MT5 File Upload Analysis")
    lines.append("=" * 70)
    lines.append("")

    if metrics.get("error"):
        lines.append(str(metrics["error"]))
        report_path.write_text("\n".join(lines), encoding="utf-8")
        return report_path

    lines.append("ملخص الأداء:")
    for key, value in metrics.items():
        lines.append(f"- {key}: {value}")
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
    lines.append("خطة تعديل 7 أيام:")
    for _, row in action_plan_df.iterrows():
        lines.append(f"- {row['day']} | {row['focus']}: {row['task']}")
        lines.append(f"  قياس النجاح: {row['success_measure']}")

    lines.append("")
    lines.append("تحذير: هذا التقرير تحليل بيانات فقط وليس توصية تداول. التداول يحمل مخاطرة حقيقية، والقرار النهائي مسؤولية المتداول.")

    report_path.write_text("\n".join(lines), encoding="utf-8")
    return report_path


def write_excel_report(
    raw_df: pd.DataFrame,
    clean_trades: pd.DataFrame,
    metrics: Dict[str, object],
    flags: List[Dict[str, object]],
    insights: Dict[str, pd.DataFrame],
    scores_df: pd.DataFrame,
    client_diagnosis_df: pd.DataFrame,
    action_plan_df: pd.DataFrame,
    source_file_name: str,
    out_dir: Path
) -> Path:
    excel_path = out_dir / "mt5_file_diagnostic_report_v2.xlsx"

    metrics_df = pd.DataFrame(list(metrics.items()), columns=["Metric", "Value"])
    flags_df = pd.DataFrame(flags) if flags else pd.DataFrame(columns=["type", "severity", "message", "suggestion"])

    account_df = pd.DataFrame([
        {"field": "source_type", "value": "Uploaded File"},
        {"field": "source_file", "value": source_file_name},
        {"field": "total_rows_raw", "value": len(raw_df)},
        {"field": "total_rows_clean", "value": len(clean_trades)},
    ])

    with pd.ExcelWriter(excel_path, engine="openpyxl") as writer:
        account_df.to_excel(writer, index=False, sheet_name="Account Info")
        scores_df.to_excel(writer, index=False, sheet_name="Scores")
        client_diagnosis_df.to_excel(writer, index=False, sheet_name="Client Diagnosis")
        action_plan_df.to_excel(writer, index=False, sheet_name="Action Plan")
        metrics_df.to_excel(writer, index=False, sheet_name="Summary")
        flags_df.to_excel(writer, index=False, sheet_name="Behavior Flags")
        clean_trades.to_excel(writer, index=False, sheet_name="Position Summary")
        clean_trades.to_excel(writer, index=False, sheet_name="Trade Deals")
        raw_df.to_excel(writer, index=False, sheet_name="Raw Uploaded Data")

        for name, table in insights.items():
            table.to_excel(writer, index=False, sheet_name=name[:31])

    return excel_path


def analyze_mt5_file(input_file: str | Path, output_dir: str | Path = OUTPUT_DIR) -> Dict[str, object]:
    input_file = Path(input_file)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    raw_df = read_mt5_file(input_file)
    clean_trades = prepare_trades(raw_df)

    metrics = calculate_metrics(clean_trades)
    insights = group_insights(clean_trades)
    flags = detect_behavioral_flags(clean_trades)

    scores_df = calculate_scores(metrics, flags)
    client_diagnosis_df = build_client_diagnosis(metrics, flags, scores_df)
    action_plan_df = build_action_plan(flags)

    chart_paths = create_charts(clean_trades, output_dir)

    txt_report = write_text_report(
        metrics=metrics,
        flags=flags,
        insights=insights,
        scores_df=scores_df,
        client_diagnosis_df=client_diagnosis_df,
        action_plan_df=action_plan_df,
        out_dir=output_dir
    )

    excel_report = write_excel_report(
        raw_df=raw_df,
        clean_trades=clean_trades,
        metrics=metrics,
        flags=flags,
        insights=insights,
        scores_df=scores_df,
        client_diagnosis_df=client_diagnosis_df,
        action_plan_df=action_plan_df,
        source_file_name=input_file.name,
        out_dir=output_dir
    )

    raw_df.to_csv(output_dir / "raw_uploaded_data.csv", index=False, encoding="utf-8-sig")
    clean_trades.to_csv(output_dir / "position_summary.csv", index=False, encoding="utf-8-sig")
    clean_trades.to_csv(output_dir / "trade_deals_clean.csv", index=False, encoding="utf-8-sig")
    scores_df.to_csv(output_dir / "scores.csv", index=False, encoding="utf-8-sig")
    client_diagnosis_df.to_csv(output_dir / "client_diagnosis.csv", index=False, encoding="utf-8-sig")
    action_plan_df.to_csv(output_dir / "action_plan.csv", index=False, encoding="utf-8-sig")

    return {
        "output_dir": str(output_dir.resolve()),
        "excel_report": str(excel_report.resolve()),
        "txt_report": str(txt_report.resolve()),
        "chart_paths": [str(p.resolve()) for p in chart_paths],
        "metrics": metrics,
        "flags_count": len(flags),
        "clean_rows": len(clean_trades),
        "raw_rows": len(raw_df),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Analyze MT5 statement file CSV/HTML/Excel.")
    parser.add_argument("input_file", help="مسار ملف كشف MT5 بصيغة CSV أو HTML أو Excel")
    parser.add_argument("--output-dir", default=OUTPUT_DIR, help="مجلد المخرجات")
    args = parser.parse_args()

    result = analyze_mt5_file(args.input_file, args.output_dir)

    print("تم التحليل بنجاح ✅")
    print(f"Output dir: {result['output_dir']}")
    print(f"Excel report: {result['excel_report']}")
    print(f"Text report: {result['txt_report']}")
    print("Metrics:")
    for k, v in result["metrics"].items():
        print(f"- {k}: {v}")
