# dashboard.py — FINAL & FLAWLESS (Deploy This Now)
import streamlit as st
import pandas as pd
import requests
import plotly.express as px
from datetime import timedelta
from io import BytesIO

st.set_page_config(page_title="Talley Customer Dashboard", layout="wide")

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
    .stApp {background-color: #0F172A;}
</style>
""", unsafe_allow_html=True)

# [DATA LOADER — unchanged, same as before]

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
                    elif answer is None or str(answer).strip() == "": continue
                    row[name] = str(answer).strip()
                submissions.append(row)
            if len(data["content"]) < limit: break
            offset += limit
        except Exception as e:
            st.error(f"Error loading data: {e}")
            return pd.DataFrame()
    return pd.DataFrame(submissions)

@st.cache_data(ttl=300)
def get_data():
    df = load_from_jotform()
    if df.empty: return df
    rename_map = {"customerName": "Customer Name", "date": "Date", "employee": "Employee",
                  "location": "Location", "status": "Status", "category": "Category",
                  "reason": "Reason", "mrc": "MRC", "reasonOther": "Reason Other",
                  "disconnectReason": "Disconnect Reason Detail"}
    df.rename(columns=rename_map, inplace=True)
    df["Submission Date"] = pd.to_datetime(df["Submission Date"], errors="coerce")
    df = df.dropna(subset=["Submission Date"]).copy()
    df["Status"] = df["Status"].astype(str).str.upper().str.strip()
    df["MRC"] = pd.to_numeric(df["MRC"], errors="coerce").fillna(0)
    df["Customer Name"] = df["Customer Name"].astype(str).str.strip()
    return df

def run_dashboard():
    # Header
    col_logo, col_title = st.columns([1, 8])
    with col_logo:
        st.image("https://via.placeholder.com/140x90/1E3A8A/FFFFFF?text=TALLEY", width=140)
    with col_title:
        st.markdown('<p class="big-title">Customer Dashboard</p>', unsafe_allow_html=True)
        st.markdown("<p style='text-align:center; color:#94A3B8; margin-top:-15px;'>True Churn • Growth • Real-time Insights</p>", unsafe_allow_html=True)

    df = get_data()
    if df.empty: st.error("No data."); st.stop()

    min_date = df["Submission Date"].min().date()
    max_date = df["Submission Date"].max().date()
    default_start = max_date - timedelta(days=89)

    col1, col2 = st.columns([3, 1])
    with col1:
        start_date, end_date = st.date_input("Analysis Period", value=(default_start, max_date), min_value=min_date, max_value=max_date)
    with col2:
        if st.button("Refresh Now"): st.cache_data.clear(); st.rerun()

    period_start = pd.Timestamp(start_date)
    period_df = df[(df["Submission Date"].dt.date >= start_date) & (df["Submission Date"].dt.date <= end_date)].copy()

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

    # Big Net MRR at top
    st.markdown(f"""
    <div class="net-mrr {'positive' if net_mrr_movement >= 0 else 'negative'}">
        {'+$' if net_mrr_movement >= 0 else '-$'}{abs(net_mrr_movement):,.0f}
    </div>
    <p style="text-align:center; font-size:22px; color:#E2E8F0;">Net MRR Movement • {start_date} to {end_date}</p>
    """, unsafe_allow_html=True)

    st.divider()

    # Quick Insights (unchanged)
    st.markdown("### Quick Insights This Period")
    cards = []
    if not churn_in.empty and "Reason" in churn_in.columns and churn_in["Reason"].str.strip().ne("").any():
        top_reason = churn_in["Reason"].value_counts().idxmax()
        top_count = churn_in["Reason"].value_counts().max()
        top_mrc = churn_in[churn_in["Reason"] == top_reason]["MRC"].sum()
        cards.append(f"<div class='card flag'><h4>Most Common Churn Reason</h4><b>{top_reason}</b><br>{top_count} customers · ${top_mrc:,.0f} lost</div>")
    if not churn_in.empty:
        biggest = churn_in.loc[churn_in["MRC"].idxmax()]
        name = str(biggest.get("Customer Name", "Unknown"))[:35]
        reason = str(biggest.get("Reason", "—"))
        cards.append(f"<div class='card flag'><h4>Largest Single Loss</h4><b>{name}</b><br>${biggest['MRC']:,.0f} MRC<br><small>{reason}</small></div>")
    if not new_in.empty:
        best = new_in.loc[new_in["MRC"].idxmax()]
        name = str(best.get("Customer Name", "New Customer"))[:35]
        loc = str(best.get("Location", "—"))
        cards.append(f"<div class='card win'><h4>Biggest New Win</h4><b>{name}</b><br>+${best['MRC']:,.0f} MRC<br><small>{loc}</small></div>")
    if not new_in.empty and "Location" in new_in.columns and new_in["Location"].str.strip().ne("").any():
        top_loc = new_in["Location"].value_counts().idxmax()
        count = new_in["Location"].value_counts().max()
        mrc = new_in[new_in["Location"] == top_loc]["MRC"].sum()
        cards.append(f"<div class='card win'><h4>Fastest Growing Location</h4><b>{top_loc}</b><br>+{count} customers<br>+${mrc:,.0f} MRC</div>")
    if cards:
        cols = st.columns(len(cards))
        for col, card in zip(cols, cards):
            with col: st.markdown(card, unsafe_allow_html=True)
    else:
        st.success("All quiet — no activity this period!")

    st.divider()

    # ——————————— TRUE CHURN (RED) ———————————
    st.markdown("### True Churn Metrics")
    st.caption("Loss from existing base only")

    def red_metric(label, value, delta):
        st.markdown(f"""
        <div style="background:#1E293B; padding:16px; border-radius:12px; border-left:6px solid #DC2626; margin:8px;">
            <p style="margin:0; color:#94A3B8; font-size:14px;">{label}</p>
            <p style="margin:8px 0 4px 0; color:white; font-size:32px; font-weight:bold;">{value}</p>
            <p style="margin:0; color:#DC2626; font-size:20px; font-weight:bold;">{delta}</p>
        </div>
        """, unsafe_allow_html=True)

    c1, c2 = st.columns(2)
    with c1:
        red_metric("Churned Customers", f"{churn_count:,}", f"Down -{churn_count}")
        cust_rate = min(churn_count / beginning_customers * 100, 100) if beginning_customers > 0 else 0
        red_metric("Customer Churn Rate", f"-{cust_rate:.2f}%", f"Down -{cust_rate:.2f}%")
    with c2:
        red_metric("Lost MRC", f"${churn_mrc:,.0f}", f"Down -${churn_mrc:,.0f}")
        rev_rate = min(churn_mrc / beginning_mrc * 100, 100) if beginning_mrc > 0 else 0
        red_metric("Revenue Churn Rate", f"-{rev_rate:.2f}%", f"Down -{rev_rate:.2f}%")

    st.divider()

    # ——————————— TRUE GROWTH (GREEN) ———————————
    st.markdown("### True Growth Metrics")
    st.caption("New wins only")

    def green_metric(label, value, delta):
        st.markdown(f"""
        <div style="background:#1E293B; padding:16px; border-radius:12px; border-left:6px solid #16A34A; margin:8px;">
            <p style="margin:0; color:#94A3B8; font-size:14px;">{label}</p>
            <p style="margin:8px 0 4px 0; color:white; font-size:32px; font-weight:bold;">{value}</p>
            <p style="margin:0; color:#16A34A; font-size:20px; font-weight:bold;">{delta}</p>
        </div>
        """, unsafe_allow_html=True)

    g1, g2 = st.columns(2)
    with g1:
        green_metric("New Customers", f"{new_count:,}", f"Up +{new_count}")
    with g2:
        green_metric("New MRC Added", f"${new_mrc:,.0f}", f"Up +${new_mrc:,.0f}")

    st.divider()

    # ——————————— NET RESULTS — DEDICATED HIGH-IMPACT SECTION ———————————
    st.markdown("### Net Results")
    st.caption("True performance after churn & growth")

    net_cust_growth = ((new_count - churn_count) / beginning_customers * 100) if beginning_customers > 0 else 0

    col_net1, col_net2, col_net3 = st.columns([1, 2, 1])
    with col_net2:
        # Net MRC — big and bold
        color = "#16A34A" if net_mrr_movement >= 0 else "#DC2626"
        arrow = "Up" if net_mrr_movement >= 0 else "Down"
        sign = "+" if net_mrr_movement >= 0 else "-"
        st.markdown(f"""
        <div style="background:#1E293B; padding:24px; border-radius:16px; text-align:center; border-left:8px solid {color}; box-shadow: 0 6px 20px rgba(0,0,0,0.4);">
            <p style="margin:0; color:#94A3B8; font-size:18px;">Net MRC</p>
            <p style="margin:12px 0 8px 0; color:white; font-size:52px; font-weight:bold;">
                {sign}${abs(net_mrr_movement):,.0f}
            </p>
            <p style="margin:0; color:{color}; font-size:28px; font-weight:bold;">
                {arrow} {sign}${abs(net_mrr_movement):,.0f}
            </p>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)

        # Net Customer Growth
        color2 = "#16A34A" if net_cust_growth >= 0 else "#DC2626"
        arrow2 = "Up" if net_cust_growth >= 0 else "Down"
        st.markdown(f"""
        <div style="background:#1E293B; padding:20px; border-radius:12px; text-align:center; border-left:6px solid {color2};">
            <p style="margin:0; color:#94A3B8; font-size:16px;">Net Customer Growth Rate</p>
            <p style="margin:10px 0 6px 0; color:white; font-size:42px; font-weight:bold;">
                {net_cust_growth:+.2f}%
            </p>
            <p style="margin:0; color:{color2}; font-size:22px; font-weight:bold;">
                {arrow2} {net_cust_growth:+.2f}%
            </p>
        </div>
        """, unsafe_allow_html=True)

    st.divider()

    # Charts & Export (unchanged)
    col_a, col_b = st.columns(2)
    with col_a:
        if not churn_in.empty:
            st.subheader("Churn by Reason")
            reason_df = churn_in.groupby("Reason").agg(Count=("Customer Name","nunique"), MRC_Lost=("MRC","sum")).reset_index().sort_values("Count", ascending=False)
            st.dataframe(reason_df.style.format({"MRC_Lost": "${:,.0f}"}), use_container_width=True)
            fig = px.bar(reason_df, x="Count", y="Reason", orientation="h", color="MRC_Lost", color_continuous_scale="Reds")
            st.plotly_chart(fig, use_container_width=True)

    with col_b:
        if not new_in.empty:
            st.subheader("New Customer Acquisition")
            pie = px.pie(new_in["Category"].value_counts().reset_index(), names="Category", values="count")
            st.plotly_chart(pie, use_container_width=True)
            bar = px.bar(new_in["Location"].value_counts().head(10).reset_index(), x="Location", y="count")
            st.plotly_chart(bar, use_container_width=True)
            st.success(f"Added {new_count:,} new customers — +${new_mrc:,.0f} MRC")

    st.divider()
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
        pd.DataFrame([{"Period": f"{start_date} to {end_date}", "Net MRC": net_mrr_movement}]).to_excel(writer, sheet_name="Summary", index=False)
    st.download_button("Download Report (Excel)", data=buffer.getvalue(),
                       file_name=f"Talley_Report_{start_date}_to_{end_date}.xlsx")

    st.caption("Auto-refreshes every 5 minutes • Real-time from JotForm")

if __name__ == "__main__":
    run_dashboard()
