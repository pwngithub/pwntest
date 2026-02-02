
# dashboard.py — FINAL (v3: ARPU, Goals, & Trends)
import streamlit as st
import pandas as pd
import requests
import plotly.express as px
from datetime import timedelta
from io import BytesIO

st.set_page_config(page_title="Talley Customer Dashboard", layout="wide", page_icon="📊")

st.markdown("""
<style>
    .big-title {font-size: 44px !important; font-weight: bold; color: #1E3A8A; text-align: center;}
    .net-mrr {font-size: 68px !important; font-weight: bold; text-align: center; margin: 30px 0;}
    .positive {color: #16A34A !important;}
    .negative {color: #DC2626 !important;}
    .card {padding: 20px; border-radius: 12px; background: #1E293B; color: white;
           border-left: 6px solid; height: 170px; box-shadow: 0 4px 12px rgba(0,0,0,0.3);}
    .win {border-left-color: #16A34A;}
    .flag {border-left-color: #DC2626;}
    .metric-box {background-color: #1E293B; padding: 15px; border-radius: 10px; text-align: center; border: 1px solid #334155;}
    .stApp {background-color: #0F172A;}
</style>
""", unsafe_allow_html=True)

# ——————————————— DATA LOADER ———————————————
def load_from_jotform():
    try:
        api_key = st.secrets["jotform"]["api_key"]
        form_id = st.secrets["jotform"]["form_id"]
    except Exception as e:
        st.error("🚨 API Secrets missing! Please set [jotform] api_key and form_id in Streamlit Cloud settings.")
        return pd.DataFrame()

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

    # Fill missing critical columns
    for col in ["Category", "Reason", "Location"]:
        if col not in df.columns:
            df[col] = pd.NA
        df[col] = df[col].astype(str).replace(["nan", "None", "<NA>"], "Unknown")

    return df

def add_category_at_disconnect(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return df
    work = df.copy()
    work = work.sort_values(["Customer Name", "Submission Date"], kind="mergesort")
    work["_last_known_category"] = work.groupby("Customer Name")["Category"].ffill()
    work["Category at Disconnect"] = work["_last_known_category"].fillna("Unknown")
    work.drop(columns=["_last_known_category"], inplace=True)
    return work

def build_churn_detail(churn_df: pd.DataFrame) -> pd.DataFrame:
    if churn_df is None or churn_df.empty:
        return pd.DataFrame(columns=["Customer Name", "Disconnect Date", "Category at Disconnect", "Reason", "MRC Lost", "Location"])

    x = churn_df.sort_values(["Customer Name", "Submission Date"], kind="mergesort").copy()
    x = x.drop_duplicates(subset=["Customer Name"], keep="last")
    x["Disconnect Date"] = x["Submission Date"].dt.date
    x["MRC Lost"] = pd.to_numeric(x.get("MRC", 0), errors="coerce").fillna(0)

    cols = ["Customer Name", "Disconnect Date", "Category at Disconnect", "Reason", "MRC Lost", "Location"]
    x = x[cols].sort_values(["Disconnect Date", "MRC Lost"], ascending=[False, False]).reset_index(drop=True)
    return x

def run_dashboard():
    # Header
    col_logo, col_title = st.columns([1, 8])
    with col_logo:
        st.image("https://via.placeholder.com/140x90/1E3A8A/FFFFFF?text=TALLEY", width=140)
    with col_title:
        st.markdown('<p class="big-title">Customer Dashboard</p>', unsafe_allow_html=True)
        st.markdown("<p style='text-align:center; color:#94A3B8; margin-top:-15px;'>True Churn • Growth • Unit Economics</p>", unsafe_allow_html=True)

    df = get_data()
    if df.empty:
        st.warning("No data found or API keys missing.")
        st.stop()
    
    # 1. Add attributes BEFORE filtering
    df = add_category_at_disconnect(df)

    # ——————————————— SIDEBAR CONTROLS ———————————————
    st.sidebar.header("🎯 Goals & Filters")
    
    # NEW: Goal Setting
    mrr_goal = st.sidebar.number_input("Monthly Net MRR Goal ($)", min_value=0, value=2000, step=100)
    
    st.sidebar.divider()
    
    # Location Filter
    all_locations = sorted(list(df["Location"].unique()))
    selected_loc = st.sidebar.multiselect("Select Locations", all_locations, default=all_locations)
    
    # Category Filter
    all_cats = sorted(list(df["Category"].unique()))
    selected_cats = st.sidebar.multiselect("Select Categories", all_cats, default=all_cats)
    
    # Apply Filters
    df_filtered = df[df["Location"].isin(selected_loc) & df["Category"].isin(selected_cats)].copy()
    
    if df_filtered.empty:
        st.info("No data matches these filters.")
        st.stop()
    # ———————————————————————————————————————————————

    min_date = df_filtered["Submission Date"].min().date()
    max_date = df_filtered["Submission Date"].max().date()
    default_start = max_date - timedelta(days=89)

    col1, col2 = st.columns([3, 1])
    with col1:
        start_date, end_date = st.date_input(
            "Analysis Period",
            value=(default_start, max_date),
            min_value=min_date,
            max_value=max_date,
        )
    with col2:
        if st.button("Refresh Now"):
            st.cache_data.clear()
            st.rerun()

    period_start = pd.Timestamp(start_date)
    period_df = df_filtered[(df_filtered["Submission Date"].dt.date >= start_date) & (df_filtered["Submission Date"].dt.date <= end_date)].copy()

    # Calculate Metrics
    new_in = period_df[period_df["Status"] == "NEW"]
    churn_in = period_df[period_df["Status"] == "DISCONNECT"]

    new_count = new_in["Customer Name"].nunique()
    churn_count = churn_in["Customer Name"].nunique()
    new_mrc = new_in["MRC"].sum()
    churn_mrc = churn_in["MRC"].sum()
    net_mrr_movement = new_mrc - churn_mrc
    net_customer_movement = new_count - churn_count
    
    # ——————————————— NEW: ARPU CALCULATIONS ———————————————
    avg_new_mrc = new_mrc / new_count if new_count > 0 else 0
    avg_lost_mrc = churn_mrc / churn_count if churn_count > 0 else 0
    arpu_diff = avg_new_mrc - avg_lost_mrc
    # ——————————————————————————————————————————————————————

    # Big Net MRR Display
    st.markdown(
        f"""
    <div class="net-mrr {'positive' if net_mrr_movement >= 0 else 'negative'}">
        {'+$' if net_mrr_movement >= 0 else '-$'}{abs(net_mrr_movement):,.0f}
    </div>
    <p style="text-align:center; font-size:22px; color:#E2E8F0;">Net MRR Movement • {start_date} to {end_date}</p>
    """, unsafe_allow_html=True)

    # ——————————————— NEW: GOAL PROGRESS ———————————————
    if mrr_goal > 0:
        progress = min(max(net_mrr_movement / mrr_goal, 0.0), 1.0)
        st.markdown(f"**Pacing to ${mrr_goal:,} Goal:**")
        st.progress(progress)
        if net_mrr_movement >= mrr_goal:
            st.caption("🚀 Goal Exceeded! Great work.")
        elif net_mrr_movement > 0:
            st.caption(f"{progress*100:.1f}% of goal achieved")
        else:
            st.caption("Net movement is negative — currently off track.")
    st.divider()
    # ——————————————————————————————————————————————————

    # Monthly Trend Chart
    st.markdown("### 📈 Monthly Net MRR Trend")
    monthly_new = df_filtered[df_filtered["Status"]=="NEW"].set_index("Submission Date").resample("ME")["MRC"].sum()
    monthly_churn = df_filtered[df_filtered["Status"]=="DISCONNECT"].set_index("Submission Date").resample("ME")["MRC"].sum()
    
    trend_df = pd.DataFrame({"New MRC": monthly_new, "Lost MRC": monthly_churn}).fillna(0)
    trend_df["Net Change"] = trend_df["New MRC"] - trend_df["Lost MRC"]
    trend_df = trend_df.tail(12)

    fig_trend = px.bar(
        trend_df, 
        y="Net Change", 
        x=trend_df.index,
        color="Net Change",
        color_continuous_scale=["#DC2626", "#16A34A"],
        text_auto='.2s'
    )
    fig_trend.update_layout(xaxis_title="Month", yaxis_title="Net MRC ($)", showlegend=False)
    st.plotly_chart(fig_trend, use_container_width=True)
    st.divider()

    # ——————————————— QUALITY OF REVENUE (ARPU) ———————————————
    st.markdown("### 💎 Quality of Revenue (Unit Economics)")
    st.caption("Are we replacing low-value churn with high-value new customers?")
    
    q1, q2, q3 = st.columns(3)
    with q1:
        st.markdown('<div class="metric-box">', unsafe_allow_html=True)
        st.metric("Avg New Customer Value", f"${avg_new_mrc:,.0f}")
        st.markdown('</div>', unsafe_allow_html=True)
    with q2:
        st.markdown('<div class="metric-box">', unsafe_allow_html=True)
        st.metric("Avg Lost Customer Value", f"${avg_lost_mrc:,.0f}")
        st.markdown('</div>', unsafe_allow_html=True)
    with q3:
        st.markdown('<div class="metric-box">', unsafe_allow_html=True)
        color = "normal"
        if arpu_diff > 0: color = "normal" # Streamlit handles green automatically for + delta
        st.metric("Value Swap (Delta)", f"${abs(arpu_diff):,.0f}", 
                 delta=f"{arpu_diff:,.0f}", 
                 delta_color="normal" if arpu_diff >= 0 else "inverse",
                 help="Positive means new customers are worth more than the ones leaving.")
        st.markdown('</div>', unsafe_allow_html=True)
    
    st.divider()
    # —————————————————————————————————————————————————————————

    # Quick Insights
    st.markdown("### Quick Insights This Period")
    cards = []
    if not churn_in.empty:
        top_reason = churn_in["Reason"].value_counts().idxmax()
        top_count = churn_in["Reason"].value_counts().max()
        top_mrc = churn_in[churn_in["Reason"] == top_reason]["MRC"].sum()
        cards.append(f'<div class="card flag"><h4>Most Common Churn Reason</h4><b>{top_reason}</b><br>{top_count} customers · ${top_mrc:,.0f} lost</div>')
        
        biggest = churn_in.loc[churn_in["MRC"].idxmax()]
        name = str(biggest.get("Customer Name", "Unknown"))[:35]
        cards.append(f'<div class="card flag"><h4>Largest Single Loss</h4><b>{name}</b><br>${biggest["MRC"]:,.0f} MRC<br><small>{biggest.get("Reason", "")}</small></div>')

    if not new_in.empty:
        best = new_in.loc[new_in["MRC"].idxmax()]
        name = str(best.get("Customer Name", "New Customer"))[:35]
        cards.append(f'<div class="card win"><h4>Biggest New Win</h4><b>{name}</b><br>+${best["MRC"]:,.0f} MRC<br><small>{best.get("Location", "")}</small></div>')
        
        top_loc = new_in["Location"].value_counts().idxmax()
        count = new_in["Location"].value_counts().max()
        mrc = new_in[new_in["Location"] == top_loc]["MRC"].sum()
        cards.append(f'<div class="card win"><h4>Fastest Growing Location</h4><b>{top_loc}</b><br>+{count} customers<br>+${mrc:,.0f} MRC</div>')

    if cards:
        cols = st.columns(len(cards))
        for col, card in zip(cols, cards):
            with col:
                st.markdown(card, unsafe_allow_html=True)
    else:
        st.success("All quiet — no significant activity this period!")

    st.divider()

    # True Churn & Growth Metrics
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Churned Customers", f"{churn_count}", delta=f"-{churn_count}", delta_color="inverse")
    c2.metric("Lost MRC", f"${churn_mrc:,.0f}", delta=f"-${churn_mrc:,.0f}", delta_color="inverse")
    c3.metric("New Customers", f"{new_count}", delta=f"+{new_count}")
    c4.metric("New MRC", f"${new_mrc:,.0f}", delta=f"+${new_mrc:,.0f}")

    st.divider()

    # Charts
    col_a, col_b = st.columns(2)
    with col_a:
        st.subheader("Churn by Reason")
        if not churn_in.empty:
            reason_df = churn_in.groupby(["Reason", "Category at Disconnect"], dropna=False).agg(Count=("Customer Name", "nunique"), MRC_Lost=("MRC", "sum")).reset_index().sort_values("MRC_Lost", ascending=False)
            fig = px.bar(reason_df, x="Count", y="Reason", orientation="h", color="MRC_Lost", color_continuous_scale="Reds")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No churn this period")

    with col_b:
        st.subheader("New Customer Acquisition")
        if not new_in.empty:
            cat_vc = new_in["Category"].value_counts().reset_index()
            cat_vc.columns = ["Category", "count"]
            pie = px.pie(cat_vc, names="Category", values="count", color_discrete_sequence=px.colors.sequential.Greens)
            st.plotly_chart(pie, use_container_width=True)
        else:
            st.info("No new customers this period")

    st.divider()

    # ——————————————— NEW: INTERACTIVE DATA EDITOR ———————————————
    st.markdown("### Churned Customers Detail")
    churn_detail_df = build_churn_detail(churn_in)
    if not churn_detail_df.empty:
        # Use st.data_editor instead of dataframe for better sorting/interaction
        st.data_editor(
            churn_detail_df, 
            column_config={
                "MRC Lost": st.column_config.NumberColumn(format="$%.2f"),
                "Disconnect Date": st.column_config.DateColumn(),
            },
            use_container_width=True, 
            hide_index=True,
            disabled=True # Read-only, but allows sorting/copying
        )
    else:
        st.info("No churned customers in this period.")
    # ————————————————————————————————————————————————————————————

    st.divider()

    # Churn by Competition
    st.markdown("### Churn by Competition")
    if not churn_in.empty:
        competitors = {"Fidium": "Fidium", "Spectrum": "Spectrum", "Starlink": "Starlink", "CCI": "CCI", "GWI": "GWI", "Other": "Other"}
        comp_data = []
        for label, keyword in competitors.items():
            mask = churn_in["Reason"].astype(str).str.contains(keyword, case=False, na=False)
            if mask.sum() > 0:
                comp_data.append({"Competitor": label, "Customers Lost": int(mask.sum()), "MRC Lost": churn_in.loc[mask, "MRC"].sum()})
        
        if comp_data:
            comp_df = pd.DataFrame(comp_data)
            fig_pie = px.pie(comp_df, names="Competitor", values="Customers Lost", color_discrete_sequence=px.colors.sequential.Reds_r, hole=0.45)
            st.plotly_chart(fig_pie, use_container_width=True)
        else:
            st.success("No customers lost to named competitors this period!")
    else:
        st.info("No churn data available")

    # Export
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        churn_detail_df.to_excel(writer, sheet_name="Churned Customers Detail", index=False)
        period_df.to_excel(writer, sheet_name="Raw Data", index=False)
    st.download_button("Download Excel Report", data=buffer.getvalue(), file_name=f"Talley_Report_{start_date}.xlsx")

if __name__ == "__main__":
    run_dashboard()
