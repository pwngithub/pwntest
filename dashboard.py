# dashboard_ceo_board.py — EXECUTIVE DASHBOARD FOR CEO/BOARD
import streamlit as st
import pandas as pd
import requests
import plotly.express as px
import plotly.graph_objects as go
from datetime import timedelta, datetime
from io import BytesIO
import numpy as np

st.set_page_config(page_title="Talley Executive Dashboard", layout="wide", initial_sidebar_state="collapsed")

# Enhanced Professional Styling
st.markdown("""
<style>
    .main-title {
        font-size: 48px !important; 
        font-weight: 700; 
        color: #1E3A8A; 
        text-align: center;
        margin-bottom: 10px;
    }
    .subtitle {
        text-align: center; 
        color: #64748B; 
        font-size: 16px;
        margin-bottom: 30px;
    }
    
    /* Executive KPI Cards */
    .kpi-card {
        background: linear-gradient(135deg, #1E293B 0%, #334155 100%);
        padding: 24px;
        border-radius: 16px;
        box-shadow: 0 8px 32px rgba(0,0,0,0.3);
        border-left: 6px solid;
        height: 180px;
        display: flex;
        flex-direction: column;
        justify-content: space-between;
    }
    .kpi-title {
        color: #94A3B8;
        font-size: 14px;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    .kpi-value {
        color: white;
        font-size: 42px;
        font-weight: 700;
        line-height: 1;
        margin: 12px 0;
    }
    .kpi-change {
        font-size: 16px;
        font-weight: 600;
    }
    
    /* Color variants */
    .growth {border-left-color: #10B981;}
    .revenue {border-left-color: #3B82F6;}
    .churn {border-left-color: #EF4444;}
    .customers {border-left-color: #8B5CF6;}
    
    .positive {color: #10B981 !important;}
    .negative {color: #EF4444 !important;}
    .neutral {color: #94A3B8 !important;}
    
    /* Hero Metric */
    .hero-metric {
        background: linear-gradient(135deg, #1E3A8A 0%, #3B82F6 100%);
        padding: 40px;
        border-radius: 20px;
        text-align: center;
        box-shadow: 0 12px 48px rgba(59, 130, 246, 0.3);
        margin: 20px 0;
    }
    .hero-label {
        color: #BFDBFE;
        font-size: 18px;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 1px;
    }
    .hero-value {
        color: white;
        font-size: 72px;
        font-weight: 800;
        margin: 16px 0;
        text-shadow: 0 4px 12px rgba(0,0,0,0.3);
    }
    
    /* Strategic Insights Box */
    .insight-box {
        background: #FEF3C7;
        border-left: 6px solid #F59E0B;
        padding: 20px;
        border-radius: 12px;
        margin: 20px 0;
    }
    .insight-title {
        color: #92400E;
        font-weight: 700;
        font-size: 16px;
        margin-bottom: 8px;
    }
    .insight-text {
        color: #78350F;
        font-size: 14px;
        line-height: 1.6;
    }
    
    /* Alert Box */
    .alert-box {
        background: #FEE2E2;
        border-left: 6px solid #EF4444;
        padding: 20px;
        border-radius: 12px;
        margin: 20px 0;
    }
    .alert-title {
        color: #991B1B;
        font-weight: 700;
        font-size: 16px;
        margin-bottom: 8px;
    }
    
    .stApp {background: linear-gradient(to bottom, #0F172A 0%, #1E293B 100%);}
    
    /* Table styling */
    .dataframe {
        font-size: 13px !important;
    }
    
    /* Section headers */
    h2, h3 {
        color: #E2E8F0 !important;
        font-weight: 600 !important;
    }
</style>
""", unsafe_allow_html=True)

# ——————————————— DATA LOADER ———————————————
def load_from_jotform():
    api_key = "22179825a79dba61013e4fc3b9d30fa4"
    form_id = "240073839937062"
    url = f"https://api.jotform.com/form/{form_id}/submissions"
    submissions = []
    offset = 0
    limit = 1000
    while True:
        params = {"apiKey": api_key, "limit": limit, "offset": offset, "orderby": "created_at"}
        try:
            r = requests.get(url, params=params, timeout=30)
            r.raise_for_status()
            data = r.json()
            if not data.get("content"):
                break
            for item in data["content"]:
                row = {"Submission Date": item["created_at"], "Submission ID": item["id"]}
                for ans in item.get("answers", {}).values():
                    name = ans.get("name") or ans.get("text") or "unknown"
                    answer = ans.get("answer")
                    if isinstance(answer, dict):
                        parts = [
                            str(v) if not isinstance(v, list) else ", ".join(map(str, v))
                            for v in answer.values()
                        ]
                        answer = ", ".join(filter(None, parts))
                    elif isinstance(answer, list):
                        answer = ", ".join(map(str, answer))
                    elif answer is None or str(answer).strip() == "":
                        continue
                    row[name] = str(answer).strip()
                submissions.append(row)
            if len(data["content"]) < limit:
                break
            offset += limit
        except Exception as e:
            st.error(f"Error loading data: {e}")
            return pd.DataFrame()
    return pd.DataFrame(submissions)

@st.cache_data(ttl=300)
def get_data():
    df = load_from_jotform()
    if df.empty:
        return df

    rename_map = {
        "customerName": "Customer Name",
        "date": "Date",
        "employee": "Employee",
        "location": "Location",
        "status": "Status",
        "category": "Category",
        "reason": "Reason",
        "mrc": "MRC",
        "reasonOther": "Reason Other",
        "disconnectReason": "Disconnect Reason Detail",
    }
    df.rename(columns=rename_map, inplace=True)

    df["Submission Date"] = pd.to_datetime(df["Submission Date"], errors="coerce")
    df = df.dropna(subset=["Submission Date"]).copy()

    if "Status" not in df.columns:
        df["Status"] = ""
    df["Status"] = df["Status"].astype(str).str.upper().str.strip()

    if "MRC" not in df.columns:
        df["MRC"] = 0
    df["MRC"] = pd.to_numeric(df["MRC"], errors="coerce").fillna(0)

    if "Customer Name" not in df.columns:
        df["Customer Name"] = ""
    df["Customer Name"] = df["Customer Name"].astype(str).str.strip()

    for col in ["Category", "Reason", "Location"]:
        if col not in df.columns:
            df[col] = pd.NA

    return df

def add_category_at_disconnect(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return df
    work = df.copy()
    if "Category" not in work.columns:
        work["Category"] = pd.NA
    work["Category"] = work["Category"].astype(str).str.strip()
    work.loc[work["Category"].isin(["", "None", "nan", "NaN", "<NA>"]), "Category"] = pd.NA
    work = work.sort_values(["Customer Name", "Submission Date"], kind="mergesort")
    work["_last_known_category"] = work.groupby("Customer Name")["Category"].ffill()
    work["Category at Disconnect"] = work["_last_known_category"].fillna("Unknown")
    work.drop(columns=["_last_known_category"], inplace=True)
    return work

def calculate_trends(df: pd.DataFrame, period_days: int):
    """Calculate month-over-month trends for strategic insights"""
    if df.empty:
        return {}
    
    max_date = df["Submission Date"].max()
    current_start = max_date - timedelta(days=period_days)
    prior_start = current_start - timedelta(days=period_days)
    
    current = df[(df["Submission Date"] > current_start)]
    prior = df[(df["Submission Date"] > prior_start) & (df["Submission Date"] <= current_start)]
    
    curr_new = current[current["Status"] == "NEW"]
    curr_churn = current[current["Status"] == "DISCONNECT"]
    prior_new = prior[prior["Status"] == "NEW"]
    prior_churn = prior[prior["Status"] == "DISCONNECT"]
    
    trends = {
        "new_customers_change": ((len(curr_new) - len(prior_new)) / len(prior_new) * 100) if len(prior_new) > 0 else 0,
        "churn_customers_change": ((len(curr_churn) - len(prior_churn)) / len(prior_churn) * 100) if len(prior_churn) > 0 else 0,
        "new_mrc_change": ((curr_new["MRC"].sum() - prior_new["MRC"].sum()) / prior_new["MRC"].sum() * 100) if prior_new["MRC"].sum() > 0 else 0,
        "churn_mrc_change": ((curr_churn["MRC"].sum() - prior_churn["MRC"].sum()) / prior_churn["MRC"].sum() * 100) if prior_churn["MRC"].sum() > 0 else 0,
    }
    
    return trends

def generate_strategic_insights(metrics: dict, trends: dict, churn_in: pd.DataFrame):
    """Generate executive insights based on data"""
    insights = []
    alerts = []
    
    # Growth insights
    if metrics.get("net_customer_movement", 0) > 0:
        insights.append(f"✓ **Positive Net Growth**: Added {metrics['net_customer_movement']:,} net customers with ${metrics['net_mrr_movement']:,.0f} in MRR")
    else:
        alerts.append(f"⚠️ **Net Customer Loss**: Lost {abs(metrics['net_customer_movement']):,} net customers and ${abs(metrics['net_mrr_movement']):,.0f} in MRR")
    
    # Churn rate analysis
    churn_rate = metrics.get("churn_rate", 0)
    if churn_rate > 5:
        alerts.append(f"⚠️ **High Churn Alert**: {churn_rate:.1f}% churn rate exceeds healthy threshold (target: <3%)")
    elif churn_rate < 2:
        insights.append(f"✓ **Excellent Retention**: {churn_rate:.1f}% churn rate demonstrates strong customer satisfaction")
    
    # Trend analysis
    if trends.get("new_customers_change", 0) > 10:
        insights.append(f"✓ **Accelerating Growth**: New customer acquisition up {trends['new_customers_change']:.1f}% vs prior period")
    elif trends.get("new_customers_change", 0) < -10:
        alerts.append(f"⚠️ **Slowing Acquisition**: New customer growth down {abs(trends['new_customers_change']):.1f}% vs prior period")
    
    # Competitive analysis
    if not churn_in.empty:
        competitor_losses = churn_in[churn_in["Reason"].astype(str).str.contains("New Provider", case=False, na=False)]
        if len(competitor_losses) > 0:
            pct_to_competitors = (len(competitor_losses) / len(churn_in) * 100)
            if pct_to_competitors > 40:
                alerts.append(f"⚠️ **Competitive Pressure**: {pct_to_competitors:.0f}% of churn to competitors - review pricing & value prop")
    
    # Revenue concentration
    if metrics.get("avg_customer_value", 0) > 0:
        if metrics["new_mrc"] / metrics["new_count"] > metrics["avg_customer_value"] * 1.2:
            insights.append("✓ **Premium Customer Acquisition**: New customers have 20%+ higher average value")
    
    return insights, alerts

def build_monthly_trend(df: pd.DataFrame, months: int = 12):
    """Build monthly trend data for visualization"""
    if df.empty:
        return pd.DataFrame()
    
    max_date = df["Submission Date"].max()
    min_date = max_date - timedelta(days=months*30)
    
    trend_df = df[df["Submission Date"] >= min_date].copy()
    trend_df["Month"] = trend_df["Submission Date"].dt.to_period("M")
    
    monthly = trend_df.groupby(["Month", "Status"]).agg({
        "Customer Name": "nunique",
        "MRC": "sum"
    }).reset_index()
    
    monthly["Month"] = monthly["Month"].dt.to_timestamp()
    
    return monthly

def run_dashboard():
    # ==================== HEADER ====================
    col_logo, col_title = st.columns([1, 8])
    with col_logo:
        st.image("https://via.placeholder.com/160x100/1E3A8A/FFFFFF?text=TALLEY", width=160)
    with col_title:
        st.markdown('<p class="main-title">Executive Dashboard</p>', unsafe_allow_html=True)
        st.markdown('<p class="subtitle">Strategic Performance Metrics • Customer Growth • Competitive Intelligence</p>', unsafe_allow_html=True)

    # ==================== DATA LOADING ====================
    df = get_data()
    if df.empty:
        st.error("⚠️ Unable to load data. Please check connection.")
        st.stop()

    df = add_category_at_disconnect(df)

    # ==================== DATE SELECTOR ====================
    min_date = df["Submission Date"].min().date()
    max_date = df["Submission Date"].max().date()
    default_start = max_date - timedelta(days=89)

    col1, col2, col3 = st.columns([3, 1, 1])
    with col1:
        start_date, end_date = st.date_input(
            "📅 Reporting Period",
            value=(default_start, max_date),
            min_value=min_date,
            max_value=max_date,
        )
    with col2:
        comparison_period = st.selectbox("Compare to", ["Prior Period", "Prior Quarter", "Prior Year"], index=0)
    with col3:
        if st.button("🔄 Refresh Data"):
            st.cache_data.clear()
            st.rerun()

    # ==================== CALCULATIONS ====================
    period_start = pd.Timestamp(start_date)
    period_end = pd.Timestamp(end_date)
    period_days = (end_date - start_date).days + 1
    period_df = df[(df["Submission Date"].dt.date >= start_date) & (df["Submission Date"].dt.date <= end_date)].copy()

    # Beginning balances
    new_before = df[(df["Status"] == "NEW") & (df["Submission Date"] <= period_start)]
    disc_before = df[(df["Status"] == "DISCONNECT") & (df["Submission Date"] <= period_start)]
    active_start = set(new_before["Customer Name"]) - set(disc_before["Customer Name"])
    beginning_customers = len(active_start)
    beginning_mrc = new_before[new_before["Customer Name"].isin(active_start)]["MRC"].sum()

    # Period activity
    new_in = period_df[period_df["Status"] == "NEW"]
    churn_in = period_df[period_df["Status"] == "DISCONNECT"]

    new_count = new_in["Customer Name"].nunique()
    new_mrc = new_in["MRC"].sum()
    churn_count = churn_in["Customer Name"].nunique()
    churn_mrc = churn_in["MRC"].sum()

    net_customer_movement = new_count - churn_count
    net_mrr_movement = new_mrc - churn_mrc

    # Ending balances
    ending_customers = beginning_customers + net_customer_movement
    ending_mrc = beginning_mrc + net_mrr_movement

    # Rates & metrics
    churn_rate = (churn_count / beginning_customers * 100) if beginning_customers > 0 else 0
    growth_rate = (new_count / beginning_customers * 100) if beginning_customers > 0 else 0
    net_growth_rate = ((ending_customers - beginning_customers) / beginning_customers * 100) if beginning_customers > 0 else 0
    
    avg_customer_value = ending_mrc / ending_customers if ending_customers > 0 else 0
    ltv_estimate = avg_customer_value * 36  # 3-year LTV estimate
    
    # Calculate trends
    trends = calculate_trends(df, period_days)
    
    # Compile metrics for insights
    metrics = {
        "net_customer_movement": net_customer_movement,
        "net_mrr_movement": net_mrr_movement,
        "churn_rate": churn_rate,
        "new_count": new_count,
        "new_mrc": new_mrc,
        "avg_customer_value": avg_customer_value,
    }
    
    # Generate insights
    insights, alerts = generate_strategic_insights(metrics, trends, churn_in)

    # ==================== HERO METRIC ====================
    mrr_color = "#10B981" if net_mrr_movement >= 0 else "#EF4444"
    mrr_sign = "+" if net_mrr_movement >= 0 else ""
    
    st.markdown(
        f"""
        <div class="hero-metric">
            <p class="hero-label">Net MRR Movement</p>
            <p class="hero-value" style="color: {mrr_color};">{mrr_sign}${net_mrr_movement:,.0f}</p>
            <p style="color: #BFDBFE; font-size: 20px; font-weight: 600;">
                {mrr_sign}{net_customer_movement:,} Net Customers • 
                Period: {start_date.strftime('%b %d')} - {end_date.strftime('%b %d, %Y')}
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ==================== EXECUTIVE KPI CARDS ====================
    st.markdown("### 📊 Key Performance Indicators")
    
    kpi1, kpi2, kpi3, kpi4 = st.columns(4)
    
    with kpi1:
        trend_new = trends.get("new_customers_change", 0)
        trend_color = "positive" if trend_new >= 0 else "negative"
        st.markdown(
            f"""
            <div class="kpi-card growth">
                <div class="kpi-title">New Customers</div>
                <div class="kpi-value">{new_count:,}</div>
                <div class="kpi-change {trend_color}">
                    {'↑' if trend_new >= 0 else '↓'} {abs(trend_new):.1f}% vs prior
                    <br><span style="color: #10B981; font-size: 14px;">+${new_mrc:,.0f} MRR</span>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    
    with kpi2:
        trend_churn = trends.get("churn_customers_change", 0)
        trend_color = "negative" if trend_churn >= 0 else "positive"
        st.markdown(
            f"""
            <div class="kpi-card churn">
                <div class="kpi-title">Churned Customers</div>
                <div class="kpi-value">{churn_count:,}</div>
                <div class="kpi-change {trend_color}">
                    {'↑' if trend_churn >= 0 else '↓'} {abs(trend_churn):.1f}% vs prior
                    <br><span style="color: #EF4444; font-size: 14px;">-${churn_mrc:,.0f} MRR</span>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    
    with kpi3:
        churn_health = "positive" if churn_rate < 3 else ("neutral" if churn_rate < 5 else "negative")
        st.markdown(
            f"""
            <div class="kpi-card revenue">
                <div class="kpi-title">Churn Rate</div>
                <div class="kpi-value">{churn_rate:.1f}%</div>
                <div class="kpi-change {churn_health}">
                    Target: <3.0%
                    <br><span style="color: #94A3B8; font-size: 14px;">Industry avg: 3-5%</span>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    
    with kpi4:
        growth_health = "positive" if net_growth_rate > 0 else "negative"
        st.markdown(
            f"""
            <div class="kpi-card customers">
                <div class="kpi-title">Net Growth Rate</div>
                <div class="kpi-value">{net_growth_rate:+.1f}%</div>
                <div class="kpi-change {growth_health}">
                    {ending_customers:,} total customers
                    <br><span style="color: #94A3B8; font-size: 14px;">Started: {beginning_customers:,}</span>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # ==================== STRATEGIC INSIGHTS & ALERTS ====================
    if alerts or insights:
        st.markdown("### 💡 Strategic Insights")
        
        col_insight, col_alert = st.columns(2)
        
        with col_insight:
            if insights:
                insight_html = "<div class='insight-box'><div class='insight-title'>🎯 Key Wins</div><div class='insight-text'>"
                for insight in insights:
                    insight_html += f"• {insight}<br>"
                insight_html += "</div></div>"
                st.markdown(insight_html, unsafe_allow_html=True)
        
        with col_alert:
            if alerts:
                alert_html = "<div class='alert-box'><div class='alert-title'>⚠️ Action Items</div><div class='insight-text' style='color: #991B1B;'>"
                for alert in alerts:
                    alert_html += f"• {alert}<br>"
                alert_html += "</div></div>"
                st.markdown(alert_html, unsafe_allow_html=True)

    st.divider()

    # ==================== FINANCIAL PERFORMANCE ====================
    st.markdown("### 💰 Revenue & Customer Metrics")
    
    fin1, fin2, fin3, fin4 = st.columns(4)
    
    with fin1:
        st.metric(
            "Total Active MRR",
            f"${ending_mrc:,.0f}",
            delta=f"${net_mrr_movement:,.0f}",
            delta_color="normal"
        )
    
    with fin2:
        st.metric(
            "Avg Customer Value",
            f"${avg_customer_value:,.0f}/mo",
            delta=None
        )
    
    with fin3:
        st.metric(
            "Est. LTV (3yr)",
            f"${ltv_estimate:,.0f}",
            delta=None
        )
    
    with fin4:
        annual_run_rate = ending_mrc * 12
        st.metric(
            "Annual Run Rate",
            f"${annual_run_rate:,.0f}",
            delta=f"${net_mrr_movement * 12:,.0f}"
        )

    st.divider()

    # ==================== TREND ANALYSIS ====================
    st.markdown("### 📈 12-Month Performance Trends")
    
    monthly_data = build_monthly_trend(df, months=12)
    
    if not monthly_data.empty:
        # Pivot for new vs churn comparison
        pivot_data = monthly_data.pivot_table(
            index="Month",
            columns="Status",
            values="Customer Name",
            fill_value=0
        ).reset_index()
        
        # Create dual-axis chart
        fig = go.Figure()
        
        if "NEW" in pivot_data.columns:
            fig.add_trace(go.Bar(
                x=pivot_data["Month"],
                y=pivot_data["NEW"],
                name="New Customers",
                marker_color="#10B981"
            ))
        
        if "DISCONNECT" in pivot_data.columns:
            fig.add_trace(go.Bar(
                x=pivot_data["Month"],
                y=pivot_data["DISCONNECT"],
                name="Churned Customers",
                marker_color="#EF4444"
            ))
        
        # Add net line
        if "NEW" in pivot_data.columns and "DISCONNECT" in pivot_data.columns:
            pivot_data["Net"] = pivot_data["NEW"] - pivot_data["DISCONNECT"]
            fig.add_trace(go.Scatter(
                x=pivot_data["Month"],
                y=pivot_data["Net"],
                name="Net Growth",
                mode="lines+markers",
                line=dict(color="#3B82F6", width=3),
                marker=dict(size=8)
            ))
        
        fig.update_layout(
            title="Customer Acquisition vs Churn (Monthly)",
            xaxis_title="Month",
            yaxis_title="Customers",
            hovermode="x unified",
            barmode="group",
            height=450,
            template="plotly_dark",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )
        
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Insufficient historical data for trend analysis")

    st.divider()

    # ==================== CHURN ANALYSIS ====================
    st.markdown("### 🔍 Churn Deep Dive")
    
    if not churn_in.empty:
        col_reason, col_category = st.columns(2)
        
        with col_reason:
            st.markdown("#### Top Churn Reasons")
            reason_df = (
                churn_in.groupby("Reason", dropna=False)
                .agg(Customers=("Customer Name", "nunique"), MRC_Lost=("MRC", "sum"))
                .reset_index()
                .sort_values("Customers", ascending=False)
                .head(10)
            )
            
            fig_reason = px.bar(
                reason_df,
                y="Reason",
                x="Customers",
                orientation="h",
                color="MRC_Lost",
                color_continuous_scale="Reds",
                text="Customers"
            )
            fig_reason.update_traces(textposition="outside")
            fig_reason.update_layout(height=400, showlegend=False, template="plotly_dark")
            st.plotly_chart(fig_reason, use_container_width=True)
        
        with col_category:
            st.markdown("#### Churn by Category")
            cat_df = (
                churn_in.groupby("Category at Disconnect", dropna=False)
                .agg(Customers=("Customer Name", "nunique"), MRC_Lost=("MRC", "sum"))
                .reset_index()
                .sort_values("Customers", ascending=False)
            )
            
            fig_cat = px.pie(
                cat_df,
                names="Category at Disconnect",
                values="Customers",
                color_discrete_sequence=px.colors.sequential.Reds_r,
                hole=0.4
            )
            fig_cat.update_traces(textposition="inside", textinfo="percent+label")
            fig_cat.update_layout(height=400, showlegend=False, template="plotly_dark")
            st.plotly_chart(fig_cat, use_container_width=True)
        
        # Detailed churn table
        st.markdown("#### Churned Customer Details")
        churn_detail = churn_in.sort_values("Submission Date", ascending=False).copy()
        churn_detail["Date"] = churn_detail["Submission Date"].dt.date
        
        display_cols = ["Date", "Customer Name", "Category at Disconnect", "Reason", "MRC", "Location"]
        available_cols = [c for c in display_cols if c in churn_detail.columns]
        
        st.dataframe(
            churn_detail[available_cols].head(20).style.format({"MRC": "${:,.0f}"}),
            use_container_width=True,
            hide_index=True
        )
        
        st.caption(f"Showing top 20 of {len(churn_detail):,} churned customers")
    
    else:
        st.success("✅ No customer churn in this period!")

    st.divider()

    # ==================== COMPETITIVE INTELLIGENCE ====================
    st.markdown("### 🎯 Competitive Analysis")
    
    if not churn_in.empty:
        competitors = {
            "Fidium": "New Provider Fidium",
            "Spectrum": "New Provider Spectrum",
            "Starlink": "New Provider Starlink",
            "CCI": "New Provider CCI",
            "GWI": "New Provider GWI",
            "Other": "New Provider Other",
        }
        
        comp_data = []
        for label, keyword in competitors.items():
            mask = churn_in["Reason"].astype(str).str.contains(keyword, case=False, na=False)
            count = int(mask.sum())
            mrc = churn_in.loc[mask, "MRC"].sum()
            if count > 0:
                comp_data.append({
                    "Competitor": label,
                    "Customers Lost": count,
                    "MRC Lost": mrc,
                    "Avg MRC": mrc / count if count > 0 else 0
                })
        
        if comp_data:
            comp_df = pd.DataFrame(comp_data).sort_values("Customers Lost", ascending=False)
            
            col_viz, col_table = st.columns([1.5, 1])
            
            with col_viz:
                fig_comp = px.bar(
                    comp_df,
                    x="Competitor",
                    y="Customers Lost",
                    color="MRC Lost",
                    color_continuous_scale="Reds",
                    text="Customers Lost"
                )
                fig_comp.update_traces(textposition="outside")
                fig_comp.update_layout(
                    title="Customers Lost by Competitor",
                    height=400,
                    template="plotly_dark"
                )
                st.plotly_chart(fig_comp, use_container_width=True)
            
            with col_table:
                st.markdown("#### Competitive Impact Summary")
                total_comp_customers = comp_df["Customers Lost"].sum()
                total_comp_mrc = comp_df["MRC Lost"].sum()
                pct_of_churn = (total_comp_customers / churn_count * 100) if churn_count > 0 else 0
                
                st.metric("Total Lost to Competitors", f"{total_comp_customers:,}", f"{pct_of_churn:.0f}% of all churn")
                st.metric("MRR Lost to Competitors", f"${total_comp_mrc:,.0f}")
                
                st.dataframe(
                    comp_df.style.format({
                        "MRC Lost": "${:,.0f}",
                        "Avg MRC": "${:,.0f}"
                    }),
                    use_container_width=True,
                    hide_index=True
                )
        else:
            st.success("✅ No customers lost to named competitors!")
    else:
        st.info("No churn data available for competitive analysis")

    st.divider()

    # ==================== CUSTOMER ACQUISITION ====================
    st.markdown("### 🚀 New Customer Acquisition")
    
    if not new_in.empty:
        acq1, acq2 = st.columns(2)
        
        with acq1:
            st.markdown("#### Acquisition by Category")
            cat_new = (
                new_in.groupby("Category", dropna=False)
                .agg(Customers=("Customer Name", "nunique"), MRC=("MRC", "sum"))
                .reset_index()
                .sort_values("Customers", ascending=False)
            )
            
            fig_new_cat = px.pie(
                cat_new,
                names="Category",
                values="Customers",
                color_discrete_sequence=px.colors.sequential.Greens_r,
                hole=0.4
            )
            fig_new_cat.update_traces(textposition="inside", textinfo="percent+label")
            fig_new_cat.update_layout(height=400, showlegend=False, template="plotly_dark")
            st.plotly_chart(fig_new_cat, use_container_width=True)
        
        with acq2:
            st.markdown("#### Top Acquisition Locations")
            loc_new = (
                new_in.groupby("Location", dropna=False)
                .agg(Customers=("Customer Name", "nunique"), MRC=("MRC", "sum"))
                .reset_index()
                .sort_values("Customers", ascending=False)
                .head(10)
            )
            
            fig_new_loc = px.bar(
                loc_new,
                y="Location",
                x="Customers",
                orientation="h",
                color="MRC",
                color_continuous_scale="Greens",
                text="Customers"
            )
            fig_new_loc.update_traces(textposition="outside")
            fig_new_loc.update_layout(height=400, showlegend=False, template="plotly_dark")
            st.plotly_chart(fig_new_loc, use_container_width=True)
    else:
        st.info("No new customers acquired in this period")

    st.divider()

    # ==================== EXECUTIVE SUMMARY FOR EXPORT ====================
    st.markdown("### 📄 Executive Report Export")
    
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        # Executive Summary
        summary_data = {
            "Metric": [
                "Reporting Period",
                "Beginning Customers",
                "Beginning MRR",
                "New Customers Added",
                "New MRR Added",
                "Customers Churned",
                "MRR Churned",
                "Net Customer Movement",
                "Net MRR Movement",
                "Ending Customers",
                "Ending MRR",
                "Churn Rate (%)",
                "Growth Rate (%)",
                "Net Growth Rate (%)",
                "Avg Customer Value",
                "Estimated LTV (3yr)",
                "Annual Run Rate"
            ],
            "Value": [
                f"{start_date} to {end_date}",
                beginning_customers,
                f"${beginning_mrc:,.2f}",
                new_count,
                f"${new_mrc:,.2f}",
                churn_count,
                f"${churn_mrc:,.2f}",
                net_customer_movement,
                f"${net_mrr_movement:,.2f}",
                ending_customers,
                f"${ending_mrc:,.2f}",
                f"{churn_rate:.2f}%",
                f"{growth_rate:.2f}%",
                f"{net_growth_rate:.2f}%",
                f"${avg_customer_value:,.2f}",
                f"${ltv_estimate:,.2f}",
                f"${annual_run_rate:,.2f}"
            ]
        }
        pd.DataFrame(summary_data).to_excel(writer, sheet_name="Executive Summary", index=False)
        
        # Strategic Insights
        if insights or alerts:
            insights_data = []
            for i, insight in enumerate(insights, 1):
                insights_data.append({"Type": "Insight", "Priority": "High", "Description": insight})
            for i, alert in enumerate(alerts, 1):
                insights_data.append({"Type": "Alert", "Priority": "Critical", "Description": alert})
            pd.DataFrame(insights_data).to_excel(writer, sheet_name="Strategic Insights", index=False)
        
        # Churn Details
        if not churn_in.empty:
            churn_export = churn_in.copy()
            churn_export["Date"] = churn_export["Submission Date"].dt.date
            export_cols = ["Date", "Customer Name", "Category at Disconnect", "Reason", "MRC", "Location"]
            available = [c for c in export_cols if c in churn_export.columns]
            churn_export[available].to_excel(writer, sheet_name="Churned Customers", index=False)
        
        # New Customers
        if not new_in.empty:
            new_export = new_in.copy()
            new_export["Date"] = new_export["Submission Date"].dt.date
            export_cols = ["Date", "Customer Name", "Category", "MRC", "Location"]
            available = [c for c in export_cols if c in new_export.columns]
            new_export[available].to_excel(writer, sheet_name="New Customers", index=False)
        
        # Competitive Analysis
        if comp_data:
            pd.DataFrame(comp_data).to_excel(writer, sheet_name="Competitive Analysis", index=False)
    
    st.download_button(
        label="📥 Download Executive Report (Excel)",
        data=buffer.getvalue(),
        file_name=f"Talley_Executive_Report_{start_date}_to_{end_date}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    
    st.caption(f"Report generated: {datetime.now().strftime('%B %d, %Y at %I:%M %p')} • Auto-refresh: Every 5 minutes")

if __name__ == "__main__":
    run_dashboard()
