# dashboard.py — "Dark Glass" UI Edition
import streamlit as st
import pandas as pd
import requests
import plotly.express as px
import plotly.io as pio
from datetime import timedelta, date, datetime
from io import BytesIO

# ——————————————— CONFIG & STYLING ———————————————
st.set_page_config(page_title="Talley Dashboard", layout="wide", page_icon="⚡")

# Force Dark Mode for Plotly
pio.templates.default = "plotly_dark"

st.markdown("""
<style>
    /* GLOBAL THEME */
    .stApp {
        background-color: #0D1117; /* Very dark blue-black */
        color: #E6EDF3;
    }
    
    /* REMOVE DEFAULT STREAMLIT PADDING */
    .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
    }

    /* CARD STYLES */
    .dashboard-card {
        background-color: #161B22;
        border: 1px solid #30363D;
        border-radius: 12px;
        padding: 24px;
        margin-bottom: 20px;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.3);
    }
    
    /* TEXT STYLES */
    .metric-label {
        font-size: 0.85rem;
        color: #8B949E;
        font-weight: 500;
        margin-bottom: 4px;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    .metric-value {
        font-size: 1.8rem;
        font-weight: 700;
        color: #F0F6FC;
    }
    .metric-sub {
        font-size: 0.8rem;
        color: #8B949E;
    }
    
    /* HERO SECTION SPECIFICS */
    .hero-big-value {
        font-size: 4rem;
        font-weight: 800;
        line-height: 1;
    }
    .hero-green { color: #3FB950; text-shadow: 0 0 20px rgba(63, 185, 80, 0.3); }
    .hero-red { color: #F85149; text-shadow: 0 0 20px rgba(248, 81, 73, 0.3); }
    
    /* INSIGHT CARDS (ROW OF 4) */
    .insight-box {
        background-color: #161B22;
        border: 1px solid #30363D;
        border-radius: 12px;
        padding: 20px;
        height: 160px;
        position: relative;
        display: flex;
        flex-direction: column;
        justify-content: space-between;
    }
    .insight-icon {
        position: absolute;
        top: 20px;
        right: 20px;
        width: 32px;
        height: 32px;
        border-radius: 50%;
        background: #21262D;
        display: flex;
        align-items: center;
        justify-content: center;
        color: #8B949E;
    }
    
    /* CUSTOM DATE BAR */
    .date-bar {
        background-color: #161B22;
        border: 1px solid #30363D;
        border-radius: 12px;
        padding: 15px;
        margin-bottom: 20px;
        display: flex;
        align-items: center;
        justify-content: space-between;
    }
    
    /* BUTTON OVERRIDES */
    div.stButton > button {
        background-color: #21262D;
        color: #C9D1D9;
        border: 1px solid #30363D;
        border-radius: 6px;
        font-size: 0.8rem;
    }
    div.stButton > button:hover {
        background-color: #30363D;
        border-color: #8B949E;
        color: white;
    }
</style>
""", unsafe_allow_html=True)

# ——————————————— HELPERS ———————————————
def load_from_jotform():
    try:
        api_key = st.secrets["jotform"]["api_key"]
        form_id = st.secrets["jotform"]["form_id"]
    except Exception:
        st.error("🚨 API Secrets missing! Check .streamlit/secrets.toml")
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
            if not data.get("content"): break
            for item in data["content"]:
                row = {"Submission Date": item["created_at"], "Submission ID": item["id"]}
                for ans in item.get("answers", {}).values():
                    name = ans.get("name") or ans.get("text") or "unknown"
                    answer = ans.get("answer")
                    if isinstance(answer, dict):
                        parts = [str(v) if not isinstance(v, list) else ", ".join(map(str, v)) for v in answer.values()]
                        answer = ", ".join(filter(None, parts))
                    elif isinstance(answer, list):
                        answer = ", ".join(map(str, answer))
                    elif answer is None or str(answer).strip() == "":
                        continue
                    row[name] = str(answer).strip()
                submissions.append(row)
            if len(data["content"]) < limit: break
            offset += limit
        except Exception as e:
            st.error(f"Error: {e}")
            return pd.DataFrame()
    return pd.DataFrame(submissions)

@st.cache_data(ttl=300)
def get_data():
    df = load_from_jotform()
    if df.empty: return df
    
    rename_map = {
        "customerName": "Customer Name", "date": "Date", "employee": "Employee",
        "location": "Location", "status": "Status", "category": "Category",
        "reason": "Reason", "mrc": "MRC", "disconnectReason": "Disconnect Reason Detail"
    }
    df.rename(columns=rename_map, inplace=True)
    df["Submission Date"] = pd.to_datetime(df["Submission Date"], errors="coerce")
    df = df.dropna(subset=["Submission Date"]).copy()
    
    if "Status" not in df.columns: df["Status"] = ""
    df["Status"] = df["Status"].astype(str).str.upper().str.strip()
    
    if "MRC" not in df.columns: df["MRC"] = 0
    df["MRC"] = pd.to_numeric(df["MRC"], errors="coerce").fillna(0)
    
    for col in ["Category", "Reason", "Location", "Customer Name"]:
        if col not in df.columns: df[col] = pd.NA
        df[col] = df[col].astype(str).replace(["nan", "None", "<NA>"], "Unknown")
        
    return df

def add_category_at_disconnect(df):
    if df.empty: return df
    work = df.sort_values(["Customer Name", "Submission Date"], kind="mergesort").copy()
    work["_last_known_category"] = work.groupby("Customer Name")["Category"].ffill()
    work["Category at Disconnect"] = work["_last_known_category"].fillna("Unknown")
    work.drop(columns=["_last_known_category"], inplace=True)
    return work

def build_churn_detail(churn_df):
    if churn_df.empty: return pd.DataFrame()
    x = churn_df.sort_values(["Customer Name", "Submission Date"], kind="mergesort").copy()
    x = x.drop_duplicates(subset=["Customer Name"], keep="last")
    x["Disconnect Date"] = x["Submission Date"].dt.date
    x["MRC Lost"] = pd.to_numeric(x.get("MRC", 0), errors="coerce").fillna(0)
    cols = ["Customer Name", "Disconnect Date", "Category at Disconnect", "Reason", "MRC Lost", "Location"]
    # Ensure all columns exist
    for c in cols:
        if c not in x.columns: x[c] = pd.NA
    return x[cols].sort_values(["Disconnect Date", "MRC Lost"], ascending=[False, False])

# ——————————————— MAIN APP ———————————————
def run_dashboard():
    # --- DATA PREP ---
    raw_df = get_data()
    if raw_df.empty:
        st.warning("No data found.")
        st.stop()
    
    df = add_category_at_disconnect(raw_df)

    # --- SESSION STATE FOR DATES ---
    if 'date_range' not in st.session_state:
        # Default: Last 90 Days
        end = df["Submission Date"].max().date()
        start = end - timedelta(days=89)
        st.session_state['date_range'] = (start, end)

    # --- SIDEBAR FILTERS ---
    st.sidebar.header("Filter Views")
    
    # Location
    all_locs = sorted(list(df["Location"].unique()))
    sel_locs = st.sidebar.multiselect("Location", all_locs, default=all_locs)
    
    # Category
    all_cats = sorted(list(df["Category"].unique()))
    sel_cats = st.sidebar.multiselect("Category (Current/New)", all_cats, default=all_cats)
    
    # Category at Disconnect
    all_disc_cats = sorted(list(df["Category at Disconnect"].unique()))
    sel_disc = st.sidebar.multiselect("Category at Disconnect", all_disc_cats, default=all_disc_cats)
    
    # Reason
    all_reasons = sorted(list(df["Reason"].unique()))
    sel_reason = st.sidebar.multiselect("Reason", all_reasons, default=all_reasons)
    
    # Filtering
    df_filtered = df[
        df["Location"].isin(sel_locs) & 
        df["Category"].isin(sel_cats) & 
        df["Category at Disconnect"].isin(sel_disc) &
        df["Reason"].isin(sel_reason)
    ].copy()

    # --- TOP BAR (Date Controls) ---
    st.markdown('<div style="margin-bottom: 5px; color: #8B949E; font-size: 0.9rem;">Date range</div>', unsafe_allow_html=True)
    
    # We use columns to simulate the bar layout: [Date Picker] [Spacer] [Buttons]
    c_date, c_space, c_30, c_90, c_180, c_ytd = st.columns([3, 3, 0.6, 0.6, 0.7, 0.6])
    
    with c_date:
        new_range = st.date_input(
            "Select Range",
            value=st.session_state['date_range'],
            label_visibility="collapsed"
        )
        if len(new_range) == 2:
            st.session_state['date_range'] = new_range

    # Date Button Logic
    curr_max = df["Submission Date"].max().date()
    curr_year_start = date(curr_max.year, 1, 1)

    with c_30:
        if st.button("30d"):
            st.session_state['date_range'] = (curr_max - timedelta(days=29), curr_max)
            st.rerun()
    with c_90:
        if st.button("90d"):
            st.session_state['date_range'] = (curr_max - timedelta(days=89), curr_max)
            st.rerun()
    with c_180:
        if st.button("180d"):
            st.session_state['date_range'] = (curr_max - timedelta(days=179), curr_max)
            st.rerun()
    with c_ytd:
        if st.button("YTD"):
            st.session_state['date_range'] = (curr_year_start, curr_max)
            st.rerun()

    # Apply Date Filter
    start_date, end_date = st.session_state['date_range']
    period_df = df_filtered[
        (df_filtered["Submission Date"].dt.date >= start_date) & 
        (df_filtered["Submission Date"].dt.date <= end_date)
    ]

    # --- CALCULATIONS ---
    # Pre-Period (Beginning) Logic
    period_start_ts = pd.Timestamp(start_date)
    new_before = df_filtered[(df_filtered["Status"] == "NEW") & (df_filtered["Submission Date"] < period_start_ts)]
    disc_before = df_filtered[(df_filtered["Status"] == "DISCONNECT") & (df_filtered["Submission Date"] < period_start_ts)]
    active_start_ids = set(new_before["Customer Name"]) - set(disc_before["Customer Name"])
    
    beg_cust = len(active_start_ids)
    # Estimate Beginning MRC (Sum of MRC of currently active customers at start)
    # Note: This is an estimation based on last known MRC from the "NEW" record. 
    # Ideal world: you have a snapshot. Real world: we sum the NEW mrc of active customers.
    beg_mrc = new_before[new_before["Customer Name"].isin(active_start_ids)]["MRC"].sum()

    # In-Period Logic
    new_in = period_df[period_df["Status"] == "NEW"]
    churn_in = period_df[period_df["Status"] == "DISCONNECT"]
    
    count_new = new_in["Customer Name"].nunique()
    count_churn = churn_in["Customer Name"].nunique()
    mrc_new = new_in["MRC"].sum()
    mrc_churn = churn_in["MRC"].sum()
    
    net_mrc = mrc_new - mrc_churn
    
    # --- HERO SECTION (The Big Green/Red Card + 4 Grid) ---
    st.markdown("<br>", unsafe_allow_html=True)
    
    hero_col_left, hero_col_right = st.columns([1.8, 1.2])
    
    # LEFT: Net MRC Big Box
    with hero_col_left:
        net_color = "hero-green" if net_mrc >= 0 else "hero-red"
        net_sign = "+" if net_mrc >= 0 else "-"
        st.markdown(f"""
        <div class="dashboard-card" style="height: 280px; display:flex; flex-direction:column; justify-content:center;">
            <div class="metric-label">Net MRC</div>
            <div class="hero-big-value {net_color}">{net_sign}${abs(net_mrc):,.0f}</div>
            <div class="metric-sub" style="margin-top:10px;">Period: {start_date} → {end_date}</div>
        </div>
        """, unsafe_allow_html=True)

    # RIGHT: 2x2 Grid
    with hero_col_right:
        r1_c1, r1_c2 = st.columns(2)
        r2_c1, r2_c2 = st.columns(2)
        
        # Helper to draw small card
        def small_card(label, val, prefix=""):
            return f"""
            <div class="dashboard-card" style="padding: 15px; margin-bottom: 10px; height: 130px;">
                <div class="metric-label">{label}</div>
                <div class="metric-value" style="font-size: 1.4rem;">{prefix}{val}</div>
            </div>
            """
            
        with r1_c1:
            st.markdown(small_card("Beginning Customers", f"{beg_cust:,}"), unsafe_allow_html=True)
        with r1_c2:
            st.markdown(small_card("Beginning MRC", f"{beg_mrc:,.0f}", "$"), unsafe_allow_html=True)
        with r2_c1:
            # New Customers (Green text for value)
            st.markdown(f"""
            <div class="dashboard-card" style="padding: 15px; margin-bottom: 0px; height: 130px;">
                <div class="metric-label">New Customers</div>
                <div class="metric-value" style="font-size: 1.4rem; color: #3FB950;">+{count_new}</div>
            </div>
            """, unsafe_allow_html=True)
        with r2_c2:
            # Churned Customers (Red text for value)
            st.markdown(f"""
            <div class="dashboard-card" style="padding: 15px; margin-bottom: 0px; height: 130px;">
                <div class="metric-label">Churned Customers</div>
                <div class="metric-value" style="font-size: 1.4rem; color: #F85149;">-{count_churn}</div>
            </div>
            """, unsafe_allow_html=True)

    # --- QUICK INSIGHTS SECTION ---
    st.markdown("<h2 style='font-family:serif; font-size: 2rem; margin-top: 30px; margin-bottom: 10px;'>Quick insights</h2>", unsafe_allow_html=True)
    st.markdown("<p style='color: #8B949E; margin-bottom: 25px;'>A fast read of what changed — best used before deep dives.</p>", unsafe_allow_html=True)
    
    # Calculate Insights
    # 1. Top Churn Reason
    top_reason = "—"
    reason_sub = "No churn data"
    if not churn_in.empty:
        top_reason = churn_in["Reason"].value_counts().idxmax()
        count = churn_in["Reason"].value_counts().max()
        reason_sub = f"{count} customers lost"

    # 2. Largest Loss
    loss_name = "—"
    loss_sub = "No single loss"
    if not churn_in.empty:
        worst = churn_in.loc[churn_in["MRC"].idxmax()]
        loss_name = str(worst.get("Customer Name", "Unknown"))[:20]
        loss_sub = f"-${worst['MRC']:,.0f} MRC"

    # 3. Biggest Win
    win_name = "—"
    win_sub = "No major win"
    if not new_in.empty:
        best = new_in.loc[new_in["MRC"].idxmax()]
        win_name = str(best.get("Customer Name", "Unknown"))[:20]
        win_sub = f"+${best['MRC']:,.0f} MRC"
    
    # 4. Fastest Location
    loc_name = "—"
    loc_sub = "No growth leader"
    if not new_in.empty:
        loc_name = new_in["Location"].value_counts().idxmax()
        l_count = new_in["Location"].value_counts().max()
        loc_sub = f"+{l_count} new customers"

    # Draw the 4 Insight Cards
    ic1, ic2, ic3, ic4 = st.columns(4)
    
    def draw_insight(title, icon_char, main_text, sub_text):
        return f"""
        <div class="insight-box">
            <div class="metric-label">{title}</div>
            <div class="insight-icon">{icon_char}</div>
            <div style="margin-top:auto;">
                <div style="font-size: 1.1rem; font-weight: 700; color: white; margin-bottom: 4px;">{main_text}</div>
                <div style="font-size: 0.8rem; color: #8B949E;">{sub_text}</div>
            </div>
        </div>
        """
    
    with ic1:
        st.markdown(draw_insight("Top churn reason", "🔥", top_reason, reason_sub), unsafe_allow_html=True)
    with ic2:
        st.markdown(draw_insight("Largest single loss", "📉", loss_name, loss_sub), unsafe_allow_html=True)
    with ic3:
        st.markdown(draw_insight("Biggest new win", "🏆", win_name, win_sub), unsafe_allow_html=True)
    with ic4:
        st.markdown(draw_insight("Fastest-growing location", "⚡", loc_name, loc_sub), unsafe_allow_html=True)

    st.divider()

    # --- CHARTS SECTION (Keeping original logic, updated visuals) ---
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Monthly Net MRR Trend")
        monthly_new = df_filtered[df_filtered["Status"]=="NEW"].set_index("Submission Date").resample("ME")["MRC"].sum()
        monthly_churn = df_filtered[df_filtered["Status"]=="DISCONNECT"].set_index("Submission Date").resample("ME")["MRC"].sum()
        
        trend_df = pd.DataFrame({"New": monthly_new, "Lost": monthly_churn}).fillna(0)
        trend_df["Net"] = trend_df["New"] - trend_df["Lost"]
        trend_df = trend_df.tail(12)
        
        fig = px.bar(trend_df, y="Net", x=trend_df.index, color="Net", 
                     color_continuous_scale=["#F85149", "#3FB950"])
        fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font_color="#8B949E")
        st.plotly_chart(fig, use_container_width=True)
        
    with c2:
        st.subheader("Churn by Competitor")
        if not churn_in.empty:
            competitors = {"Fidium": "Fidium", "Spectrum": "Spectrum", "Starlink": "Starlink", "CCI": "CCI", "GWI": "GWI", "Other": "Other"}
            comp_data = []
            for label, keyword in competitors.items():
                mask = churn_in["Reason"].astype(str).str.contains(keyword, case=False, na=False)
                if mask.sum() > 0:
                    comp_data.append({"Competitor": label, "Count": int(mask.sum())})
            if comp_data:
                cdf = pd.DataFrame(comp_data)
                fig_pie = px.pie(cdf, names="Competitor", values="Count", hole=0.5, color_discrete_sequence=px.colors.sequential.RdBu)
                fig_pie.update_layout(paper_bgcolor="rgba(0,0,0,0)", font_color="#8B949E")
                st.plotly_chart(fig_pie, use_container_width=True)
            else:
                st.info("No competitor churn detected.")
        else:
            st.info("No churn data.")

    # --- DATA TABLE ---
    st.subheader("Churned Customers Detail")
    churn_detail = build_churn_detail(churn_in)
    if not churn_detail.empty:
        st.dataframe(
            churn_detail.style.format({"MRC Lost": "${:,.2f}"}),
            use_container_width=True,
            height=400
        )
    else:
        st.info("No churn details for this period.")

if __name__ == "__main__":
    run_dashboard()
