# mt5_diagnostic_dashboard.py
# ------------------------------------------------------------
# MT5 Diagnostic Dashboard
# يقرأ مخرجات سكربت:
# mt5_direct_pull_diagnostic_v2.py
#
# التشغيل:
# 1) تأكد أنك شغلت سكربت V2 أولاً وطلع مجلد mt5_direct_output_v2
# 2) ثبت Streamlit:
#    python -m pip install streamlit plotly pandas openpyxl
# 3) شغل الداشبورد:
#    streamlit run mt5_diagnostic_dashboard.py
#
# إذا كان مجلد النتائج في مكان مختلف:
#    streamlit run mt5_diagnostic_dashboard.py -- --data-dir "C:\Users\dell\mt5_direct_output_v2"
# ------------------------------------------------------------

import argparse
from pathlib import Path

import pandas as pd
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go


DEFAULT_DATA_DIR = Path.home() / "mt5_direct_output_v2"


# =========================
# Page Config
# =========================

st.set_page_config(
    page_title="MT5 Trading Diagnostic Dashboard",
    page_icon="📊",
    layout="wide",
)


# =========================
# Styling
# =========================

CUSTOM_CSS = """
<style>
.main {
    background-color: #f8fafc;
}
.block-container {
    padding-top: 2rem;
    padding-bottom: 2rem;
}
.metric-card {
    background: white;
    padding: 18px 20px;
    border-radius: 16px;
    border: 1px solid #e5e7eb;
    box-shadow: 0 8px 24px rgba(15, 23, 42, 0.05);
}
.section-card {
    background: white;
    padding: 22px;
    border-radius: 18px;
    border: 1px solid #e5e7eb;
    box-shadow: 0 8px 24px rgba(15, 23, 42, 0.05);
    margin-bottom: 18px;
}
.big-title {
    font-size: 34px;
    font-weight: 800;
    color: #0f172a;
    margin-bottom: 0;
}
.subtitle {
    font-size: 16px;
    color: #64748b;
    margin-top: 4px;
}
.score-box {
    background: linear-gradient(135deg, #0f172a, #1e293b);
    color: white;
    padding: 22px;
    border-radius: 20px;
    box-shadow: 0 12px 30px rgba(15, 23, 42, 0.2);
}
.score-label {
    color: #cbd5e1;
    font-size: 14px;
}
.score-value {
    color: white;
    font-size: 42px;
    font-weight: 900;
    margin: 0;
}
.warning-box {
    background: #fff7ed;
    border: 1px solid #fed7aa;
    color: #9a3412;
    padding: 16px 18px;
    border-radius: 16px;
}
.good-box {
    background: #ecfdf5;
    border: 1px solid #a7f3d0;
    color: #065f46;
    padding: 16px 18px;
    border-radius: 16px;
}
.badge-high {
    background: #fee2e2;
    color: #991b1b;
    padding: 4px 10px;
    border-radius: 999px;
    font-weight: 700;
}
.badge-medium {
    background: #fef3c7;
    color: #92400e;
    padding: 4px 10px;
    border-radius: 999px;
    font-weight: 700;
}
.badge-low {
    background: #dcfce7;
    color: #166534;
    padding: 4px 10px;
    border-radius: 999px;
    font-weight: 700;
}
</style>
"""

st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


# =========================
# Helpers
# =========================

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", default=str(DEFAULT_DATA_DIR))
    args, _ = parser.parse_known_args()
    return args


@st.cache_data(show_spinner=False)
def load_csv(path: str) -> pd.DataFrame:
    p = Path(path)
    if not p.exists():
        return pd.DataFrame()
    return pd.read_csv(p)


@st.cache_data(show_spinner=False)
def load_excel_sheet(excel_path: str, sheet_name: str) -> pd.DataFrame:
    p = Path(excel_path)
    if not p.exists():
        return pd.DataFrame()
    try:
        return pd.read_excel(p, sheet_name=sheet_name)
    except Exception:
        return pd.DataFrame()


def find_excel(data_dir: Path) -> Path | None:
    candidates = [
        data_dir / "mt5_direct_diagnostic_report_v2.xlsx",
        data_dir / "mt5_direct_diagnostic_report.xlsx",
    ]
    for c in candidates:
        if c.exists():
            return c
    xlsx = list(data_dir.glob("*.xlsx"))
    return xlsx[0] if xlsx else None


def get_metric(summary_df: pd.DataFrame, key: str, default=None):
    if summary_df.empty:
        return default
    if "Metric" not in summary_df.columns or "Value" not in summary_df.columns:
        return default
    row = summary_df[summary_df["Metric"].astype(str) == key]
    if row.empty:
        return default
    return row["Value"].iloc[0]


def score_color(score):
    try:
        score = float(score)
    except Exception:
        return "gray"

    if score >= 80:
        return "green"
    if score >= 65:
        return "blue"
    if score >= 50:
        return "orange"
    return "red"


def make_gauge(title, value):
    try:
        value = float(value)
    except Exception:
        value = 0

    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=value,
        title={"text": title},
        gauge={
            "axis": {"range": [0, 100]},
            "bar": {"color": "#0f172a"},
            "steps": [
                {"range": [0, 35], "color": "#fee2e2"},
                {"range": [35, 50], "color": "#ffedd5"},
                {"range": [50, 65], "color": "#fef3c7"},
                {"range": [65, 80], "color": "#dbeafe"},
                {"range": [80, 100], "color": "#dcfce7"},
            ],
        }
    ))
    fig.update_layout(height=280, margin=dict(l=20, r=20, t=50, b=20))
    return fig


def show_metric_card(label, value, note=""):
    st.markdown(
        f"""
        <div class="metric-card">
            <div style="font-size:14px;color:#64748b;font-weight:700;">{label}</div>
            <div style="font-size:28px;color:#0f172a;font-weight:900;margin-top:4px;">{value}</div>
            <div style="font-size:13px;color:#94a3b8;margin-top:3px;">{note}</div>
        </div>
        """,
        unsafe_allow_html=True
    )


def severity_badge(sev: str):
    sev = str(sev)
    if sev.lower() == "high" or sev.lower() == "critical":
        return f'<span class="badge-high">{sev}</span>'
    if sev.lower() == "medium":
        return f'<span class="badge-medium">{sev}</span>'
    return f'<span class="badge-low">{sev}</span>'


# =========================
# Load Data
# =========================

args = parse_args()
data_dir = Path(args.data_dir)
excel_path = find_excel(data_dir)

st.markdown('<p class="big-title">📊 MT5 Trading Diagnostic Dashboard</p>', unsafe_allow_html=True)
st.markdown('<p class="subtitle">تحويل سجل التداول إلى تشخيص واضح: أداء، سلوك، مخاطرة، وخطة تعديل.</p>', unsafe_allow_html=True)

with st.sidebar:
    st.header("⚙️ Data Source")
    data_dir_input = st.text_input("Results folder", value=str(data_dir))
    if data_dir_input != str(data_dir):
        st.info("اضغط Enter ثم أعد تحديث الصفحة إذا غيرت المسار.")
        data_dir = Path(data_dir_input)
        excel_path = find_excel(data_dir)

    st.caption("المجلد المتوقع غالباً:")
    st.code(str(DEFAULT_DATA_DIR))

    st.divider()
    st.caption("شغّل سكربت V2 أولاً ثم افتح هذا الداشبورد.")

if not data_dir.exists():
    st.error(f"لم أجد مجلد البيانات: {data_dir}")
    st.stop()

if excel_path is None:
    st.error("لم أجد ملف Excel داخل مجلد النتائج. تأكد أنك شغلت سكربت V2 أولاً.")
    st.stop()

summary_df = load_excel_sheet(str(excel_path), "Summary")
scores_df = load_excel_sheet(str(excel_path), "Scores")
diagnosis_df = load_excel_sheet(str(excel_path), "Client Diagnosis")
action_plan_df = load_excel_sheet(str(excel_path), "Action Plan")
flags_df = load_excel_sheet(str(excel_path), "Behavior Flags")
account_df = load_excel_sheet(str(excel_path), "Account Info")
position_df = load_excel_sheet(str(excel_path), "Position Summary")
trade_deals_df = load_excel_sheet(str(excel_path), "Trade Deals")
by_symbol_df = load_excel_sheet(str(excel_path), "by_symbol")
by_hour_df = load_excel_sheet(str(excel_path), "by_hour")
by_weekday_df = load_excel_sheet(str(excel_path), "by_weekday")
by_side_df = load_excel_sheet(str(excel_path), "by_side")

analysis_df = position_df if not position_df.empty else trade_deals_df


# =========================
# Header Summary
# =========================

total_trades = get_metric(summary_df, "total_trades", 0)
net_profit = get_metric(summary_df, "net_profit", 0)
win_rate = get_metric(summary_df, "win_rate", 0)
profit_factor = get_metric(summary_df, "profit_factor", 0)
expectancy = get_metric(summary_df, "expectancy", 0)
max_drawdown = get_metric(summary_df, "max_drawdown", 0)
max_loss_streak = get_metric(summary_df, "max_loss_streak", 0)
avg_win = get_metric(summary_df, "avg_win", 0)
avg_loss = get_metric(summary_df, "avg_loss", 0)

st.write("")

col1, col2, col3, col4 = st.columns(4)
with col1:
    show_metric_card("Net Profit", net_profit, "صافي الربح/الخسارة")
with col2:
    show_metric_card("Win Rate", f"{win_rate}%", "نسبة الصفقات الرابحة")
with col3:
    show_metric_card("Profit Factor", profit_factor, "جودة الربح مقابل الخسارة")
with col4:
    show_metric_card("Total Trades", total_trades, "عدد الصفقات المحللة")

st.write("")

col5, col6, col7, col8 = st.columns(4)
with col5:
    show_metric_card("Expectancy", expectancy, "متوسط العائد لكل صفقة")
with col6:
    show_metric_card("Max Drawdown", max_drawdown, "أكبر تراجع تقريبي")
with col7:
    show_metric_card("Avg Win", avg_win, "متوسط الصفقة الرابحة")
with col8:
    show_metric_card("Avg Loss", avg_loss, "متوسط الصفقة الخاسرة")


# =========================
# Scores
# =========================

st.write("")
st.subheader("🧠 Diagnostic Scores")

if not scores_df.empty:
    score_cols = st.columns(min(5, len(scores_df)))
    for i, (_, row) in enumerate(scores_df.iterrows()):
        with score_cols[i % len(score_cols)]:
            st.plotly_chart(make_gauge(row["score_name"], row["score"]), use_container_width=True)
else:
    st.warning("لا توجد صفحة Scores في ملف Excel.")


# =========================
# Client Diagnosis
# =========================

st.write("")
st.subheader("🩺 Client Diagnosis")

if not diagnosis_df.empty:
    for _, row in diagnosis_df.iterrows():
        section = row.get("section", "")
        content = row.get("content_ar", "")
        if "Main Problem" in str(section):
            st.markdown(f'<div class="warning-box"><b>{section}</b><br>{content}</div>', unsafe_allow_html=True)
        elif "Recommendation" in str(section):
            st.markdown(f'<div class="good-box"><b>{section}</b><br>{content}</div>', unsafe_allow_html=True)
        else:
            st.markdown(
                f"""
                <div class="section-card">
                    <b>{section}</b><br>
                    <span style="color:#334155;">{content}</span>
                </div>
                """,
                unsafe_allow_html=True
            )
else:
    st.info("لا يوجد تشخيص عميل. تأكد من تشغيل نسخة V2.")


# =========================
# Charts
# =========================

st.write("")
st.subheader("📈 Performance Charts")

if not analysis_df.empty and "equity_curve" in analysis_df.columns:
    x_col = "trade_number" if "trade_number" in analysis_df.columns else analysis_df.index
    fig_eq = px.line(
        analysis_df,
        x=x_col,
        y="equity_curve",
        markers=True,
        title="Equity Curve / منحنى الأداء"
    )
    fig_eq.update_layout(height=420)
    st.plotly_chart(fig_eq, use_container_width=True)
else:
    st.warning("لا توجد بيانات كافية لرسم منحنى الأداء.")

chart_col1, chart_col2 = st.columns(2)

with chart_col1:
    if not by_symbol_df.empty and "symbol" in by_symbol_df.columns:
        fig_symbol = px.bar(
            by_symbol_df.sort_values("net_profit"),
            x="symbol",
            y="net_profit",
            title="Net Profit by Symbol / صافي الربح حسب الرمز",
            text="net_profit",
        )
        fig_symbol.update_layout(height=420)
        st.plotly_chart(fig_symbol, use_container_width=True)
    else:
        st.info("لا توجد بيانات by_symbol.")

with chart_col2:
    if not by_hour_df.empty and "hour" in by_hour_df.columns:
        fig_hour = px.bar(
            by_hour_df.sort_values("hour"),
            x="hour",
            y="net_profit",
            title="Net Profit by Hour / صافي الربح حسب الساعة",
            text="net_profit",
        )
        fig_hour.update_layout(height=420)
        st.plotly_chart(fig_hour, use_container_width=True)
    else:
        st.info("لا توجد بيانات by_hour.")

chart_col3, chart_col4 = st.columns(2)

with chart_col3:
    if not by_weekday_df.empty and "weekday" in by_weekday_df.columns:
        fig_weekday = px.bar(
            by_weekday_df,
            x="weekday",
            y="net_profit",
            title="Net Profit by Weekday / صافي الربح حسب اليوم",
            text="net_profit",
        )
        fig_weekday.update_layout(height=420)
        st.plotly_chart(fig_weekday, use_container_width=True)
    else:
        st.info("لا توجد بيانات by_weekday.")

with chart_col4:
    if not by_side_df.empty:
        side_col = by_side_df.columns[0]
        fig_side = px.bar(
            by_side_df,
            x=side_col,
            y="net_profit",
            title="Net Profit by Side / صافي الربح حسب الاتجاه",
            text="net_profit",
        )
        fig_side.update_layout(height=420)
        st.plotly_chart(fig_side, use_container_width=True)
    else:
        st.info("لا توجد بيانات by_side.")


# =========================
# Behavior Flags
# =========================

st.write("")
st.subheader("🚩 Behavior Flags")

if not flags_df.empty:
    for _, row in flags_df.iterrows():
        sev = row.get("severity", "")
        typ = row.get("type", "")
        message = row.get("message", "")
        suggestion = row.get("suggestion", "")

        st.markdown(
            f"""
            <div class="section-card">
                {severity_badge(sev)}
                <span style="font-weight:800;color:#0f172a;margin-left:8px;">{typ}</span>
                <br><br>
                <span style="color:#334155;">{message}</span>
                <br>
                <span style="color:#64748b;"><b>Suggestion:</b> {suggestion}</span>
            </div>
            """,
            unsafe_allow_html=True
        )
else:
    st.success("لم يتم اكتشاف Flags سلوكية واضحة بالقواعد الحالية.")


# =========================
# Action Plan
# =========================

st.write("")
st.subheader("🗓️ 7-Day Correction Plan")

if not action_plan_df.empty:
    for _, row in action_plan_df.iterrows():
        st.markdown(
            f"""
            <div class="section-card">
                <b>{row.get('day', '')} — {row.get('focus', '')}</b><br><br>
                <span style="color:#334155;">{row.get('task', '')}</span><br>
                <span style="color:#64748b;"><b>قياس النجاح:</b> {row.get('success_measure', '')}</span>
            </div>
            """,
            unsafe_allow_html=True
        )

    custom_note = action_plan_df["custom_note"].iloc[0] if "custom_note" in action_plan_df.columns else ""
    if custom_note:
        st.info(custom_note)
else:
    st.info("لا توجد خطة تعديل. تأكد من تشغيل نسخة V2.")


# =========================
# Raw Tables
# =========================

st.write("")
with st.expander("📋 عرض الجداول الخام"):
    st.write("Summary")
    st.dataframe(summary_df, use_container_width=True)

    st.write("Scores")
    st.dataframe(scores_df, use_container_width=True)

    st.write("Behavior Flags")
    st.dataframe(flags_df, use_container_width=True)

    st.write("Position Summary")
    st.dataframe(position_df, use_container_width=True)

    st.write("Trade Deals")
    st.dataframe(trade_deals_df, use_container_width=True)


# =========================
# Download
# =========================

st.write("")
st.subheader("⬇️ Download Reports")

with open(excel_path, "rb") as f:
    st.download_button(
        label="Download Excel Report",
        data=f,
        file_name=excel_path.name,
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

txt_path = data_dir / "diagnostic_report_ar_v2.txt"
if txt_path.exists():
    with open(txt_path, "rb") as f:
        st.download_button(
            label="Download Arabic Text Report",
            data=f,
            file_name=txt_path.name,
            mime="text/plain",
        )

st.caption("تحذير: هذا الداشبورد تحليل بيانات وليس توصية تداول. التداول يحمل مخاطرة حقيقية والقرار النهائي مسؤولية المتداول.")
