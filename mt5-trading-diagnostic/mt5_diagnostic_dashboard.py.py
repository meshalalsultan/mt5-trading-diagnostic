# mt5_diagnostic_dashboard_v4_file_upload.py
# ------------------------------------------------------------
# MT5 Diagnostic Dashboard - V4 File Upload
#
# هذه النسخة لا تحتاج منصة MT5 ولا حساب العميل.
# العميل يرفع ملف CSV / HTML / XLS / XLSX
# والداشبورد يحلل الملف ويعرض نفس التشخيص والرسوم.
#
# التشغيل:
# python -m pip install -r requirements.txt
# streamlit run mt5_diagnostic_dashboard_v4_file_upload.py
# ------------------------------------------------------------

import tempfile
from pathlib import Path

import pandas as pd
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go

from mt5_file_analyzer import analyze_mt5_file


APP_DIR = Path(__file__).resolve().parent
DEFAULT_OUTPUT_DIR = APP_DIR / "mt5_file_output"


st.set_page_config(
    page_title="MT5 File Diagnostic Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)


CUSTOM_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Tajawal:wght@400;500;700;800;900&family=Cairo:wght@400;600;700;800;900&display=swap');

html, body, [class*="css"]  {
    font-family: 'Tajawal', 'Cairo', Tahoma, Arial, sans-serif !important;
}

body {
    color: #0f172a;
}

.stApp {
    background: radial-gradient(circle at top left, #e0f2fe 0%, transparent 32%),
                radial-gradient(circle at top right, #ede9fe 0%, transparent 30%),
                linear-gradient(180deg, #f8fbff 0%, #f4f7fb 45%, #eef3f9 100%);
}

.block-container {
    padding-top: 1.3rem;
    padding-bottom: 2rem;
    max-width: 1500px;
}

/* =========================
   Hero
   ========================= */
.hero-card {
    background: linear-gradient(135deg, #0f172a 0%, #172554 48%, #1e40af 100%);
    border-radius: 28px;
    padding: 30px 34px;
    color: white;
    box-shadow: 0 20px 48px rgba(15, 23, 42, 0.28);
    border: 1px solid rgba(255,255,255,0.10);
}

.hero-title {
    font-size: 44px;
    font-weight: 900;
    margin-bottom: 8px;
    line-height: 1.15;
    text-align: left;
    letter-spacing: -0.5px;
}

.hero-subtitle {
    font-size: 21px;
    font-weight: 600;
    color: #e2e8f0;
    margin-bottom: 0;
    line-height: 1.7;
    text-align: left;
}

/* =========================
   Pills
   ========================= */
.info-pill {
    display: inline-block;
    background: #ffffff;
    color: #0f172a;
    padding: 10px 16px;
    border-radius: 999px;
    font-size: 15px;
    font-weight: 700;
    margin: 8px 8px 0 0;
    border: 1px solid #dbeafe;
    box-shadow: 0 8px 18px rgba(15, 23, 42, 0.06);
}

/* =========================
   Typography
   ========================= */
.section-title {
    font-size: 32px;
    font-weight: 900;
    color: #0f172a;
    margin-top: 4px;
    margin-bottom: 14px;
    text-align: left;
}

.small-muted {
    color: #334155;
    font-size: 17px;
    font-weight: 500;
    line-height: 1.95;
    text-align: left;
}

.kpi-card {
    background: rgba(255,255,255,0.96);
    border: 1px solid rgba(226,232,240,0.9);
    border-radius: 22px;
    padding: 18px 22px;
    box-shadow: 0 14px 34px rgba(15, 23, 42, 0.06);
    min-height: 132px;
}

.kpi-label {
    color: #475569;
    font-size: 24px;
    font-weight: 800;
    margin-bottom: 10px;
}

.kpi-value {
    color: #0f172a;
    font-size: 36px;
    font-weight: 900;
    margin-top: 6px;
    margin-bottom: 8px;
    line-height: 1.2;
}

.kpi-note {
    color: #64748b;
    font-size: 15px;
    font-weight: 500;
}

.panel-card {
    background: rgba(255,255,255,0.96);
    border: 1px solid rgba(226,232,240,0.9);
    border-radius: 24px;
    padding: 22px;
    box-shadow: 0 14px 34px rgba(15, 23, 42, 0.06);
    margin-bottom: 16px;
}

.problem-card {
    background: linear-gradient(135deg, #fff7ed 0%, #fff1f2 100%);
    border: 1px solid #fed7aa;
    border-radius: 24px;
    padding: 22px;
    box-shadow: 0 12px 28px rgba(251, 146, 60, 0.11);
}

.recommendation-card {
    background: linear-gradient(135deg, #ecfdf5 0%, #eff6ff 100%);
    border: 1px solid #a7f3d0;
    border-radius: 24px;
    padding: 22px;
    box-shadow: 0 12px 28px rgba(16, 185, 129, 0.11);
}

.flag-card, .plan-card {
    background: rgba(255,255,255,0.97);
    border: 1px solid rgba(226,232,240,0.9);
    border-radius: 22px;
    padding: 20px;
    box-shadow: 0 12px 28px rgba(15, 23, 42, 0.055);
    margin-bottom: 14px;
}

.flag-type {
    font-weight: 900;
    color: #0f172a;
    font-size: 21px;
}

.flag-message {
    color: #1e293b;
    font-size: 17px;
    font-weight: 500;
    margin-top: 12px;
    line-height: 1.85;
    text-align: left;
}

.flag-suggestion {
    color: #475569;
    font-size: 16px;
    font-weight: 500;
    margin-top: 10px;
    line-height: 1.85;
    text-align: left;
}

.badge-high {
    background: #fee2e2;
    color: #991b1b;
    padding: 6px 12px;
    border-radius: 999px;
    font-size: 13px;
    font-weight: 900;
    display: inline-block;
}

.badge-medium {
    background: #fef3c7;
    color: #92400e;
    padding: 6px 12px;
    border-radius: 999px;
    font-size: 13px;
    font-weight: 900;
    display: inline-block;
}

.badge-low {
    background: #dcfce7;
    color: #166534;
    padding: 6px 12px;
    border-radius: 999px;
    font-size: 13px;
    font-weight: 900;
    display: inline-block;
}

.plan-day {
    color: #2563eb;
    font-weight: 900;
    font-size: 16px;
}

.plan-focus {
    color: #0f172a;
    font-weight: 900;
    font-size: 21px;
    margin-top: 4px;
    margin-bottom: 8px;
    text-align: left;
}

/* =========================
   Tabs
   ========================= */
.stTabs [data-baseweb="tab-list"] {
    gap: 8px;
}

.stTabs [data-baseweb="tab"] {
    background-color: rgba(255,255,255,0.82);
    border-radius: 14px;
    padding: 10px 20px;
    font-weight: 800;
    font-size: 18px;
    color: #0f172a;
    border: 1px solid #e5e7eb;
}

.stTabs [aria-selected="true"] {
    background: linear-gradient(135deg, #0f172a 0%, #1d4ed8 100%) !important;
    color: white !important;
}

/* =========================
   Sidebar
   ========================= */
[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #0f172a 0%, #172554 100%);
    border-right: 1px solid rgba(255,255,255,0.08);
}

[data-testid="stSidebar"] h1,
[data-testid="stSidebar"] h2,
[data-testid="stSidebar"] h3,
[data-testid="stSidebar"] label,
[data-testid="stSidebar"] .stMarkdown,
[data-testid="stSidebar"] p,
[data-testid="stSidebar"] span,
[data-testid="stSidebar"] div[data-testid="stCaptionContainer"] {
    color: #f8fafc !important;
}

[data-testid="stSidebar"] .stTextInput input,
[data-testid="stSidebar"] .stNumberInput input,
[data-testid="stSidebar"] textarea {
    color: #0f172a !important;
    background: #ffffff !important;
    border-radius: 12px !important;
}

[data-testid="stSidebar"] .stFileUploader {
    background: rgba(255,255,255,0.06);
    border-radius: 16px;
    padding: 8px;
}

[data-testid="stSidebar"] .stFileUploader section {
    background: rgba(255,255,255,0.08) !important;
    border: 1px dashed rgba(255,255,255,0.18) !important;
    border-radius: 16px !important;
}

[data-testid="stSidebar"] .stFileUploader section * {
    color: #f8fafc !important;
}

[data-testid="stSidebar"] .stButton button,
[data-testid="stSidebar"] .stDownloadButton button {
    background: #ffffff !important;
    color: #0f172a !important;
    border: none !important;
    border-radius: 14px !important;
    font-weight: 900 !important;
    font-size: 16px !important;
    padding: 0.70rem 1rem !important;
    box-shadow: 0 10px 20px rgba(15,23,42,0.15);
}

[data-testid="stSidebar"] .stButton button:hover,
[data-testid="stSidebar"] .stDownloadButton button:hover {
    background: #e2e8f0 !important;
    color: #0f172a !important;
}

[data-testid="stSidebar"] .stButton button:disabled {
    background: rgba(255,255,255,0.35) !important;
    color: rgba(15,23,42,0.45) !important;
}

[data-testid="stSidebar"] code {
    color: #0f172a !important;
    background: #e2e8f0 !important;
    border-radius: 10px;
}

/* =========================
   General Buttons
   ========================= */
div[data-testid="stButton"] button,
div[data-testid="stDownloadButton"] button {
    border-radius: 14px;
    font-weight: 900;
    font-size: 16px;
}

/* =========================
   DataFrames / Text
   ========================= */
.stDataFrame, .stTable {
    font-size: 15px !important;
}

hr {
    margin-top: 8px;
    margin-bottom: 18px;
}
</style>
"""

st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


# =========================
# Helpers
# =========================

@st.cache_data(show_spinner=False)
def load_excel_sheet(excel_path: str, sheet_name: str) -> pd.DataFrame:
    p = Path(excel_path)
    if not p.exists():
        return pd.DataFrame()
    try:
        return pd.read_excel(p, sheet_name=sheet_name)
    except Exception:
        return pd.DataFrame()


def clear_cache():
    try:
        st.cache_data.clear()
    except Exception:
        pass


def find_excel(data_dir: Path):
    candidates = [
        data_dir / "mt5_file_diagnostic_report_v2.xlsx",
        data_dir / "mt5_direct_diagnostic_report_v2.xlsx",
        data_dir / "mt5_direct_diagnostic_report.xlsx",
    ]
    for c in candidates:
        if c.exists():
            return c
    xlsx_files = list(data_dir.glob("*.xlsx"))
    return xlsx_files[0] if xlsx_files else None


def get_metric(summary_df: pd.DataFrame, key: str, default=None):
    if summary_df.empty:
        return default
    if "Metric" not in summary_df.columns or "Value" not in summary_df.columns:
        return default
    row = summary_df[summary_df["Metric"].astype(str) == key]
    if row.empty:
        return default
    return row["Value"].iloc[0]


def safe_float(x, default=0.0):
    try:
        return float(x)
    except Exception:
        return default


def format_money(x):
    try:
        return f"${float(x):,.2f}"
    except Exception:
        return str(x)


def format_number(x):
    try:
        x = float(x)
        if x.is_integer():
            return f"{int(x)}"
        return f"{x:,.2f}"
    except Exception:
        return str(x)


def severity_badge(sev: str):
    sev_text = str(sev)
    sev_lower = sev_text.lower()
    if sev_lower in ["high", "critical"]:
        return f'<span class="badge-high">{sev_text}</span>'
    if sev_lower == "medium":
        return f'<span class="badge-medium">{sev_text}</span>'
    return f'<span class="badge-low">{sev_text}</span>'


def show_kpi_card(label, value, note=""):
    st.markdown(
        f"""
        <div class="kpi-card">
            <div class="kpi-label">{label}</div>
            <div class="kpi-value">{value}</div>
            <div class="kpi-note">{note}</div>
        </div>
        """,
        unsafe_allow_html=True
    )


def make_gauge(title, value):
    value = safe_float(value, 0)
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=value,
        number={"font": {"size": 34, "family": "Tajawal, Cairo, Tahoma, Arial"}},
        title={"text": title, "font": {"size": 18, "family": "Tajawal, Cairo, Tahoma, Arial"}},
        gauge={
            "axis": {"range": [0, 100], "tickwidth": 1},
            "bar": {"color": "#1d4ed8"},
            "bgcolor": "white",
            "borderwidth": 0,
            "steps": [
                {"range": [0, 35], "color": "#fee2e2"},
                {"range": [35, 50], "color": "#ffedd5"},
                {"range": [50, 65], "color": "#fef3c7"},
                {"range": [65, 80], "color": "#dbeafe"},
                {"range": [80, 100], "color": "#dcfce7"},
            ],
        }
    ))
    fig.update_layout(
        height=290,
        margin=dict(l=10, r=10, t=60, b=10),
        paper_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Tajawal, Cairo, Tahoma, Arial", color="#0f172a")
    )
    return fig


def make_plot_layout(fig, title):
    fig.update_layout(
        title=dict(
            text=title,
            font=dict(size=22, family="Tajawal, Cairo, Tahoma, Arial", color="#0f172a")
        ),
        font=dict(family="Tajawal, Cairo, Tahoma, Arial", color="#334155", size=14),
        paper_bgcolor="rgba(255,255,255,0)",
        plot_bgcolor="rgba(255,255,255,0)",
        margin=dict(l=20, r=20, t=60, b=20),
        hoverlabel=dict(font=dict(family="Tajawal, Cairo, Tahoma, Arial", size=14)),
    )
    fig.update_xaxes(showgrid=False, zeroline=False)
    fig.update_yaxes(showgrid=True, gridcolor="rgba(148,163,184,0.18)", zeroline=False)
    return fig


# =========================
# Header
# =========================

st.markdown(
    """
    <div class="hero-card">
        <div class="hero-title">📊 MT5 File Diagnostic Dashboard</div>
        <div class="hero-subtitle">
            ارفع كشف العميل CSV / HTML / Excel، واحصل على تشخيص بصري احترافي بدون الحاجة إلى منصة العميل.
        </div>
    </div>
    """,
    unsafe_allow_html=True
)


# =========================
# Sidebar Upload
# =========================

with st.sidebar:
    st.header("📤 Upload Statement")

    uploaded_file = st.file_uploader(
        "ارفع كشف MT5",
        type=["csv", "html", "htm", "xlsx", "xls"],
        help="يدعم CSV / HTML / XLS / XLSX"
    )

    output_dir = st.text_input("مجلد المخرجات", value=str(DEFAULT_OUTPUT_DIR))

    analyze_clicked = st.button("🚀 Analyze Uploaded File", use_container_width=True)


if uploaded_file is not None and analyze_clicked:
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    suffix = Path(uploaded_file.name).suffix.lower()
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(uploaded_file.getvalue())
        tmp_path = Path(tmp.name)

    with st.spinner("جاري تحليل الملف وإنشاء التقرير..."):
        try:
            result = analyze_mt5_file(tmp_path, output_dir=out_dir)
            clear_cache()
            st.success("تم تحليل الملف بنجاح ✅")
            st.info(f"تم تحليل {result['clean_rows']} صفقة من أصل {result['raw_rows']} صف خام.")
            with st.expander("تفاصيل التحليل"):
                st.json(result)
        except Exception as e:
            st.error("فشل تحليل الملف ❌")
            st.exception(e)

data_dir = Path(output_dir)
excel_path = find_excel(data_dir)

if excel_path is None:
    st.info("ارفع ملف CSV أو HTML أو Excel من القائمة الجانبية ثم اضغط Analyze Uploaded File.")
    st.stop()


# =========================
# Load Data
# =========================

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
# Source Info
# =========================

source_info = {}
if not account_df.empty and "field" in account_df.columns and "value" in account_df.columns:
    source_info = dict(zip(account_df["field"], account_df["value"]))

source_file = str(source_info.get("source_file", "-"))
raw_rows = str(source_info.get("total_rows_raw", "-"))
clean_rows = str(source_info.get("total_rows_clean", "-"))

st.markdown(
    f"""
    <div style="margin-top:16px; margin-bottom:12px;">
        <span class="info-pill">📄 File: {source_file}</span>
        <span class="info-pill">📦 Raw Rows: {raw_rows}</span>
        <span class="info-pill">✅ Clean Trades: {clean_rows}</span>
    </div>
    """,
    unsafe_allow_html=True
)


# =========================
# Metrics
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
best_trade = get_metric(summary_df, "best_trade", 0)
worst_trade = get_metric(summary_df, "worst_trade", 0)

st.write("")

k1, k2, k3, k4 = st.columns(4)
with k1:
    show_kpi_card("Net Profit", format_money(net_profit), "صافي الربح / الخسارة")
with k2:
    show_kpi_card("Win Rate", f"{format_number(win_rate)}%", "نسبة الصفقات الرابحة")
with k3:
    show_kpi_card("Profit Factor", format_number(profit_factor), "جودة الربح مقابل الخسارة")
with k4:
    show_kpi_card("Total Trades", format_number(total_trades), "عدد الصفقات المحللة")

st.write("")

k5, k6, k7, k8 = st.columns(4)
with k5:
    show_kpi_card("Expectancy", format_money(expectancy), "متوسط العائد لكل صفقة")
with k6:
    show_kpi_card("Max Drawdown", format_money(max_drawdown), "أكبر تراجع تقريبي")
with k7:
    show_kpi_card("Avg Win", format_money(avg_win), "متوسط الصفقة الرابحة")
with k8:
    show_kpi_card("Avg Loss", format_money(avg_loss), "متوسط الصفقة الخاسرة")


# =========================
# Tabs
# =========================

tab1, tab2, tab3, tab4 = st.tabs([
    "📌 Executive Overview",
    "🧠 Diagnosis & Behavior",
    "📈 Visual Analysis",
    "📋 Data Tables"
])


with tab1:
    st.markdown('<div class="section-title">النظرة التنفيذية</div>', unsafe_allow_html=True)

    left_col, right_col = st.columns([1.4, 1])

    with left_col:
        if not analysis_df.empty and "equity_curve" in analysis_df.columns:
            x_col = "trade_number" if "trade_number" in analysis_df.columns else analysis_df.index
            fig_eq = go.Figure()
            fig_eq.add_trace(go.Scatter(
                x=analysis_df[x_col],
                y=analysis_df["equity_curve"],
                mode="lines+markers",
                name="Equity Curve",
                line=dict(color="#1d4ed8", width=4, shape="spline"),
                marker=dict(size=7, color="#0f172a"),
                fill="tozeroy",
                fillcolor="rgba(29,78,216,0.12)",
                hovertemplate="Trade %{x}<br>Cumulative P/L: %{y:.2f}<extra></extra>"
            ))
            fig_eq = make_plot_layout(fig_eq, "منحنى الأداء التراكمي")
            fig_eq.update_layout(height=430)
            st.plotly_chart(fig_eq, use_container_width=True)
        else:
            st.info("لا توجد بيانات كافية لعرض منحنى الأداء.")

    with right_col:
        wins = safe_float(get_metric(summary_df, "wins", 0), 0)
        losses = safe_float(get_metric(summary_df, "losses", 0), 0)
        breakeven = safe_float(get_metric(summary_df, "breakeven", 0), 0)

        pie_df = pd.DataFrame({
            "result": ["Wins", "Losses", "Breakeven"],
            "count": [wins, losses, breakeven]
        })

        fig_pie = px.pie(
            pie_df,
            names="result",
            values="count",
            hole=0.62,
            color="result",
            color_discrete_map={"Wins": "#10b981", "Losses": "#ef4444", "Breakeven": "#f59e0b"}
        )
        fig_pie.update_traces(textposition="inside", textinfo="percent+label", marker=dict(line=dict(color="white", width=3)))
        fig_pie.update_layout(
            title="توزيع نتائج الصفقات",
            height=430,
            font=dict(family="Tajawal, Cairo, Tahoma, Arial", color="#0f172a", size=15),
            paper_bgcolor="rgba(0,0,0,0)",
            margin=dict(l=20, r=20, t=60, b=20),
            showlegend=True
        )
        st.plotly_chart(fig_pie, use_container_width=True)

    st.write("")

    score_map = {}
    if not scores_df.empty and "score_name" in scores_df.columns and "score" in scores_df.columns:
        for _, row in scores_df.iterrows():
            score_map[row["score_name"]] = row["score"]

    s_col1, s_col2, s_col3 = st.columns(3)
    with s_col1:
        st.plotly_chart(make_gauge("Overall Trading Health", score_map.get("Overall Trading Health Score", 0)), use_container_width=True)
    with s_col2:
        st.plotly_chart(make_gauge("Discipline Score", score_map.get("Discipline Score", 0)), use_container_width=True)
    with s_col3:
        st.plotly_chart(make_gauge("Risk Behavior Score", score_map.get("Risk Behavior Score", 0)), use_container_width=True)

    st.markdown(
        f"""
        <div class="panel-card">
            <div class="section-title" style="font-size:24px;">ملخص سريع</div>
            <div class="small-muted">
                الملف يحتوي على <b>{format_number(total_trades)}</b> صفقة محللة.
                صافي النتيجة <b>{format_money(net_profit)}</b>.
                أفضل صفقة <b>{format_money(best_trade)}</b>،
                وأسوأ صفقة <b>{format_money(worst_trade)}</b>.
                أطول سلسلة خسائر بلغت <b>{format_number(max_loss_streak)}</b>.
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )


with tab2:
    st.markdown('<div class="section-title">التشخيص والسلوك</div>', unsafe_allow_html=True)

    main_problem_text = ""
    root_cause_text = ""
    recommendation_text = ""
    executive_summary_text = ""
    confidence_text = ""

    if not diagnosis_df.empty:
        for _, row in diagnosis_df.iterrows():
            section = str(row.get("section", ""))
            content = str(row.get("content_ar", ""))
            if section == "Main Problem":
                main_problem_text = content
            elif section == "Root Cause Hypothesis":
                root_cause_text = content
            elif section == "Primary Recommendation":
                recommendation_text = content
            elif section == "Executive Summary":
                executive_summary_text = content
            elif section == "Data Confidence":
                confidence_text = content

    d1, d2 = st.columns([1.1, 1])

    with d1:
        st.markdown(
            f"""
            <div class="problem-card">
                <div class="section-title" style="font-size:24px;">المشكلة الرئيسية</div>
                <div class="small-muted" style="color:#7c2d12;">
                    {main_problem_text if main_problem_text else "لا توجد بيانات تشخيصية كافية."}
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )

        st.markdown(
            f"""
            <div class="panel-card">
                <div class="section-title" style="font-size:24px;">السبب المحتمل</div>
                <div class="small-muted">
                    {root_cause_text if root_cause_text else "لا توجد فرضية سبب حالياً."}
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )

    with d2:
        st.markdown(
            f"""
            <div class="recommendation-card">
                <div class="section-title" style="font-size:24px;">التوصية الأساسية</div>
                <div class="small-muted" style="color:#065f46;">
                    {recommendation_text if recommendation_text else "لا توجد توصية حالياً."}
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )

        st.markdown(
            f"""
            <div class="panel-card">
                <div class="section-title" style="font-size:24px;">الثقة في البيانات</div>
                <div class="small-muted">
                    {confidence_text if confidence_text else "لا توجد ملاحظة متعلقة بحجم العينة."}
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )

    st.markdown(
        f"""
        <div class="panel-card">
            <div class="section-title" style="font-size:24px;">الملخص التنفيذي</div>
            <div class="small-muted">
                {executive_summary_text if executive_summary_text else "لا يوجد ملخص تنفيذي."}
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

    st.markdown('<div class="section-title" style="font-size:28px;">الأعلام السلوكية المكتشفة</div>', unsafe_allow_html=True)

    if not flags_df.empty:
        for _, row in flags_df.iterrows():
            sev = row.get("severity", "")
            typ = row.get("type", "")
            message = row.get("message", "")
            suggestion = row.get("suggestion", "")

            st.markdown(
                f"""
                <div class="flag-card">
                    {severity_badge(sev)}
                    <span class="flag-type" style="margin-right:8px;">{typ}</span>
                    <div class="flag-message">{message}</div>
                    <div class="flag-suggestion"><b>التعديل المقترح:</b> {suggestion}</div>
                </div>
                """,
                unsafe_allow_html=True
            )
    else:
        st.success("لم يتم اكتشاف أخطاء سلوكية واضحة بالقواعد الحالية.")

    st.markdown('<div class="section-title" style="font-size:28px;">خطة التعديل - 7 أيام</div>', unsafe_allow_html=True)

    if not action_plan_df.empty:
        for _, row in action_plan_df.iterrows():
            st.markdown(
                f"""
                <div class="plan-card">
                    <div class="plan-day">{row.get('day', '')}</div>
                    <div class="plan-focus">{row.get('focus', '')}</div>
                    <div class="small-muted" style="margin-top:8px;">{row.get('task', '')}</div>
                    <div class="small-muted" style="margin-top:8px;"><b>قياس النجاح:</b> {row.get('success_measure', '')}</div>
                </div>
                """,
                unsafe_allow_html=True
            )

        if "custom_note" in action_plan_df.columns and not action_plan_df.empty:
            custom_note = str(action_plan_df["custom_note"].iloc[0])
            if custom_note:
                st.info(custom_note)
    else:
        st.info("لا توجد خطة تعديل متاحة حالياً.")


with tab3:
    st.markdown('<div class="section-title">التحليل البصري</div>', unsafe_allow_html=True)

    c1, c2 = st.columns(2)

    with c1:
        if not by_symbol_df.empty and "symbol" in by_symbol_df.columns:
            plot_df = by_symbol_df.sort_values("net_profit", ascending=True).copy()
            fig_symbol = px.bar(
                plot_df,
                x="net_profit",
                y="symbol",
                orientation="h",
                color="net_profit",
                color_continuous_scale=["#ef4444", "#f59e0b", "#10b981"],
                text="net_profit"
            )
            fig_symbol.update_traces(texttemplate="%{text:.2f}", textposition="outside")
            fig_symbol = make_plot_layout(fig_symbol, "صافي الربح حسب الرمز")
            fig_symbol.update_layout(height=430, coloraxis_showscale=False)
            st.plotly_chart(fig_symbol, use_container_width=True)
        else:
            st.info("لا توجد بيانات by_symbol.")

    with c2:
        if not by_hour_df.empty and "hour" in by_hour_df.columns:
            plot_df = by_hour_df.sort_values("hour").copy()
            fig_hour = go.Figure()
            fig_hour.add_trace(go.Bar(
                x=plot_df["hour"],
                y=plot_df["net_profit"],
                name="Net Profit",
                marker=dict(
                    color=plot_df["net_profit"],
                    colorscale=[[0.0, "#ef4444"], [0.5, "#f59e0b"], [1.0, "#10b981"]],
                    showscale=False
                ),
                text=plot_df["net_profit"],
                texttemplate="%{text:.2f}",
                textposition="outside"
            ))
            fig_hour = make_plot_layout(fig_hour, "صافي الربح حسب الساعة")
            fig_hour.update_layout(height=430)
            st.plotly_chart(fig_hour, use_container_width=True)
        else:
            st.info("لا توجد بيانات by_hour.")

    c3, c4 = st.columns(2)

    with c3:
        if not by_weekday_df.empty and "weekday" in by_weekday_df.columns:
            fig_weekday = px.bar(
                by_weekday_df,
                x="weekday",
                y="net_profit",
                color="net_profit",
                color_continuous_scale=["#ef4444", "#f59e0b", "#10b981"],
                text="net_profit"
            )
            fig_weekday.update_traces(texttemplate="%{text:.2f}", textposition="outside")
            fig_weekday = make_plot_layout(fig_weekday, "صافي الربح حسب اليوم")
            fig_weekday.update_layout(height=430, coloraxis_showscale=False)
            st.plotly_chart(fig_weekday, use_container_width=True)
        else:
            st.info("لا توجد بيانات by_weekday.")

    with c4:
        if not by_side_df.empty:
            side_col = by_side_df.columns[0]
            fig_side = px.bar(
                by_side_df,
                x=side_col,
                y="net_profit",
                color="net_profit",
                color_continuous_scale=["#ef4444", "#f59e0b", "#10b981"],
                text="net_profit"
            )
            fig_side.update_traces(texttemplate="%{text:.2f}", textposition="outside")
            fig_side = make_plot_layout(fig_side, "صافي الربح حسب اتجاه الصفقة")
            fig_side.update_layout(height=430, coloraxis_showscale=False)
            st.plotly_chart(fig_side, use_container_width=True)
        else:
            st.info("لا توجد بيانات by_side.")

    if not analysis_df.empty and "hour" in analysis_df.columns and "weekday" in analysis_df.columns and "net_profit" in analysis_df.columns:
        try:
            heat_df = analysis_df.copy()
            weekday_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
            heat_df["weekday"] = pd.Categorical(heat_df["weekday"], categories=weekday_order, ordered=True)

            pivot = pd.pivot_table(
                heat_df,
                index="weekday",
                columns="hour",
                values="net_profit",
                aggfunc="sum",
                fill_value=0
            )

            if not pivot.empty:
                fig_heat = go.Figure(data=go.Heatmap(
                    z=pivot.values,
                    x=[str(c) for c in pivot.columns],
                    y=[str(i) for i in pivot.index],
                    colorscale=[
                        [0.0, "#7f1d1d"],
                        [0.35, "#ef4444"],
                        [0.50, "#f8fafc"],
                        [0.70, "#86efac"],
                        [1.0, "#166534"]
                    ],
                    colorbar=dict(title="Net Profit"),
                    hovertemplate="Day: %{y}<br>Hour: %{x}<br>Net Profit: %{z:.2f}<extra></extra>"
                ))
                fig_heat = make_plot_layout(fig_heat, "خريطة حرارية: الربح حسب اليوم والساعة")
                fig_heat.update_layout(height=480)
                st.plotly_chart(fig_heat, use_container_width=True)
        except Exception:
            st.info("تعذر إنشاء الخريطة الحرارية من البيانات الحالية.")


with tab4:
    st.markdown('<div class="section-title">الجداول التفصيلية</div>', unsafe_allow_html=True)

    subtab1, subtab2, subtab3, subtab4 = st.tabs(["Summary", "Scores & Flags", "Trades", "Insights"])

    with subtab1:
        st.dataframe(summary_df, use_container_width=True)

    with subtab2:
        st.markdown("### Scores")
        st.dataframe(scores_df, use_container_width=True)
        st.markdown("### Behavior Flags")
        st.dataframe(flags_df, use_container_width=True)

    with subtab3:
        st.markdown("### Position Summary")
        st.dataframe(position_df, use_container_width=True)
        st.markdown("### Trade Deals")
        st.dataframe(trade_deals_df, use_container_width=True)

    with subtab4:
        if not by_symbol_df.empty:
            st.markdown("### by_symbol")
            st.dataframe(by_symbol_df, use_container_width=True)
        if not by_hour_df.empty:
            st.markdown("### by_hour")
            st.dataframe(by_hour_df, use_container_width=True)
        if not by_weekday_df.empty:
            st.markdown("### by_weekday")
            st.dataframe(by_weekday_df, use_container_width=True)
        if not by_side_df.empty:
            st.markdown("### by_side")
            st.dataframe(by_side_df, use_container_width=True)


# Downloads
st.write("")
st.markdown('<div class="section-title">تنزيل التقارير</div>', unsafe_allow_html=True)

dl1, dl2 = st.columns(2)

with dl1:
    with open(excel_path, "rb") as f:
        st.download_button(
            label="⬇️ Download Excel Report",
            data=f,
            file_name=excel_path.name,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )

with dl2:
    txt_path = data_dir / "diagnostic_report_ar_v2.txt"
    if txt_path.exists():
        with open(txt_path, "rb") as f:
            st.download_button(
                label="⬇️ Download Arabic Text Report",
                data=f,
                file_name=txt_path.name,
                mime="text/plain",
                use_container_width=True
            )

st.caption("تحذير: هذا الداشبورد مخصص لتحليل البيانات وليس لتقديم توصيات تداول. التداول يحمل مخاطرة حقيقية والقرار النهائي مسؤولية المتداول.")