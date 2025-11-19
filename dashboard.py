# dashboard.py
import streamlit as st
import pandas as pd
import requests
import plotly.express as px
from datetime import timedelta

# ------------------------------------------------------------------
# Fix the syntax error from the previous version
# ------------------------------------------------------------------
st.set_page_config(page_title="Talley Customer Dashboard", layout="wide")

# ------------------------------------------------------------------
# SAFE JOTFORM LOADER – handles dicts, lists, checkboxes, etc.
# ------------------------------------------------------------------
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

            if not data["content"]:
                break

            for item in data["content"]:
                row = {
                    "Submission Date": item["created_at"],
                    "Submission ID": item["id"]
                }

                for ans in item.get("answers", {}).values():
                    name = ans.get("name") or ans.get("text") or "unknown"
                    answer = ans.get("answer")

                    # ---- SAFE conversion of complex answer types ----
                    if isinstance(answer, dict):
                        # Checkboxes / multi-select
                        answer = ", ".join(answer.get(k, []) for k in answer if isinstance(answer[k], list))
                        if not answer:
                            answer = str(answer)
                    elif isinstance(answer, list):
                        answer = ", ".join(str(x) for x in answer)
                    elif answer is None or answer == "":
                        continue

                    row[name] = answer

                submissions.append(row)

            if len(data["content"]) < limit:
                break
            offset += limit

        except Exception as e:
            st.error(f"JotForm API error: {e}")
            return pd.DataFrame()

    return pd.DataFrame(submissions)


# ------------------------------------------------------------------
# CACHED & CLEANED DATA
# ------------------------------------------------------------------
@st.cache_data(ttl=300, show_spinner=False)  # refresh every 5 min
def get_data():
    df = load_from_jotform()
    if df.empty:
        return df

    # Rename columns to friendly names
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

    # Core cleaning
    df["Submission Date"] = pd.to_datetime(df["Submission Date"], errors="coerce")
    df = df.dropna(subset=["Submission Date"]).copy()
    df["Status"] = df["Status"].astype(str).str.upper().str.strip()
    df["MRC"] = pd.to_numeric(df["MRC"], errors="coerce").fillna(0)
    df["Customer Name"] = df["Customer Name"].astype(str).str.strip()

    return df


# ------------------------------------------------------------------
# MAIN DASHBOARD
# ------------------------------------------------------------------
def main():
    st.title("Talley Customer Dashboard")
    st.markdown("**True Churn + Growth Analytics**")

    with st.spinner("Fetching latest data from JotForm..."):
        df = get_data()

    if df.empty:
        st.error("No data received. Check your JotForm API key and form ID.")
        st.stop()

    # Date range selector
    min_date = df["Submission Date"].min().date()
    max_date = df["Submission Date"].max().date()

    default_start = max_date - timedelta(days=29)
    if default_start < min_date:
        default_start = min_date

    col1, col2 = st.columns([3, 1])
    with col1:
        start_date, end_date = st.date_input(
            "Analysis Period",
            value=(default_start, max_date),
            min_value=min_date,
            max_value=max_date,
        )
    with col2:
        if st.button("Force Refresh"):
            st.cache_data.clear()
            st.rerun()

    period_start = pd.Timestamp(start_date)
    period_end   = pd.Timestamp(end_date)

    # Filter data for the selected period
    period_df = df[
        (df["Submission Date"].dt.date >= start_date) &
        (df["Submission Date"].dt.date <= end_date)
    ].copy()

    # -------------------------- TRUE CHURN CALCULATION --------------------------
    # Customers active at the beginning of the period
    new_before    = df[(df["Status"] == "NEW") & (df["Submission Date"] <= period_start)]
    disc_before   = df[(df["Status"] == "DISCONNECT") & (df["Submission Date"] <= period_start)]

    active_start_names = set(new_before["Customer Name"]) - set(disc_before["Customer Name"])

    beginning_customers = len(active_start_names)
    beginning_mrc = new_before[new_before["Customer Name"].isin(active_start_names)]["MRC"].sum()

    # Activity during the period
    new_in_period  = period_df[period_df["Status"] == "NEW"]
    churn_in_period = period_df[period_df["Status"] == "DISCONNECT"]

    new_count   = new_in_period["Customer Name"].nunique()
    new_mrc     = new_in_period["MRC"].sum()
    churn_count = churn_in_period["Customer Name"].nunique()
    churn_mrc   = churn_in_period["MRC"].sum()

    ending_customers = beginning_customers + new_count - churn_count

    customer_churn_rate = (churn_count / beginning_customers * 100) if beginning_customers else 0
    net_growth_rate     = ((ending_customers - beginning_customers) / beginning_customers * 100) if beginning_customers else 0
    revenue_churn_rate  = (churn_mrc / beginning_mrc * 100) if beginning_mrc > 0 else 0

    # -------------------------- DISPLAY KPIs --------------------------
    st.markdown("### True Churn Metrics")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Beginning Customers", f"{beginning_customers:,}")
    c2.metric("New Customers", f"{new_count:,}", delta=f"+{new_count}")
    c3.metric("Churned Customers", f"{churn_count:,}", delta=f"-{churn_count}")
    c4.metric("Ending Customers", f"{ending_customers:,}", delta=f"{ending_customers - beginning_customers:+,}")

    c5, c6, c7, c8 = st.columns(4)
    c5.metric("Customer Churn Rate", f"{customer_churn_rate:.2f}%", delta_color="inverse")
    c6.metric("Net Growth Rate", f"{net_growth_rate:+.2f}%")
    c7.metric("Lost MRC", f"${churn_mrc:,.0f}", delta_color="inverse")
    c8.metric("Revenue Churn Rate", f"{revenue_churn_rate:.2f}%", delta_color="inverse")

    with st.expander("How is True Churn calculated?"):
        st.write(f"""
        - **Beginning Customers** = Customers who had a NEW record on/before **{start_date}** and no DISCONNECT by that date  
        - **Churned** = Customers with a DISCONNECT submission between {start_date} and {end_date}  
        - Rates are calculated against the true starting base
        """)

    st.divider()

    # -------------------------- CHURN BY REASON --------------------------
    st.subheader("Churn by Reason")
    if not churn_in_period.empty:
        reason_df = (churn_in_period.groupby("Reason")
                    .agg(Count=("Customer Name", "nunique"),
                         MRC_Lost=("MRC", "sum"))
                    .reset_index()
                    .sort_values("Count", ascending=False))
        st.dataframe(reason_df, use_container_width=True)

        fig = px.bar(reason_df, x="Count", y="Reason", orientation="h",
                     color="MRC_Lost", title="Churn Reasons (count & $ impact)",
                     color_continuous_scale="Reds")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No churn in this period")

    # -------------------------- NEW CUSTOMERS --------------------------
    st.subheader("New Customer Acquisition")
    if not new_in_period.empty:
        col_a, col_b = st.columns(2)
        with col_a:
            cat = new_in_period["Category"].value_counts().reset_index()
            fig1 = px.pie(cat, values="count", names="Category", title="By Category")
            st.plotly_chart(fig1, use_container_width=True)
        with col_b:
            loc = new_in_period["Location"].value_counts().head(15).reset_index()
            fig2 = px.bar(loc, x="Location", y="count", title="Top 15 Locations – New Customers")
            st.plotly_chart(fig2, use_container_width=True)

        st.success(f"Added {new_count:,} new customers (+${new_mrc:,.0f} MRC)")
    else:
        st.info("No new customers in selected period")

    st.caption("Data refreshes automatically every 5 minutes • Source: JotForm")

if __name__ == "__main__":
    main()
