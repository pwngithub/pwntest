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
    st.markdown("### True Churn + Growth Analytics")

    with st.spinner("Loading latest data from JotForm..."):
        df = get_data()

    if df.empty:
        st.error("No data loaded.")
        st.stop()

    min_date = df["Submission Date"].min().date()
    max_date = df["Submission Date"].max().date()
    default_start = max_date - timedelta(days=179)  # ~6 months for good trends
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

    # True Churn Calculation (unchanged)
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

    # KPIs (unchanged)
    st.markdown("### True Churn Metrics")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Beginning Customers", f"{beginning_customers:,}")
    c2.metric("New Customers", f"{new_count:,}", delta=f"+{new_count}")
    c3.metric("Churned Customers", f"{churn_count:,}", delta=f"-{churn_count}")
    c4.metric("Ending Customers", f"{beginning_customers + new_count - churn_count:,}")

    c5, c6, c7, c8 = st.columns(4)
    c5.metric("Customer Churn Rate", f"{(churn_count/beginning_customers*100):.2f}%" if beginning_customers else "0%", delta_color="inverse")
    c6.metric("Net Growth Rate", f"{((beginning_customers + new_count - churn_count)/beginning_customers-1)*100:+.2f}%" if beginning_customers else "0%")
    c7.metric("Lost MRC", f"${churn_mrc:,.0f}", delta_color="inverse")
    c8.metric("Revenue Churn Rate", f"{(churn_mrc/beginning_mrc*100):.2f}%" if beginning_mrc > 0 else "0%", delta_color="inverse")

    st.divider()

    # ==================== MONTHLY CHURN BY REASON + MOVING AVG + EXPORT ====================
    if not churn_in_period.empty:
        st.subheader("Churn by Reason — Monthly Trend")

        monthly = churn_in_period.copy()
        monthly["Month"] = monthly["Submission Date"].dt.to_period("M").astype(str)
        monthly["Month_dt"] = monthly["Submission Date"].dt.to_period("M").dt.to_timestamp()

        trend = monthly.groupby(["Month", "Month_dt", "Reason"]).agg(
            Customers=("Customer Name", "nunique"),
            MRC_Lost=("MRC", "sum")
        ).reset_index()

        # Sort chronologically
        trend = trend.sort_values("Month_dt")

        # Total per month for % calc
        monthly_totals = trend.groupby("Month").agg(Total_Customers=("Customers", "sum")).reset_index()
        trend = trend.merge(monthly_totals, on="Month")
        trend["% of Monthly Churn"] = (trend["Customers"] / trend["Total_Customers"] * 100).round(1)

        # Moving average
        show_ma = st.checkbox("Show 3-Month Moving Average", value=True)
        if show_ma:
            ma = trend.groupby("Reason").apply(
                lambda x: x.assign(MA_Customers=x["Customers"].rolling(3, min_periods=1).mean())
            ).reset_index(drop=True)
            trend = ma

        # Plot
        fig_cust = px.bar(
            trend, x="Month", y="Customers", color="Reason",
            text=trend.apply(lambda row: f"{row['Customers']}<br>({row['% of Monthly Churn']}%)" if row['Customers'] > 0 else "", axis=1),
            title="Monthly Churn by Reason (Count + % of Total)",
            labels={"Customers": "Customers Lost", "Month": "Month"},
            height=550
        )
        fig_cust.update_traces(textposition="inside")

        if show_ma:
            fig_cust.add_scatter(
                x=trend["Month"], y=trend["MA_Customers"],
                mode="lines+markers", name="3-Mo Avg", line=dict(dash="dot", width=3),
                hovertemplate="3-Mo Avg: %{y:.0f}<extra></extra>"
            )

        fig_mrc = px.bar(
            trend, x="Month", y="MRC_Lost", color="Reason",
            title="Monthly MRC Lost by Reason",
            labels={"MRC_Lost": "MRC Lost ($)"},
            height=550
        )

        st.plotly_chart(fig_cust, use_container_width=True)
        st.plotly_chart(fig_mrc, use_container_width=True)

        # EXPORT BUTTON
        export_df = trend[["Month", "Reason", "Customers", "% of Monthly Churn", "MRC_Lost"]].copy()
        export_df["% of Monthly Churn"] = export_df["% of Monthly Churn"].astype(str) + "%"
        export_df.rename(columns={"Month": "Period"}, inplace=True)

        csv = export_df.to_csv(index=False).encode()
        st.download_button(
            label="Export Monthly Churn Data to Excel",
            data=csv,
            file_name=f"talley_churn_by_reason_monthly_{start_date}_to_{end_date}.csv",
            mime="text/csv"
        )

        with st.expander("View raw monthly data"):
            st.dataframe(trend.drop(columns=["Month_dt", "Total_Customers"]), use_container_width=True)

    else:
        st.info("No disconnects in selected period.")

    st.divider()

    # Keep your original sections below...
    if not churn_in_period.empty:
        st.subheader("Total Churn by Reason (Selected Period)")
        summary = churn_in_period.groupby("Reason").agg(
            Count=("Customer Name", "nunique"),
            MRC_Lost=("MRC", "sum")
        ).reset_index().sort_values("Count", ascending=False)
        st.dataframe(summary.style.format({"MRC_Lost": "${:,.0f}"}), use_container_width=True)

    if not new_in_period.empty:
        st.subheader("New Customer Acquisition")
        cola, colb = st.columns(2)
        with cola:
            st.plotly_chart(px.pie(new_in_period["Category"].value_counts().reset_index(),
                                 names="Category", values="count", title="By Category"), use_container_width=True)
        with colb:
            st.plotly_chart(px.bar(new_in_period["Location"].value_counts().head(15).reset_index(),
                                 x="Location", y="count", title="Top 15 Locations"), use_container_width=True)
        st.success(f"Added {new_count:,} new customers — +${new_mrc:,.0f} MRC")

    st.caption("Auto-refreshes every 5 minutes • Source: JotForm")


if __name__ == "__main__":
    run_dashboard()
