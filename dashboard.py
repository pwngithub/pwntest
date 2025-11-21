# dashboard.py — FINAL VERSION: TRUE CHURN IS 100% RED
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

# [DATA LOADER — unchanged]
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

    st.markdown(f"""
    <div class="net-mrr {'positive' if net_mrr_movement >= 0 else 'negative'}">
        {'+$' if net_mrr_movement >= 0 else '-$'}{abs(net_mrr_movement):,.0f}
    </div>
    <p style="text-align:center; font-size:22px; color:#E2E8F0;">Net MRR Movement • {start_date} to {end_date}</p>
    """, unsafe_allow_html=True)

    st.divider()

    # [Quick Insights — unchanged]

    st.divider()

    # TRUE CHURN & GROWTH
    col_left, col_right = st.columns(2)

    # TRUE CHURN — 100% RED, NO GREEN EVER
    with col_left:
        st.markdown("### True Churn Metrics")
        st.caption("Loss from existing base only")

        def red_metric(label, value, delta):
            st.markdown(f"""
            <div style="background:#1E293B; padding:15px; border-radius:10px; border-left:6px solid #DC2626; margin-bottom:15px;">
                <p style="margin:0; color:#94A3B8; font-size:14px;">{label}</p>
                <p style="margin:5px 0 8px 0; color:white; font-size:28px; font-weight:bold;">{value}</p>
                <p style="margin:0; color:#DC2626; font-size:18px; font-weight:bold;">{delta}</p>
            </div>
            """, unsafe_allow_html=True)

        c1, c2 = st.columns(2)
        with c1:
            red_metric("Churned Customers", f"{churn_count:,}", f"↓ -{churn_count}")
            cust_churn_rate = min(churn_count / beginning_customers * 100, 100) if beginning_customers > 0 else 0
            red_metric("Customer Churn Rate", f"-{cust_churn_rate:.2f}%", f"↓ -{cust_churn_rate:.2f}%")
        with c2:
            red_metric("Lost MRC", f"${churn_mrc:,.0f}", f"↓ -${churn_mrc:,.0f}")
            rev_churn_rate = min(churn_mrc / beginning_mrc * 100, 100) if beginning_mrc > 0 else 0
            red_metric("Revenue Churn Rate", f"-{rev_churn_rate:.2f}%", f"↓ -{rev_churn_rate:.2f}%")

    # TRUE GROWTH — keeps normal green/red logic
    with col_right:
        st.markdown("### True Growth Metrics")
        st.caption("New wins + net recurring revenue impact")
        g1, g2, g3 = st.columns(3)
        g1.metric("New Customers", f"{new_count:,}", delta=f"+{new_count}")
        g2.metric("New MRC Added", f"${new_mrc:,.0f}", delta=f"+${new_mrc:,.0f}")
        g3.metric("Net MRC", f"{'+' if net_mrr_movement >= 0 else '-'}${abs(net_mrr_movement):,.0f}",
                  delta=f"{'+' if net_mrr_movement >= 0 else '-'}${abs(net_mrr_movement):,.0f}",
                  delta_color="normal" if net_mrr_movement >= 0 else "inverse")

    st.divider()
    st.caption("Auto-refreshes every 5 minutes • Real-time from JotForm")

if __name__ == "__main__":
    run_dashboard()
