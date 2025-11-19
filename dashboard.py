import streamlit as st
import pandas as pd
import requests
import plotly.express as px
from datetime import timedelta

st.set_page_config(page_title="Talley Customer Dashboard", layout="wide")

def load_from_jotform():
    api_key = "22179825a79dba61013e4fc3b9d30fa4"
    form_id = "240073839937062"
    base_url = f"https://api.jotform.com/form/{form_id}/submissions"
    submissions = []
    limit = 1000
    offset = 0

    while True:
        params = {
            "apiKey": api_key,
            "limit": limit,
            "offset": offset,
            "orderby": "created_at",
        }
        try:
            response = requests.get(base_url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()
            items = data.get("content", [])

            if not items:
                break

            for item in items:
                answers = item.get("answers", {})
                submission_date = item.get("created_at")
                record = {"Submission Date": submission_date}

                for ans in answers.values():
                    name = ans.get("name")
                    answer = ans.get("answer", "")
                    if name and answer not in [None, ""]:
                        record[name] = answer
                submissions.append(record)

            if len(items) < limit:
                break
            offset += limit

        except Exception as e:
            st.error(f"Error loading data from JotForm: {e}")
            return pd.DataFrame()

    return pd.DataFrame(submissions)

@st.cache_data(ttl=300)  # Cache for 5 minutes
def get_clean_data():
    df = load_from_jotform()

    if df.empty:
        return df, df

    # Normalize column names
    df.rename(columns={
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
    }, inplace=True)

    # Clean and parse dates
    df["Submission Date"] = pd.to_datetime(df["Submission Date"], errors="coerce")
    df = df.dropna(subset=["Submission Date"]).copy()

    # Convert MRC to numeric
    df["MRC"] = pd.to_numeric(df["MRC"], errors="coerce").fillna(0)

    # Standardize Status
    df["Status"] = df["Status"].str.upper().str.strip()

    return df, df.copy()

def run_dashboard():
    st.title("Talley Customer Dashboard")
    st.markdown("### True Churn & Growth Analytics")

    # Load data
    with st.spinner("Loading data from JotForm..."):
        full_df, _ = get_clean_data()

    if full_df.empty:
        st.error("No data returned from JotForm. Check API key and form ID.")
        return

    # Date range selector
    min_date = full_df["Submission Date"].min().date()
    max_date = full_df["Submission Date"].max().date()
    st.caption(f"Available data: {min_date} → {max_date}")

    default_start = max_date - timedelta(days=29)  # Default last 30 days
    if default_start < min_date:
        default_start = min_date

    start_date, end_date = st.date_input(
        "Select Period for Analysis",
        value=(default_start, max_date),
        min_value=min_date,
        max_value=max_date,
    )

    period_start = pd.Timestamp(start_date)
    period_end = pd.Timestamp(end_date)

    # Filter data in selected period
    period_mask = (full_df["Submission Date"].dt.date >= start_date) & \
                  (full_df["Submission Date"].dt.date <= end_date)
    period_df = full_df[period_mask].copy()

    if period_df.empty:
        st.warning("No records in selected date range.")
        return

    # ====== TRUE CHURN CALCULATION ======
    # 1. Customers active at START of period
    new_before = full_df[
        (full_df["Status"] == "NEW") &
        (full_df["Submission Date"] <= period_start)
    ]
    disconnect_before = full_df[
        (full_df["Status"] == "Disconnect") &
        (full_df["Submission Date"] <= period_start)
    ]

    # Customers who signed up before period and haven't cancelled yet
    active_customers_start = new_before[
        ~new_before["Customer Name"].isin(disconnect_before["Customer Name"])
    ]

    beginning_customers = active_customers_start["Customer Name"].nunique()
    beginning_mrc = active_customers_start["MRC"].sum()

    # 2. Activity DURING the period
    new_in_period = period_df[period_df["Status"] == "NEW"]
    churn_in_period = period_df[period_df["Status"] == "Disconnect"]

    new_count = new_in_period["Customer Name"].nunique()
    new_mrc_added = new_in_period["MRC"].sum()

    churn_count = churn_in_period["Customer Name"].nunique()
    churn_mrc_lost = churn_in_period["MRC"].sum()

    # 3. Ending numbers
    ending_customers = beginning_customers + new_count - churn_count
    ending_mrc = beginning_mrc + new_mrc_added - churn_mrc_lost

    # 4. Rates
    customer_churn_rate = (churn_count / beginning_customers * 100) if beginning_customers > 0 else 0
    net_growth_rate = ((ending_customers - beginning_customers) / beginning_customers * 100) if beginning_customers > 0 else 0
    revenue_churn_rate = (churn_mrc_lost / beginning_mrc * 100) if beginning_mrc > 0 else 0

    # ====== DISPLAY TRUE CHURN KPIs ======
    st.markdown("## True Churn Metrics")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Beginning Customers", f"{beginning_customers:,}", help="Active at start of period")
    col2.metric("New Customers", f"{new_count:,}", f"+{new_count:,}")
    col3.metric("Churned Customers", f"{churn_count:,}", f"-{churn_count:,}")
    col4.metric("Ending Customers", f"{ending_customers:,}", f"{ending_customers - beginning_customers:+,}")

    col5, col6, col7, col8 = st.columns(4)
    col5.metric("Customer Churn Rate", f"{customer_churn_rate:.2f}%", 
                delta=f"{customer_churn_rate:.1f}% lost" if customer_churn_rate > 5 else None,
                delta_color="inverse")
    col6.metric("Net Customer Growth", f"{net_growth_rate:+.2f}%", delta_color="normal")
    col7.metric("Lost MRC (Churn)", f"${churn_mrc_lost:,.0f}", delta_color="inverse")
    col8.metric("Revenue Churn Rate", f"{revenue_churn_rate:.2f}%", delta_color="inverse")

    with st.expander("How is True Churn Calculated?"):
        st.write(f"""
        - **Beginning Customers**: Unique customers with a 'NEW' submission **on or before {start_date}** who had **not** disconnected by that date.
        - **Churned Customers**: Those who submitted a 'Disconnect' form **during** {start_date} to {end_date}.
        - **Customer Churn Rate** = Churned ÷ Beginning Customers
        - **Revenue Churn Rate** = Lost MRC ÷ Beginning MRC
        """)

    st.markdown("---")

    # ====== CHURN ANALYSIS BY REASON ======
    st.header("Churn Analysis by Reason")
    if not churn_in_period.empty:
        reason_summary = (
            churn_in_period.groupby("Reason")
            .agg(
                Count=("Customer Name", "nunique"),
                Total_MRC_Lost=("MRC", "sum")
            )
            .reset_index()
            .sort_values("Count", ascending=False)
        )
        st.dataframe(reason_summary, use_container_width=True)

        fig_reason = px.bar(
            reason_summary,
            x="Count",
            y="Reason",
            orientation="h",
            title="Churn by Reason",
            color="Total_MRC_Lost",
            color_continuous_scale="Reds",
            height=500,
            labels={"Count": "Customers Lost", "Total_MRC_Lost": "MRC Lost ($)"}
        )
        st.plotly_chart(fig_reason, use_container_width=True)
    else:
        st.info("No churn recorded in this period.")

    st.markdown("---")

    # ====== CHURN BY LOCATION ======
    st.header("Churn by Location (Top 20)")
    if not churn_in_period.empty:
        loc_churn = (
            churn_in_period.groupby("Location")
            .agg(Count=("Customer Name", "nunique"))
            .reset_index()
            .sort_values("Count", ascending=False)
            .head(20)
        )
        fig_loc = px.bar(loc_churn, x="Location", y="Count", title="Top 20 Locations by Churn", color="Count")
        st.plotly_chart(fig_loc, use_container_width=True)

    # ====== NEW CUSTOMERS SECTION ======
    st.header("New Customer Acquisition")
    if not new_in_period.empty:
        col_a, col_b = st.columns(2)

        with col_a:
            cat_new = new_in_period.groupby("Category").size().reset_index(name="Count").sort_values("Count", ascending=False)
            fig_cat = px.pie(cat_new, values="Count", names="Category", title="New Customers by Category")
            st.plotly_chart(fig_cat, use_container_width=True)

        with col_b:
            loc_new = (
                new_in_period.groupby("Location")
                .agg(Count=("Customer Name", "nunique"))
                .reset_index()
                .sort_values("Count", ascending=False)
                .head(15)
            )
            fig_loc_new = px.bar(loc_new, x="Location", y="Count", title="Top Locations - New Customers")
            st.plotly_chart(fig_loc_new, use_container_width=True)

        st.success(f"Added {new_count:,} new customers (+${new_mrc_added:,.0f} MRC) in this period!")
    else:
        st.info("No new customers in selected period.")

    st.markdown("---")
    st.caption("Dashboard auto-refreshes every 5 minutes • Powered by JotForm + Streamlit")

if __name__ == "__main__":
    run_dashboard()
