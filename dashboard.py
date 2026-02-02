# dashboard_ceo_board_v2.py — EXECUTIVE DASHBOARD WITH PROPER CUSTOMER TRACKING
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
    
    /* Warning badge */
    .warning-badge {
        background: #FEF3C7;
        color: #92400E;
        padding: 4px 12px;
        border-radius: 12px;
        font-size: 12px;
        font-weight: 600;
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
    
    # CRITICAL: Normalize customer names for proper deduplication
    df["Customer Name"] = df["Customer Name"].astype(str).str.strip().str.upper()
    df["Customer Name Clean"] = df["Customer Name"]  # Keep a clean version for tracking

    for col in ["Category", "Reason", "Location"]:
        if col not in df.columns:
            df[col] = pd.NA

    return df

def build_customer_lifecycle(df: pd.DataFrame):
    """
    Build comprehensive customer lifecycle tracking.
    Each customer should only be counted once at any point in time.
    Tracks: first acquisition, latest status, category progression, total value.
    """
    if df.empty:
        return pd.DataFrame()
    
    # Sort by customer and date to get chronological order
    df_sorted = df.sort_values(["Customer Name", "Submission Date"]).copy()
    
    # For each customer, get their complete history
    customer_lifecycle = []
    
    for customer_name, group in df_sorted.groupby("Customer Name"):
        if pd.isna(customer_name) or customer_name == "" or customer_name.upper() == "NAN":
            continue
            
        # Get first NEW event
        first_new = group[group["Status"] == "NEW"].sort_values("Submission Date").head(1)
        
        if first_new.empty:
            # Customer has records but no NEW status - skip or flag
            continue
        
        first_acquisition = first_new.iloc[0]
        
        # Get all disconnects
        disconnects = group[group["Status"] == "DISCONNECT"].sort_values("Submission Date")
        
        # Determine current status
        if not disconnects.empty:
            # Customer has churned (use latest disconnect)
            latest_disconnect = disconnects.iloc[-1]
            current_status = "CHURNED"
            churn_date = latest_disconnect["Submission Date"]
            churn_reason = latest_disconnect.get("Reason", "Unknown")
            final_mrc = latest_disconnect.get("MRC", 0)
            
            # Check if they came back (NEW after DISCONNECT)
            reacquisitions = group[(group["Status"] == "NEW") & 
                                  (group["Submission Date"] > churn_date)]
            if not reacquisitions.empty:
                current_status = "REACQUIRED"
                latest_acquisition = reacquisitions.iloc[-1]
                final_mrc = latest_acquisition.get("MRC", 0)
        else:
            current_status = "ACTIVE"
            churn_date = pd.NaT
            churn_reason = None
            final_mrc = first_acquisition.get("MRC", 0)
        
        # Get category progression (forward fill to get latest known)
        categories = group["Category"].dropna()
        latest_category = categories.iloc[-1] if not categories.empty else "Unknown"
        
        # Calculate total value
        total_value = group["MRC"].sum()
        
        customer_lifecycle.append({
            "Customer Name": customer_name,
            "First Acquisition Date": first_acquisition["Submission Date"],
            "Current Status": current_status,
            "Latest Category": latest_category,
            "First Category": first_acquisition.get("Category", "Unknown"),
            "Initial MRC": first_acquisition.get("MRC", 0),
            "Current MRC": final_mrc,
            "Total Value": total_value,
            "Churn Date": churn_date,
            "Churn Reason": churn_reason,
            "Location": first_acquisition.get("Location", "Unknown"),
            "Total Events": len(group),
        })
    
    return pd.DataFrame(customer_lifecycle)

def calculate_period_metrics(lifecycle_df: pd.DataFrame, df: pd.DataFrame, start_date, end_date):
    """
    Calculate metrics for a specific period using lifecycle tracking.
    Ensures each customer is only counted once.
    """
    if lifecycle_df.empty:
        return {}
    
    period_start = pd.Timestamp(start_date)
    period_end = pd.Timestamp(end_date)
    
    # Beginning balance: customers acquired before period start and not churned before period start
    beginning = lifecycle_df[
        (lifecycle_df["First Acquisition Date"] < period_start) &
        ((lifecycle_df["Churn Date"].isna()) | (lifecycle_df["Churn Date"] >= period_start))
    ]
    beginning_customers = len(beginning)
    beginning_mrc = beginning["Current MRC"].sum()
    
    # New customers: acquired during period (first acquisition in period)
    new_customers = lifecycle_df[
        (lifecycle_df["First Acquisition Date"] >= period_start) &
        (lifecycle_df["First Acquisition Date"] <= period_end)
    ]
    new_count = len(new_customers)
    new_mrc = new_customers["Initial MRC"].sum()
    
    # Churned customers: churned during period
    churned_customers = lifecycle_df[
        (lifecycle_df["Churn Date"] >= period_start) &
        (lifecycle_df["Churn Date"] <= period_end) &
        (lifecycle_df["Current Status"] == "CHURNED")
    ]
    churn_count = len(churned_customers)
    churn_mrc = churned_customers["Current MRC"].sum()
    
    # Ending balance
    ending = lifecycle_df[
        (lifecycle_df["First Acquisition Date"] <= period_end) &
        ((lifecycle_df["Churn Date"].isna()) | (lifecycle_df["Churn Date"] > period_end))
    ]
    ending_customers = len(ending)
    ending_mrc = ending["Current MRC"].sum()
    
    # Calculate movements
    net_customer_movement = new_count - churn_count
    net_mrr_movement = new_mrc - churn_mrc
    
    # Rates
    churn_rate = (churn_count / beginning_customers * 100) if beginning_customers > 0 else 0
    growth_rate = (new_count / beginning_customers * 100) if beginning_customers > 0 else 0
    net_growth_rate = ((ending_customers - beginning_customers) / beginning_customers * 100) if beginning_customers > 0 else 0
    
    # Average values
    avg_customer_value = ending_mrc / ending_customers if ending_customers > 0 else 0
    
    return {
        "beginning_customers": beginning_customers,
        "beginning_mrc": beginning_mrc,
        "new_count": new_count,
        "new_mrc": new_mrc,
        "churn_count": churn_count,
        "churn_mrc": churn_mrc,
        "ending_customers": ending_customers,
        "ending_mrc": ending_mrc,
        "net_customer_movement": net_customer_movement,
        "net_mrr_movement": net_mrr_movement,
        "churn_rate": churn_rate,
        "growth_rate": growth_rate,
        "net_growth_rate": net_growth_rate,
        "avg_customer_value": avg_customer_value,
        "new_customers_df": new_customers,
        "churned_customers_df": churned_customers,
        "active_customers_df": ending,
    }

def calculate_trends(lifecycle_df: pd.DataFrame, df: pd.DataFrame, current_start, current_end):
    """Calculate trends by comparing current period to prior period"""
    if lifecycle_df.empty:
        return {}
    
    period_days = (current_end - current_start).days + 1
    prior_start = current_start - timedelta(days=period_days)
    prior_end = current_start - timedelta(days=1)
    
    current_metrics = calculate_period_metrics(lifecycle_df, df, current_start, current_end)
    prior_metrics = calculate_period_metrics(lifecycle_df, df, prior_start, prior_end)
    
    trends = {
        "new_customers_change": ((current_metrics["new_count"] - prior_metrics["new_count"]) / prior_metrics["new_count"] * 100) if prior_metrics["new_count"] > 0 else 0,
        "churn_customers_change": ((current_metrics["churn_count"] - prior_metrics["churn_count"]) / prior_metrics["churn_count"] * 100) if prior_metrics["churn_count"] > 0 else 0,
        "new_mrc_change": ((current_metrics["new_mrc"] - prior_metrics["new_mrc"]) / prior_metrics["new_mrc"] * 100) if prior_metrics["new_mrc"] > 0 else 0,
        "churn_mrc_change": ((current_metrics["churn_mrc"] - prior_metrics["churn_mrc"]) / prior_metrics["churn_mrc"] * 100) if prior_metrics["churn_mrc"] > 0 else 0,
    }
    
    return trends

def generate_strategic_insights(metrics: dict, trends: dict):
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
    
    # Revenue concentration
    if metrics.get("avg_customer_value", 0) > 0 and metrics.get("new_count", 0) > 0:
        new_avg = metrics["new_mrc"] / metrics["new_count"]
        if new_avg > metrics["avg_customer_value"] * 1.2:
            insights.append("✓ **Premium Customer Acquisition**: New customers have 20%+ higher average value")
        elif new_avg < metrics["avg_customer_value"] * 0.8:
            alerts.append("⚠️ **Lower Value Acquisitions**: New customers averaging 20%+ below current customer base")
    
    return insights, alerts

def build_monthly_trend(lifecycle_df: pd.DataFrame, months: int = 12):
    """Build monthly trend data using lifecycle tracking"""
    if lifecycle_df.empty:
        return pd.DataFrame()
    
    max_date = lifecycle_df["First Acquisition Date"].max()
    min_date = max_date - timedelta(days=months*30)
    
    # Create monthly buckets
    date_range = pd.date_range(start=min_date, end=max_date, freq='MS')
    monthly_data = []
    
    for start in date_range:
        end = start + pd.offsets.MonthEnd(0)
        
        # New customers this month
        new = lifecycle_df[
            (lifecycle_df["First Acquisition Date"] >= start) &
            (lifecycle_df["First Acquisition Date"] <= end)
        ]
        
        # Churned customers this month
        churned = lifecycle_df[
            (lifecycle_df["Churn Date"] >= start) &
            (lifecycle_df["Churn Date"] <= end) &
            (lifecycle_df["Current Status"] == "CHURNED")
        ]
        
        monthly_data.append({
            "Month": start,
            "New Customers": len(new),
            "New MRC": new["Initial MRC"].sum(),
            "Churned Customers": len(churned),
            "Churned MRC": churned["Current MRC"].sum(),
            "Net Customers": len(new) - len(churned),
            "Net MRC": new["Initial MRC"].sum() - churned["Current MRC"].sum(),
        })
    
    return pd.DataFrame(monthly_data)

def run_dashboard():
    # ==================== HEADER ====================
    col_logo, col_title = st.columns([1, 8])
    with col_logo:
        st.image("https://via.placeholder.com/160x100/1E3A8A/FFFFFF?text=TALLEY", width=160)
    with col_title:
        st.markdown('<p class="main-title">Executive Dashboard</p>', unsafe_allow_html=True)
        st.markdown('<p class="subtitle">Strategic Performance Metrics • Customer Lifecycle Analytics • Real-time Intelligence</p>', unsafe_allow_html=True)

    # ==================== DATA LOADING ====================
    df = get_data()
    if df.empty:
        st.error("⚠️ Unable to load data. Please check connection.")
        st.stop()

    # Build customer lifecycle (ensures no double counting)
    with st.spinner("Building customer lifecycle analytics..."):
        lifecycle_df = build_customer_lifecycle(df)
    
    if lifecycle_df.empty:
        st.error("No valid customer data found.")
        st.stop()
    
    # Show data quality metrics
    with st.expander("📊 Data Quality Metrics", expanded=False):
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Unique Customers", len(lifecycle_df))
        with col2:
            st.metric("Total Events", len(df))
        with col3:
            duplicate_events = len(df) - len(lifecycle_df)
            st.metric("Events per Customer", f"{len(df) / len(lifecycle_df):.1f}")
        with col4:
            active = len(lifecycle_df[lifecycle_df["Current Status"] == "ACTIVE"])
            st.metric("Currently Active", active)

    # ==================== DATE SELECTOR ====================
    min_date = lifecycle_df["First Acquisition Date"].min().date()
    max_date = lifecycle_df["First Acquisition Date"].max().date()
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
    metrics = calculate_period_metrics(lifecycle_df, df, start_date, end_date)
    trends = calculate_trends(lifecycle_df, df, pd.Timestamp(start_date), pd.Timestamp(end_date))
    
    # Extract key metrics
    beginning_customers = metrics["beginning_customers"]
    beginning_mrc = metrics["beginning_mrc"]
    new_count = metrics["new_count"]
    new_mrc = metrics["new_mrc"]
    churn_count = metrics["churn_count"]
    churn_mrc = metrics["churn_mrc"]
    ending_customers = metrics["ending_customers"]
    ending_mrc = metrics["ending_mrc"]
    net_customer_movement = metrics["net_customer_movement"]
    net_mrr_movement = metrics["net_mrr_movement"]
    churn_rate = metrics["churn_rate"]
    growth_rate = metrics["growth_rate"]
    net_growth_rate = metrics["net_growth_rate"]
    avg_customer_value = metrics["avg_customer_value"]
    
    ltv_estimate = avg_customer_value * 36  # 3-year LTV
    annual_run_rate = ending_mrc * 12
    
    # Get customer dataframes
    new_customers_df = metrics["new_customers_df"]
    churned_customers_df = metrics["churned_customers_df"]
    active_customers_df = metrics["active_customers_df"]
    
    # Generate insights
    insights, alerts = generate_strategic_insights(metrics, trends)

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
                <div class="kpi-title">New Customers (Unique)</div>
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
                <div class="kpi-title">Churned Customers (Unique)</div>
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
                <div class="kpi-title">Monthly Churn Rate</div>
                <div class="kpi-value">{churn_rate:.1f}%</div>
                <div class="kpi-change {churn_health}">
                    Target: <3.0%
                    <br><span style="color: #94A3B8; font-size: 14px;">Industry: 3-5%</span>
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
                    {ending_customers:,} active customers
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
        st.metric(
            "Annual Run Rate",
            f"${annual_run_rate:,.0f}",
            delta=f"${net_mrr_movement * 12:,.0f}"
        )

    st.divider()

    # ==================== CUSTOMER COHORT ANALYSIS ====================
    st.markdown("### 👥 Customer Base Analysis")
    
    cohort1, cohort2, cohort3 = st.columns(3)
    
    with cohort1:
        st.markdown("#### Status Distribution")
        status_counts = lifecycle_df["Current Status"].value_counts()
        fig_status = px.pie(
            values=status_counts.values,
            names=status_counts.index,
            color_discrete_sequence=["#10B981", "#EF4444", "#F59E0B"],
            hole=0.4
        )
        fig_status.update_traces(textposition="inside", textinfo="percent+label")
        fig_status.update_layout(height=300, showlegend=False, template="plotly_dark")
        st.plotly_chart(fig_status, use_container_width=True)
    
    with cohort2:
        st.markdown("#### Active Customers by Category")
        active_by_cat = active_customers_df["Latest Category"].value_counts().head(8)
        fig_cat = px.bar(
            x=active_by_cat.values,
            y=active_by_cat.index,
            orientation='h',
            color=active_by_cat.values,
            color_continuous_scale="Blues"
        )
        fig_cat.update_layout(height=300, showlegend=False, template="plotly_dark")
        st.plotly_chart(fig_cat, use_container_width=True)
    
    with cohort3:
        st.markdown("#### Key Metrics")
        st.metric("Active Customers", len(active_customers_df))
        st.metric("Churned (All Time)", len(lifecycle_df[lifecycle_df["Current Status"] == "CHURNED"]))
        st.metric("Lifetime Churn Rate", f"{(len(lifecycle_df[lifecycle_df['Current Status'] == 'CHURNED']) / len(lifecycle_df) * 100):.1f}%")

    st.divider()

    # ==================== TREND ANALYSIS ====================
    st.markdown("### 📈 12-Month Performance Trends")
    
    monthly_data = build_monthly_trend(lifecycle_df, months=12)
    
    if not monthly_data.empty:
        fig = go.Figure()
        
        fig.add_trace(go.Bar(
            x=monthly_data["Month"],
            y=monthly_data["New Customers"],
            name="New Customers",
            marker_color="#10B981"
        ))
        
        fig.add_trace(go.Bar(
            x=monthly_data["Month"],
            y=monthly_data["Churned Customers"],
            name="Churned Customers",
            marker_color="#EF4444"
        ))
        
        fig.add_trace(go.Scatter(
            x=monthly_data["Month"],
            y=monthly_data["Net Customers"],
            name="Net Growth",
            mode="lines+markers",
            line=dict(color="#3B82F6", width=3),
            marker=dict(size=8),
            yaxis="y2"
        ))
        
        fig.update_layout(
            title="Customer Acquisition vs Churn (Monthly) - Unique Customers Only",
            xaxis_title="Month",
            yaxis_title="Customers",
            yaxis2=dict(title="Net Growth", overlaying="y", side="right"),
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
    st.markdown("### 🔍 Churn Deep Dive (Period)")
    
    if not churned_customers_df.empty:
        col_reason, col_category = st.columns(2)
        
        with col_reason:
            st.markdown("#### Top Churn Reasons")
            reason_counts = churned_customers_df["Churn Reason"].value_counts().head(10)
            reason_mrc = churned_customers_df.groupby("Churn Reason")["Current MRC"].sum().reindex(reason_counts.index)
            
            reason_df = pd.DataFrame({
                "Reason": reason_counts.index,
                "Customers": reason_counts.values,
                "MRC Lost": reason_mrc.values
            })
            
            fig_reason = px.bar(
                reason_df,
                y="Reason",
                x="Customers",
                orientation="h",
                color="MRC Lost",
                color_continuous_scale="Reds",
                text="Customers"
            )
            fig_reason.update_traces(textposition="outside")
            fig_reason.update_layout(height=400, showlegend=False, template="plotly_dark")
            st.plotly_chart(fig_reason, use_container_width=True)
        
        with col_category:
            st.markdown("#### Churn by Category")
            cat_counts = churned_customers_df["Latest Category"].value_counts()
            
            fig_cat = px.pie(
                values=cat_counts.values,
                names=cat_counts.index,
                color_discrete_sequence=px.colors.sequential.Reds_r,
                hole=0.4
            )
            fig_cat.update_traces(textposition="inside", textinfo="percent+label")
            fig_cat.update_layout(height=400, showlegend=False, template="plotly_dark")
            st.plotly_chart(fig_cat, use_container_width=True)
        
        # Detailed churn table
        st.markdown("#### Churned Customer Details")
        churn_display = churned_customers_df.copy()
        churn_display["Churn Date"] = pd.to_datetime(churn_display["Churn Date"]).dt.date
        
        display_cols = ["Customer Name", "Churn Date", "Latest Category", "Churn Reason", "Current MRC", "Location"]
        
        st.dataframe(
            churn_display[display_cols].sort_values("Churn Date", ascending=False).head(20).style.format({"Current MRC": "${:,.0f}"}),
            use_container_width=True,
            hide_index=True
        )
        
        st.caption(f"Showing top 20 of {len(churned_customers_df):,} churned customers (unique only)")
    
    else:
        st.success("✅ No customer churn in this period!")

    st.divider()

    # ==================== COMPETITIVE INTELLIGENCE ====================
    st.markdown("### 🎯 Competitive Analysis")
    
    if not churned_customers_df.empty:
        competitors = {
            "Fidium": "Fidium",
            "Spectrum": "Spectrum",
            "Starlink": "Starlink",
            "CCI": "CCI",
            "GWI": "GWI",
            "Other": "Other",
        }
        
        comp_data = []
        for label, keyword in competitors.items():
            mask = churned_customers_df["Churn Reason"].astype(str).str.contains(keyword, case=False, na=False)
            count = int(mask.sum())
            mrc = churned_customers_df.loc[mask, "Current MRC"].sum()
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
                    title="Unique Customers Lost by Competitor",
                    height=400,
                    template="plotly_dark"
                )
                st.plotly_chart(fig_comp, use_container_width=True)
            
            with col_table:
                st.markdown("#### Competitive Impact Summary")
                total_comp_customers = comp_df["Customers Lost"].sum()
                total_comp_mrc = comp_df["MRC Lost"].sum()
                pct_of_churn = (total_comp_customers / churn_count * 100) if churn_count > 0 else 0
                
                st.metric("Unique Customers Lost", f"{total_comp_customers:,}", f"{pct_of_churn:.0f}% of churn")
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
    st.markdown("### 🚀 New Customer Acquisition (Period)")
    
    if not new_customers_df.empty:
        acq1, acq2 = st.columns(2)
        
        with acq1:
            st.markdown("#### Acquisition by Category")
            cat_new = new_customers_df["First Category"].value_counts()
            
            fig_new_cat = px.pie(
                values=cat_new.values,
                names=cat_new.index,
                color_discrete_sequence=px.colors.sequential.Greens_r,
                hole=0.4
            )
            fig_new_cat.update_traces(textposition="inside", textinfo="percent+label")
            fig_new_cat.update_layout(height=400, showlegend=False, template="plotly_dark")
            st.plotly_chart(fig_new_cat, use_container_width=True)
        
        with acq2:
            st.markdown("#### Top Acquisition Locations")
            loc_new = new_customers_df["Location"].value_counts().head(10)
            
            fig_new_loc = px.bar(
                y=loc_new.index,
                x=loc_new.values,
                orientation="h",
                color=loc_new.values,
                color_continuous_scale="Greens",
                text=loc_new.values
            )
            fig_new_loc.update_traces(textposition="outside")
            fig_new_loc.update_layout(height=400, showlegend=False, template="plotly_dark")
            st.plotly_chart(fig_new_loc, use_container_width=True)
        
        # New customer details
        st.markdown("#### New Customer Details")
        new_display = new_customers_df.copy()
        new_display["Acquisition Date"] = pd.to_datetime(new_display["First Acquisition Date"]).dt.date
        
        display_cols = ["Customer Name", "Acquisition Date", "First Category", "Initial MRC", "Location"]
        
        st.dataframe(
            new_display[display_cols].sort_values("Acquisition Date", ascending=False).head(20).style.format({"Initial MRC": "${:,.0f}"}),
            use_container_width=True,
            hide_index=True
        )
        
        st.caption(f"Showing top 20 of {len(new_customers_df):,} new customers (unique only)")
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
                "CUSTOMER METRICS",
                "Beginning Unique Customers",
                "New Unique Customers Added",
                "Unique Customers Churned",
                "Net Customer Movement",
                "Ending Unique Customers",
                "Churn Rate (%)",
                "Growth Rate (%)",
                "Net Growth Rate (%)",
                "",
                "REVENUE METRICS",
                "Beginning MRR",
                "New MRR Added",
                "MRR Churned",
                "Net MRR Movement",
                "Ending MRR",
                "Avg Customer Value (MRR)",
                "Estimated LTV (3yr)",
                "Annual Run Rate",
                "",
                "DATA QUALITY",
                "Total Unique Customers (All Time)",
                "Total Transaction Events",
                "Avg Events per Customer",
            ],
            "Value": [
                f"{start_date} to {end_date}",
                "",
                beginning_customers,
                new_count,
                churn_count,
                net_customer_movement,
                ending_customers,
                f"{churn_rate:.2f}%",
                f"{growth_rate:.2f}%",
                f"{net_growth_rate:.2f}%",
                "",
                "",
                f"${beginning_mrc:,.2f}",
                f"${new_mrc:,.2f}",
                f"${churn_mrc:,.2f}",
                f"${net_mrr_movement:,.2f}",
                f"${ending_mrc:,.2f}",
                f"${avg_customer_value:,.2f}",
                f"${ltv_estimate:,.2f}",
                f"${annual_run_rate:,.2f}",
                "",
                "",
                len(lifecycle_df),
                len(df),
                f"{len(df) / len(lifecycle_df):.2f}",
            ]
        }
        pd.DataFrame(summary_data).to_excel(writer, sheet_name="Executive Summary", index=False)
        
        # Strategic Insights
        if insights or alerts:
            insights_data = []
            for insight in insights:
                insights_data.append({"Type": "Win", "Priority": "High", "Description": insight})
            for alert in alerts:
                insights_data.append({"Type": "Alert", "Priority": "Critical", "Description": alert})
            pd.DataFrame(insights_data).to_excel(writer, sheet_name="Strategic Insights", index=False)
        
        # Customer Lifecycle (Full)
        lifecycle_export = lifecycle_df.copy()
        lifecycle_export["First Acquisition Date"] = pd.to_datetime(lifecycle_export["First Acquisition Date"]).dt.date
        lifecycle_export["Churn Date"] = pd.to_datetime(lifecycle_export["Churn Date"]).dt.date
        lifecycle_export.to_excel(writer, sheet_name="Customer Lifecycle", index=False)
        
        # Period Churned Customers
        if not churned_customers_df.empty:
            churn_export = churned_customers_df.copy()
            churn_export["Churn Date"] = pd.to_datetime(churn_export["Churn Date"]).dt.date
            churn_export.to_excel(writer, sheet_name="Period Churned Customers", index=False)
        
        # Period New Customers
        if not new_customers_df.empty:
            new_export = new_customers_df.copy()
            new_export["First Acquisition Date"] = pd.to_datetime(new_export["First Acquisition Date"]).dt.date
            new_export.to_excel(writer, sheet_name="Period New Customers", index=False)
        
        # Active Customers
        active_export = active_customers_df.copy()
        active_export["First Acquisition Date"] = pd.to_datetime(active_export["First Acquisition Date"]).dt.date
        active_export.to_excel(writer, sheet_name="Active Customers", index=False)
        
        # Competitive Analysis
        if comp_data:
            pd.DataFrame(comp_data).to_excel(writer, sheet_name="Competitive Analysis", index=False)
        
        # Monthly Trends
        if not monthly_data.empty:
            monthly_export = monthly_data.copy()
            monthly_export["Month"] = pd.to_datetime(monthly_export["Month"]).dt.date
            monthly_export.to_excel(writer, sheet_name="Monthly Trends", index=False)
    
    st.download_button(
        label="📥 Download Executive Report (Excel)",
        data=buffer.getvalue(),
        file_name=f"Talley_Executive_Report_{start_date}_to_{end_date}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    
    st.caption(f"Report generated: {datetime.now().strftime('%B %d, %Y at %I:%M %p')} • Data includes {len(lifecycle_df):,} unique customers with {len(df):,} total events")

if __name__ == "__main__":
    run_dashboard()
