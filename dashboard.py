# dashboard.py   ← save exactly with this name if using Tally / Streamlit Community Cloud
import streamlit as st
import pandas as pd
import requests
import plotly.express as px
from datetime import timedelta

# ==================================================================
# CONFIG
# ==================================================================
st.set_page_config(page_title="Talley Customer Dashboard", layout="wide")

# ==================================================================
# SAFE JOTFORM LOADER – handles dicts/lists/checkboxes perfectly
# ==================================================================
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
                row = {
                    "Submission Date": item["created_at"],
                    "Submission ID": item["id"]
                }

                for ans in item.get("answers", {}).values():
                    name = ans.get("name") or ans.get("text") or "field"
                    answer = ans.get("answer")

                    # Fix complex answers (checkboxes, etc.)
                    if isinstance(answer, (dict, list)):
                        if isinstance(answer, dict):
                            parts = []
                            for v in answer.values():
                                if isinstance(v, list):
                                    parts.extend(v)
                                else:
                                    parts.append(str(v))
                            answer = ", ".join(parts) if parts else str(answer)
                        else:
                            answer = ", ".join(str(x) for x in answer)
                    if not answer:
                        continue

                    row[name] = answer

                submissions.append(row)

            if len(data["content"]) < limit:
                break
            offset += limit

        except Exception as e:
            st.error(f"Error loading JotForm data: {e}")
            return pd.DataFrame()

    return pd.DataFrame(submissions)


# ==================================================================
# CACHED & CLEANED DATA
# ==================================================================
@st.cache_data(ttl=300)  # 5-minute cache
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
    df["Status"] = df["Status"].astype(str).str.upper().str.strip()
    df["MRC"] = pd.to_numeric(df["MRC"], errors="coerce").fillna(0)
    df["Customer Name"] = df["Customer Name"].astype(str).str.strip()

    return df


# ==================================================================
# MAIN FUNCTION – this is the one that runs
# ==================================================================
def run_dashboard():          # ← this name is required by many hosting platforms
    st.title("Talley Customer Dashboard")
    st.markdown("**True Churn + Growth Analytics**")

    with st.spinner("Loading data from JotForm..."):
        df = get_data()

    if df.empty:
        st.error("No data loaded. Check API key and form ID.")
        st.stop()

    # Date selector
    min_date = df["Submission Date"].min().date()
    max_date = df["Submission Date"].max().date()

    default_start = max_date - timedelta(days=29)
    if default_start < min_date:
        default_start = min_date

    col1, col2 = st.columns([3, 1])
    with col1:
        start_date, end_date = st.date_input(
            "Select period",
            value=(default_start, max_date),
            min_value=min_date,
            max_value=max_date,
        )
    with col2:
        if st.button("Refresh now"):
            st.cache_data.clear()
            st.rerun()

    period_start = pd.Timestamp(start_date)

    # Filter period
    period_df = df[(df["Submission Date"].dt.date >= start_date) & (df["Submission Date"].dt.date <= end_date)].copy()

    # ========================= TRUE CHURN =========================
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

    ending_customers = beginning_customers + new_count - churn_count

    churn_rate = (churn_count / beginning_customers * 100) if beginning_customers else 0
    growth_rate = ((ending_customers - beginning_customers) / beginning_customers * 100) if beginning_customers else 0
    rev_churn = (churn_mrc / beginning_mrc * 100) if beginning_mrc else 0

    # ========================= DISPLAY =========================
    st.markdown("### True Churn Metrics")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Beginning", f"{beginning_customers:,}")
    c2.metric("New", f"{new_count:,}", delta=f"+{new_count}")
    c3.metric("Churned", f"{churn_count:,}", delta=f"-{churn_count}")
    c4.metric("Ending", f"{ending_customers:,}", delta=f"{ending_customers-beginning_customers:+,}")

    c5, c6, c7, c8 = st.columns(4)
    c5.metric("Churn Rate", f"{churn_rate:.2f}%", delta_color="inverse")
    c6.metric("Net Growth", f"{growth_rate:+.2f}%")
    c7.metric("Lost MRC", f"${churn_mrc:,.0f}", delta_color="inverse")
    c8.metric("Revenue Churn", f"{rev_churn:.2f}%", delta_color="inverse")

    st.divider()

    # Churn by Reason
    if not churn_in.empty:
        reason = churn_in.groupby("Reason").agg(Count=("Customer Name","nunique"), MRC=("MRC","sum")).reset_index().sort_values("Count", ascending=False)
        st.subheader("Churn by Reason")
        st.dataframe(reason, use_container_width=True)
        fig = px.bar(reason, x="Count", y="Reason", orientation="h", color="MRC", title="Churn Reasons")
        st.plotly_chart(fig, use_container_width=True)

    # New customers
    if not new_in.empty:
        st.subheader("New Customers")
        col a, col b = st.columns(2)
        with col a:
            pie = new_in["Category"].value_counts().reset_index()
            st.plotly_chart(px.pie(pie, names="Category", values="count", title="By Category"), use_container_width=True)
        with col b:
            bar = new_in["Location"].value_counts().head(15).reset_index()
            st.plotly_chart(px.bar(bar, x="Location", y="count", title="Top 15 Locations"), use_container_width=True)
        st.success(f"Added {new_count:,} new customers (+${new_mrc:,.0f} MRC)")

    st.caption("Refreshes every 5 min • Source: JotForm")


# ==================================================================
# REQUIRED FOR ALL HOSTING PLATFORMS (Streamlit Cloud, Tally, etc.)
# ==================================================================
if __name__ == "__main__":
    run_dashboard()        # ← this line makes it work everywhere
