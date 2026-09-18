from pathlib import Path

import pandas as pd

from mt5_file_analyzer import (
    analyze_mt5_file,
    build_position_summary,
    calculate_max_drawdown,
    prepare_trades,
)


ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / "mt5_sample_statement_for_analysis.html"
REALISTIC_DEMO = ROOT / "samples" / "mt5_realistic_deals_demo.csv"


def test_sample_statement_generates_complete_report(tmp_path):
    result = analyze_mt5_file(SAMPLE, tmp_path)

    assert result["raw_rows"] == 225
    assert result["clean_rows"] == 222
    assert Path(result["excel_report"]).exists()
    assert Path(result["text_report"]).exists()

    workbook = pd.ExcelFile(result["excel_report"])
    expected = {
        "Account Info",
        "Summary",
        "Scores",
        "Client Diagnosis",
        "Action Plan",
        "Behavior Flags",
        "Smart Solutions",
        "Position Summary",
        "Trade Deals",
        "by_symbol",
        "by_hour",
        "by_weekday",
        "by_side",
    }
    assert expected.issubset(set(workbook.sheet_names))


def test_drawdown_uses_starting_balance_and_zero_baseline():
    curve = pd.Series([-100.0, -50.0, -250.0])
    amount, percentage = calculate_max_drawdown(curve, initial_balance=1000.0)

    assert amount == -250.0
    assert percentage == -25.0


def test_deal_rows_are_consolidated_by_position_id():
    raw = pd.DataFrame(
        [
            {
                "Time": "2026-01-01 10:00:00",
                "Position": 77,
                "Deal": 1,
                "Symbol": "XAUUSD",
                "Type": "buy",
                "Volume": 0.1,
                "Price": 2300,
                "Profit": 0,
                "Commission": -1,
            },
            {
                "Time": "2026-01-01 11:00:00",
                "Position": 77,
                "Deal": 2,
                "Symbol": "XAUUSD",
                "Type": "sell",
                "Volume": 0.1,
                "Price": 2310,
                "Profit": 100,
                "Commission": -1,
            },
        ]
    )

    deals = prepare_trades(raw)
    positions = build_position_summary(deals)

    assert len(deals) == 2
    assert len(positions) == 1
    assert positions.iloc[0]["deal_count"] == 2
    assert positions.iloc[0]["net_profit"] == 98


def test_realistic_deal_statement_runs_full_pipeline(tmp_path):
    result = analyze_mt5_file(REALISTIC_DEMO, tmp_path)

    assert result["raw_rows"] == 37
    assert result["clean_rows"] == 18

    account = pd.read_excel(result["excel_report"], sheet_name="Account Info")
    account_values = dict(zip(account["field"], account["value"]))
    assert account_values["deal_rows_clean"] == 36
    assert account_values["initial_balance_detected"] == 10000

    flags = pd.read_excel(result["excel_report"], sheet_name="Behavior Flags")
    flag_types = set(flags["type"])
    assert "Overtrading" in flag_types
    assert "Fast Re-entry After Loss" in flag_types
    assert "Possible Revenge Trading" in flag_types
