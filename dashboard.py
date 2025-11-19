# dashboard.py
import streamlit as st
import pandas as pd
import requests
import plotly.express as px
import plotly.graph_objects as go
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
                        parts = []
                        for v in answer.values():
                            if isinstance(v, list): parts.extend(v)
                            else: parts.append(str(v))
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
    st.title("Talley Customer Dashboard")
    st.markdown("### True Churn + Growth + Revenue Retention")

    with st.spinner("Loading latest data from JotForm..."):
        df = get_data()

    if df.empty:
        st.error("No data loaded.")
        st.stop()

    min_date = df["Submission Date"].min().date()
    max_date = df["Submission Date"].max().date()
    default_start = max_date - timedelta(days=365)
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
    period_df = df[(df["Submission Date"].dt.date >= start_date) & (df["Submission Date"].dt.date <= end_date)].copy()

    # ==================== TRUE CHURN & GROWTH CALCULATION ====================
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

    # ==================== TRUE CHURN METRICS ====================
    st.markdown("### True Churn Metrics")
    st.caption("Losses from existing customer base")

    ch1, ch2, ch3, ch4 = st.columns(4)
    ch1.metric("Churned Customers", f"{churn_count:,}", delta=f"-{churn_count}")
    ch2.metric("Customer Churn Rate", f"{(churn_count/beginning_customers*100):.2f}%" if beginning_customers else "0%", delta_color="inverse")
    ch3.metric("Lost MRC", f"${churn_mrc:,.0f}", delta_color="inverse")
    ch4.metric("Revenue Churn Rate", f"{(churn_mrc/beginning_mrc*100):.2f}%" if beginning_mrc > 0 else "0%", delta_color="inverse")

    # ==================== TRUE GROWTH METRICS ====================
    st.divider()
    st.markdown("### True Growth Metrics")
    st.caption("New customers and net expansion")

    gr1, gr2, gr3, gr4 = st.columns(4)
    gr1.metric("New Customers", f"{new_count:,}", delta=f"+{new_count}")
    gr2.metric("New MRC Added", f"${new_mrc:,.0f}")
    gr3.metric("Net Customer Change", f"{new_count - churn_count:+,}", delta=f"{new_count - churn_count:+,}")
    gr4.metric("Net Growth Rate", f"{((ending_customers / beginning_customers - 1)*100):+.2f}%" if beginning_customers else "N/A")

    st.divider()

    # ==================== REVENUE COHORT ANALYSIS ====================
    st.subheader("Revenue Cohort Analysis – MRC Retention by Signup Month")

    # Get first NEW record + MRC for each customer
    new_records = df[df["Status"] == "NEW"].sort_values("Submission Date")
    first_new = new_records.drop_duplicates("Customer Name", keep="first")[["Customer Name", "Submission Date", "MRC"]]
    first_new["Cohort Month"] = first_new["Submission Date"].dt.to_period("M")

    # Get all DISCONNECT dates
    disconnects = df[df["Status"] == "DISCONNECT"][["Customer Name", "Submission Date"]]
    disconnects = disconnects.sort_values("Submission Date").drop_duplicates("Customer Name", keep="last")

    # Combine to get active period
    cohort_mrc = first_new.merge(disconnects, on="Customer Name", how="left", suffixes=("_start", "_end"))
    cohort_mrc["End Month"] = cohort_mrc["Submission Date_end"].dt.to_period("M").fillna(pd.Period(year=2100, month=1, freq="M"))

    # Expand each customer into monthly rows
    rows = []
    for _, row in cohort_mrc.iterrows():
        start = row["Cohort Month"]
        end = row["End Month"]
        mrc = row["MRC"]
        months = pd.period_range(start, end, freq="M")
        for i, month in enumerate(months):
            rows.append({"Cohort Month": start, "Month Number": i, "Month": month, "MRC": mrc})

    monthly_mrc = pd.DataFrame(rows)

    # Aggregate MRC per cohort per month number
    cohort_revenue = monthly_mrc.groupby(["Cohort Month", "Month Number"])["MRC"].sum().unstack(fill_value=0)
    cohort_revenue = cohort_revenue.reindex(columns=range(13), fill_value=0)

    # Calculate retention % vs Month 0
    initial_mrc = cohort_revenue[0]
    revenue_retention = cohort_revenue.divide(initial_mrc, axis=0) * 100

    # Heatmap
    fig = go.Figure(data=go.Heatmap(
        z=revenue_retention.values,
        x=list(revenue_retention.columns),
        y=[str(c) for c in revenue_retention.index],
        colorscale="RdYlGn",
        zmid=100,
        text=[[f"{val:.1f}%" if val > 0 else "" for val in row] for row in revenue_retention.values],
        texttemplate="%{text}",
        textfont={"size": 11},
        hoverongaps=False
    ))

    fig.update_layout(
        title="Revenue Cohort Heatmap – % of Original MRC Retained",
        xaxis_title="Months Since Signup",
        yaxis_title="Cohort (Signup Month)",
        height=650
    )

    st.plotly_chart(fig, use_container_width=True)

    with st.expander("View Revenue Cohort Table"):
        display_table = revenue_retention.round(1).astype(str) + "%"
        display_table.insert(0, "Initial MRC", initial_mrc.map("${:,.0f}".format))
        st.dataframe(display_table, use_container_width=True)

    st.divider()

    # ==================== CHURN BY REASON ====================
    if not churn_in_period.empty:
        st.subheader("Churn by Reason")
        reason_df = (
            churn_in_period.groupby("Reason")
            .agg(Count=("Customer Name", "nunique"), MRC_Lost=("MRC", "sum"))
            .reset_index()
            .sort_values("Count", ascending=False)
        )
        st.dataframe(reason_df.style.format({"MRC_Lost": "${:,.0f}"}), use_container_width=True)

        fig_reason = px.bar(
            reason_df, x="Count", y="Reason", orientation="h",
            color="MRC_Lost", title="Churn Reasons (Count + $ Impact)",
            color_continuous_scale="Reds"
        )
        st.plotly_chart(fig_reason, use_container_width=True)

    # ==================== NEW CUSTOMERS ====================
    if not new_in_period.empty:
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


if __name__ == "__main__":
    run_dashboard()
