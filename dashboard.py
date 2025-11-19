# dashboard.py
import streamlit as st
import pandas as pd
import requests
import plotly.express as px
from datetime import timedelta
from io import BytesIO

st.set_page_config(page_title="Talley Customer Dashboard", layout="wide")

# ——————————————— STYLING ———————————————
st.markdown("""
<style>
    .big-title {font-size: 42px !important; font-weight: bold; color: #1E3A8A; text-align: center;}
    .net-mrr {font-size: 60px !important; font-weight: bold; text-align: center; margin: 20px 0;}
    .positive {color: #16A34A !important;}
    .negative {color: #DC2626 !important;}
    .card {padding: 20px; border-radius: 12px; background: #F8FAFC; border-left: 6px solid; height: 160px;}
    .win  {border-left-color: #16A34A;}
    .flag {border-left-color: #DC2626;}
</style>
""", unsafe_allow_html=True)

# ===============================================
# DATA LOADER (unchanged)
# ===============================================
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
                        parts = [str(v) if not isinstance(v, list) else ", ".join(v) for v in answer.values()]
                        answer = ", ".join(filter(None, parts))
                    elif isinstance(answer, list):
                        answer = ", ".join(str(x) for x in answer)
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
        "customerName": "Customer Name", "date": "Date", "employee": "Employee",
        "location": "Location", "status": "Status", "category": "Category",
        "reason": "Reason", "mrc": "MRC", "reasonOther": "Reason Other",
        "disconnectReason": "Disconnect Reason Detail",
    }
    df.rename(columns=rename_map, inplace=True)
    df["Submission Date"] = pd.to_datetime(df["Submission Date"], errors="coerce")
    df = df.dropna(subset=["Submission Date"]).copy()
    df["Status"] = df["Status"].astype(str).str.upper().str.strip()
    df["MRC"] = pd.to_numeric(df["MRC"], errors="coerce").fillna(0)
    df["Customer Name"] = df["Customer Name"].astype(str).str.strip()
    return df


def run_dashboard():
    # Header
    col_logo, col_title = st.columns([1, 6])
    with col_logo:
        st.image("https://via.placeholder.com/120x80/1E3A8A/FFFFFF?text=TALLEY", width=120)  # ← replace with real logo
    with col_title:
        st.markdown('<p class="big-title">Customer Dashboard</p>', unsafe_allow_html=True)
        st.markdown("**True Churn + Growth Analytics** • Real-time from JotForm")

    df = get_data()
    if df.empty:
        st.error("No data loaded.")
        st.stop()

    min_date = df["Submission Date"].min().date()
    max_date = df["Submission Date"].max().date()
    default_start = max_date - timedelta(days=89)
    if default_start < min_date:
        default_start = min_date

    col1, col2 = st.columns([3, 1])
    with col1:
        start_date, end_date = st.date_input("Analysis period", value=(default_start, max_date),
                                             min_value=min_date, max_value=max_date)
    with col2:
        if st.button("Refresh now"):
            st.cache_data.clear()
            st.rerun()

    period_start = pd.Timestamp(start_date)
    period_df = df[(df["Submission Date"].dt.date >= start_date) & (df["Submission Date"].dt.date <= end_date)].copy()

    # Calculations
    new_before = df[(df["Status"] == "NEW") & (df["Submission Date"] <= period_start)]
    disc_before = df[(df["Status"] == "DISCONNECT") & (df["Submission Date"] <= period_start)]
    active_start = set(new_before["Customer Name"]) - set(disc_before["Customer Name"])

    beginning_customers = len(active_start)
    beginning_mrc = new_before[new_before["Customer Name"].isin(active_start)]["MRC"].sum()

    new_in = period_df[period_df["Status"] == "NEW"]
    churn_in = period_df[period_df["Status"] == "DISCONNECT"]

    new_count = new_in["Customer Name"].nunique()
    churn_count = churn_in["Customer Name"].nunique()
    new_mrc = new_in["MRC"].sum()
    churn_mrc = churn_in["MRC"].sum()

    net_mrr_movement = new_mrc - churn_mrc

    # Big Net MRR Number
    st.markdown(f"""
    <div class="net-mrr {'positive' if net_mrr_movement >= 0 else 'negative'}">
        {'+$' if net_mrr_movement >= 0 else '-$'}
        {abs(net_mrr_movement):,.0f}
    </div>
    <p style="text-align:center; font-size:20px; margin-top:-10px;">
        Net MRR Movement ({start_date} to {end_date})
    </p>
    """, unsafe_allow_html=True)

    st.divider()

    # QUICK INSIGHTS — now 100% guaranteed to show
    st.markdown("### Quick Insights This Period")
    c1, c2, c3, c4 = st.columns(4)

    # 1. Most common churn reason
    if not churn_in.empty and "Reason" in churn_in.columns:
        top_reason = churn_in["Reason"].value_counts().idxmax()
        top_reason_count = churn_in["Reason"].value_counts().max()
        top_reason_mrc = churn_in[churn_in["Reason"] == top_reason]["MRC"].sum()
        with c1:
            st.markdown(f"""
            <div class="card flag">
                <h4>Most Common Churn Reason</h4>
                <b>{top_reason or "—"}</b><br>
                {top_reason_count} customers · ${top_reason_mrc:,.0f} lost
            </div>
            """, unsafe_allow_html=True)
    else:
        with c1:
            st.markdown('<div class="card win"><h4>No Churn</h4>Congratulations! Zero disconnects this period</div>', unsafe_allow_html=True)

    # 2. Largest single loss
    if not churn_in.empty:
        biggest = churn_in.loc[churn_in["MRC"].idxmax()]
        with c2:
            st.markdown(f"""
            <div class="card flag">
                <h4>Largest Single Loss</h4>
                <b>{biggest["Customer Name"]}</b><br>
                ${biggest["MRC"]:,.0f} MRC<br>
                {biggest.get("Reason", "—")}
            </div>
            """, unsafe_allow_html=True)
    else:
        with c2:
            st.markdown('<div class="card win"><h4>No Losses</h4>All customers retained</div>', unsafe_allow_html=True)

    # 3. Biggest new win
    if not new_in.empty:
        best_new = new_in.loc[new_in["MRC"].idxmax()]
        with c3:
            st.markdown(f"""
            <div class="card win">
                <h4>Biggest New Win</h4>
                <b>{best_new["Customer Name"]}</b><br>
                +${best_new["MRC"]:,.0f} MRC<br>
                {best_new.get("Location", "")}
            </div>
            """, unsafe_allow_html=True)
    else:
        with c3:
            st.markdown('<div class="card"><h4>No New Customers</h4>(yet)</div>', unsafe_allow_html=True)

    # 4. Fastest growing location
    if not new_in.empty and "Location" in new_in.columns:
        top_loc = new_in["Location"].value_counts().idxmax()
        top_loc_count = new_in["Location"].value_counts().max()
        top_loc_mrc = new_in[new_in["Location"] == top_loc]["MRC"].sum()
        with c4:
            st.markdown(f"""
            <div class="card win">
                <h4>Fastest Growing Location</h4>
                <b>{top_loc}</b><br>
                +{top_loc_count} customers<br>
                +${top_loc_mrc:,.0f} MRC
            </div>
            """, unsafe_allow_html=True)
    else:
        with c4:
            st.markdown('<div class="card"><h4>No Location Data</h4>—</div>', unsafe_allow_html=True)

    st.divider()

    # Rest of dashboard (unchanged, only tiny fixes)
    col_left, col_right = st.columns(2)

    with col_left:
        st.markdown("### True Churn Metrics")
        st.caption("Losses from existing base")
        ch1, ch2 = st.columns(2)
        ch1.metric("Churned Customers", f"{churn_count:,}", delta=f"-{churn_count}")
        ch2.metric("Lost MRC", f"${churn_mrc:,.0f}", delta_color="inverse")
        ch1.metric("Customer Churn Rate", f"{(churn_count/beginning_customers*100):.2f}%" if beginning_customers else "0%", delta_color="inverse")
        ch2.metric("Revenue Churn Rate", f"{(churn_mrc/beginning_mrc*100):.2f}%" if beginning_mrc > 0 else "0%", delta_color="inverse")

    with col_right:
        st.markdown("### True Growth Metrics")
        st.caption("New customers & expansion")
        gr1, gr2 = st.columns(2)
        gr1.metric("New Customers", f"{new_count:,}", delta=f"+{new_count}")
        gr2.metric("New MRC Added", f"${new_mrc:,.0f}")
        gr1.metric("Net Customer Change", f"{new_count - churn_count:+,}")
        gr2.metric("Net Growth Rate", f"{((new_count - churn_count)/beginning_customers*100):+.2f}%" if beginning_customers else "N/A")

    st.divider()

    # Churn by Reason + New Customers
    col_a, col_b = st.columns(2)
    with col_a:
        if not churn_in.empty:
            st.subheader("Churn by Reason")
            reason_df = churn_in.groupby("Reason").agg(
                Count=("Customer Name", "nunique"),
                MRC_Lost=("MRC", "sum")
            ).reset_index().sort_values("Count", ascending=False)
            st.dataframe(reason_df.style.format({"MRC_Lost": "${:,.0f}"}), use_container_width=True)
            fig = px.bar(reason_df, x="Count", y="Reason", orientation="h", color="MRC_Lost",
                         color_continuous_scale="Reds", title="Churn Reasons")
            st.plotly_chart(fig, use_container_width=True)

    with col_b:
        if not new_in.empty:
            st.subheader("New Customer Acquisition")
            pie = px.pie(new_in["Category"].value_counts().reset_index(), names="Category", values="count", title="By Category")
            st.plotly_chart(pie, use_container_width=True)
            bar = px.bar(new_in["Location"].value_counts().head(10).reset_index(), x="Location", y="count", title="Top Locations")
            st.plotly_chart(bar, use_container_width=True)
            st.success(f"Added {new_count:,} new customers — +${new_mrc:,.0f} MRC")

    # Export
    st.divider()
    summary_df = pd.DataFrame([{
        "Period": f"{start_date} to {end_date}",
        "Net MRR Movement": net_mrr_movement,
        "New Customers": new_count, "Churned": churn_count,
        "New MRC": new_mrc, "Lost MRC": churn_mrc
    }])
    excel_buffer = BytesIO()
    with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
        summary_df.to_excel(writer, sheet_name="Summary", index=False)
        if not churn_in.empty:
            reason_df.to_excel(writer, sheet_name="Churn_by_Reason", index=False)
    st.download_button(
        label="Download Full Report (Excel)",
        data=excel_buffer.getvalue(),
        file_name=f"Talley_Report_{start_date}_to_{end_date}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

    st.caption("Auto-refreshes every 5 minutes • Source: JotForm")


if __name__ == "__main__":
    run_dashboard()
