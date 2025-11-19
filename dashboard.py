# dashboard.py
import streamlit as st
import pandas as pd
import requests
import plotly.express as px
from datetime import timedelta

st.set_page_config(page_title="Talley Customer Dashboard", layout="wide")

# ===============================================
# SAFE JOTFORM DATA LOADER
# ===============================================
def load_from_jotform():
    api_key = "22179825a79dba61013e4fc3b9d30fa4"
    form_id = "240073839937062"
    url = f"https://api.jotform.com/form/{form_id}/submissions"
    submissions = []
    offset = 0
    limit = 1000

    while True:
        params = {
            "apiKey": api_key,
            "limit": limit,
            "offset": offset,
            "orderby": "created_at"
        }
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
                answers = item.get("answers", {})
                for ans in answers.values():
                    name = ans.get("name") or ans.get("text") or "unknown"
                    answer = ans.get("answer")

                    if isinstance(answer, dict):
                        parts = []
                        for v in answer.values():
                            if isinstance(v, list):
                                parts.extend(v)
                            else:
                                parts.append(str(v))
                        answer = ", ".join(parts) if parts else ""
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


# ===============================================
# CACHED & CLEANED DATA
# ===============================================
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
    df["Status"] = df["Status"].astype(str).str.upper().str.strip()
    df["MRC"] = pd.to_numeric(df["MRC"], errors="coerce").fillna(0)
    df["Customer Name"] = df["Customer Name"].astype(str).str.strip()

    return df


# ===============================================
# MAIN DASHBOARD FUNCTION
# ===============================================
def run_dashboard():
    st.title("Talley Customer Dashboard")
    st.markdown("### True Churn + Growth Analytics")

    with st.spinner("Loading latest data from JotForm..."):
        df = get_data()

    if df.empty:
        st.error("No data loaded. Please check your JotForm API key and form ID.")
        st.stop()

    min_date = df["Submission Date"].min().date()
    max_date = df["Submission Date"].max().date()
    default_start = max_date - timedelta(days=29)
    if default_start < min_date:
        default_start = min_date

    col1, col2 = st.columns([3, 1])
    with col1:
        start_date, end_date = st.date_input(
            "Select analysis period",
            value=(default_start, max_date),
            min_value=min_date,
            max_value=max_date,
        )
    with col2:
        if st.button("Refresh now"):
            st.cache_data.clear()
            st.rerun()

    period_start = pd.Timestamp(start_date)
    period_df = df[
        (df["Submission Date"].dt.date >= start_date) &
        (df["Submission Date"].dt.date <= end_date)
    ].copy()

    # ==================== TRUE CHURN CALCULATION ====================
    new_before = df[(df["Status"] == "NEW") & (df["Submission Date"] <= period_start)]
    disc_before = df[(df["Status"] == "DISCONNECT") & (df["Submission Date"] <= period_start)]
    active_customers_start = set(new_before["Customer Name"]) - set(disc_before["Customer Name"])

    beginning_customers = len(active_customers_start)
    beginning_mrc = new_before[new_before["Customer Name"].isin(active_customers_start)]["MRC"].sum()

    new_in_period = period_df[period_df["Status"] == "NEW"]
    churn_in_period = period_df[period_df["Status"] == "DISCONNECT"]

    new_count = new_in_period["Customer Name"].nunique()
    churn_count = churn_in_period["Customer Name"].nunique()
    new_mrc = new_in_period["MRC"].sum()
    churn_mrc = churn_in_period["MRC"].sum()

    ending_customers = beginning_customers + new_count - churn_count
    churn_rate = (churn_count / beginning_customers * 100) if beginning_customers else 0
    growth_rate = ((ending_customers - beginning_customers) / beginning_customers * 100) if beginning_customers else 0
    rev_churn_rate = (churn_mrc / beginning_mrc * 100) if beginning_mrc > 0 else 0

    # ==================== NEW: DISCONNECTS BY REASON KPIs ====================
    st.markdown("### Disconnect Summary – Selected Period")

    if not churn_in_period.empty:
        reason_summary = (
            churn_in_period.groupby("Reason")
            .agg(
                Customers=("Customer Name", "nunique"),
                MRC_Lost=("MRC", "sum")
            )
            .reset_index()
            .sort_values("Customers", ascending=False)
        )

        total_churned = reason_summary["Customers"].sum()
        total_mrc_lost = reason_summary["MRC_Lost"].sum()
        top_reason = reason_summary.iloc[0]["Reason"]
        top_reason_count = reason_summary.iloc[0]["Customers"]
        top_reason_mrc = reason_summary.iloc[0]["MRC_Lost"]

        # Big KPI row
        k1, k2, k3, k4 = st.columns(4)
        k1.metric("Total Customers Lost", f"{total_churned:,}")
        k2.metric("Total MRC Lost", f"${total_mrc_lost:,.0f}")
        k3.metric("Most Common Reason", top_reason)
        k4.metric("Lost to Top Reason", f"{top_reason_count:,}", delta=f"${top_reason_mrc:,.0f} MRC")

        # Detailed breakdown
        st.dataframe(
            reason_summary.style.format({"MRC_Lost": "${:,.0f}"}),
            use_container_width=True
        )

        fig = px.bar(
            reason_summary,
            x="Customers",
            y="Reason",
            orientation="h",
            color="MRC_Lost",
            color_continuous_scale="Reds",
            title="All Disconnects by Reason (Count + MRC Impact)",
            labels={"Customers": "Customers Lost", "MRC_Lost": "MRC Lost ($)"}
        )
        fig.update_layout(height=max(400, len(reason_summary) * 45))
        st.plotly_chart(fig, use_container_width=True)

    else:
        st.info("No disconnects in the selected period.")

    st.divider()

    # ==================== TRUE CHURN METRICS ====================
    st.markdown("### True Churn Metrics (vs Beginning Base)")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Beginning Customers", f"{beginning_customers:,}")
    c2.metric("New Customers", f"{new_count:,}", delta=f"+{new_count}")
    c3.metric("Churned Customers", f"{churn_count:,}", delta=f"-{churn_count}")
    c4.metric("Ending Customers", f"{ending_customers:,}", delta=f"{ending_customers - beginning_customers:+,}")

    c5, c6, c7, c8 = st.columns(4)
    c5.metric("Customer Churn Rate", f"{churn_rate:.2f}%", delta_color="inverse")
    c6.metric("Net Growth Rate", f"{growth_rate:+.2f}%")
    c7.metric("Lost MRC", f"${churn_mrc:,.0f}", delta_color="inverse")
    c8.metric("Revenue Churn Rate", f"{rev_churn_rate:.2f}%", delta_color="inverse")

    with st.expander("How is True Churn calculated?"):
        st.caption(f"""
        • Beginning = Active customers on/before **{start_date}** (no prior disconnect)
        • Churned = Customers who submitted a DISCONNECT in the selected period
        • Rates are calculated against the true starting base
        """)

    # ==================== NEW CUSTOMERS SECTION ====================
    if not new_in_period.empty:
        st.divider()
        st.subheader("New Customer Acquisition")
        col_a, col_b = st.columns(2)
        with col_a:
            cat_pie = new_in_period["Category"].value_counts().reset_index()
            fig_pie = px.pie(cat_pie, names="Category", values="count", title="By Category")
            st.plotly_chart(fig_pie, use_container_width=True)
        with col_b:
            loc_bar = new_in_period["Location"].value_counts().head(15).reset_index()
            fig_bar = px.bar(loc_bar, x="Location", y="count", title="Top 15 Locations")
            st.plotly_chart(fig_bar, use_container_width=True)
        st.success(f"Added {new_count:,} new customers — +${new_mrc:,.0f} MRC")

    st.caption("Auto-refreshes every 5 minutes • Source: JotForm")


# ===============================================
# RUN
# ===============================================
if __name__ == "__main__":
    run_dashboard()
