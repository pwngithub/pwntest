def run_dashboard():
    from datetime import timedelta
    import pandas as pd
    import streamlit as st
    import requests
    import plotly.express as px

    # -------------------------------
    # DATA LOADER
    # -------------------------------
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
                "direction": "ASC",
            }

            response = requests.get(base_url, params=params)
            response.raise_for_status()
            data = response.json()

            items = data.get("content", [])
            if not items:
                break

            for item in items:
                answers = item.get("answers", {})
                submission_date = item.get("created_at", None)
                record = {"Submission Date": submission_date}
                for ans in answers.values():
                    name = ans.get("name")
                    answer = ans.get("answer")
                    if name and answer is not None:
                        record[name] = answer
                submissions.append(record)

            # If we got fewer than `limit` submissions this page, we're done
            if len(items) < limit:
                break

            offset += limit

        df = pd.DataFrame(submissions)
        return df

    # -------------------------------
    # APP TITLE
    # -------------------------------
    st.title("Talley Customer Dashboard")

    df = load_from_jotform()

    if df.empty:
        st.error("No data returned from JotForm.")
        return

    # -------------------------------
    # COLUMN NORMALIZATION
    # -------------------------------
    df.rename(
        columns={
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
        },
        inplace=True,
    )

    # -------------------------------
    # DATE PARSING
    # -------------------------------
    df["Submission Date"] = pd.to_datetime(df["Submission Date"], errors="coerce")
    df = df.dropna(subset=["Submission Date"])

    if df.empty:
        st.error("All submission dates were invalid after parsing.")
        return

    df["Month"] = df["Submission Date"].dt.to_period("M").astype(str)

    min_date = df["Submission Date"].min().date()
    max_date = df["Submission Date"].max().date()

    # Show available range for sanity check
    st.caption(f"Available data range: {min_date} → {max_date}")

    # Default to last 7 days if possible
    default_start = max_date - timedelta(days=6)
    if default_start < min_date:
        default_start = min_date

    start_date, end_date = st.date_input(
        "📅 Select date range",
        value=(default_start, max_date),
        min_value=min_date,
        max_value=max_date,
    )

    # -------------------------------
    # FILTER BY DATE RANGE
    # -------------------------------
    mask = (df["Submission Date"].dt.date >= start_date) & (
        df["Submission Date"].dt.date <= end_date
    )
    df = df.loc[mask]

    if df.empty:
        st.warning("No records found in the selected date range.")
        return

    # -------------------------------
    # BASIC KPIs
    # -------------------------------
    total_records = len(df)
    disconnects = df[df["Status"] == "Disconnect"]
    new_customers = df[df["Status"] == "NEW"]
    churn_mrc = pd.to_numeric(disconnects["MRC"], errors="coerce").fillna(0).sum()

    col1, col2, col3 = st.columns(3)
    col1.metric("📈 Total Records", f"{total_records}")
    col2.metric("📉 Churned Customers", f"{len(disconnects)}")
    col3.metric("💲 Churn MRC Impact", f"${churn_mrc:,.2f}")

    st.markdown("---")

    # -------------------------------
    # CHURN ANALYSIS BY REASON
    # -------------------------------
    st.header("Churn Analysis by Reason")

    if not disconnects.empty:
        churn_summary = (
            disconnects.groupby("Reason")
            .agg(
                Count=("Reason", "count"),
                Total_MRC=(
                    "MRC",
                    lambda x: pd.to_numeric(x, errors="coerce").fillna(0).sum(),
                ),
            )
            .reset_index()
        )
        churn_summary = churn_summary.sort_values(by="Count", ascending=False)

        st.dataframe(churn_summary, use_container_width=True)

        fig_reason = px.bar(
            churn_summary,
            x="Count",
            y="Reason",
            orientation="h",
            title="Churn by Reason (Sorted)",
            color="Count",
            color_continuous_scale=["#7CB342", "#405C88"],
            height=500,
        )
        st.plotly_chart(fig_reason, use_container_width=True)
    else:
        st.info("No disconnect records in this date range.")

    st.markdown("---")

    # -------------------------------
    # CHURN BY LOCATION
    # -------------------------------
    st.header("Churn by Location (Top 20)")

    if not disconnects.empty:
        loc_summary = (
            disconnects.groupby("Location")
            .size()
            .reset_index(name="Count")
            .sort_values(by="Count", ascending=False)
            .head(20)
        )

        fig_location = px.bar(
            loc_summary,
            x="Location",
            y="Count",
            title="Churn by Location (Top 20)",
            color="Count",
            color_continuous_scale=["#7CB342", "#405C88"],
        )
        st.plotly_chart(fig_location, use_container_width=True)
    else:
        st.info("No disconnect records to show by location.")

    st.markdown("---")

    # -------------------------------
    # NEW CUSTOMER TRENDS
    # -------------------------------
    st.header("New Customer Trends")

    if not new_customers.empty:
        new_by_category = (
            new_customers.groupby("Category")
            .size()
            .reset_index(name="Count")
            .sort_values(by="Count", ascending=False)
        )

        new_by_location = (
            new_customers.groupby("Location")
            .size()
            .reset_index(name="Count")
            .sort_values(by="Count", ascending=False)
            .head(20)
        )

        col4, col5 = st.columns(2)

        with col4:
            fig_new_cat = px.bar(
                new_by_category,
                x="Category",
                y="Count",
                title="New Customers by Category",
                color="Count",
                color_continuous_scale=["#7CB342", "#405C88"],
            )
            st.plotly_chart(fig_new_cat, use_container_width=True)

        with col5:
            fig_new_loc = px.bar(
                new_by_location,
                x="Location",
                y="Count",
                title="New Customers by Location (Top 20)",
                color="Count",
                color_continuous_scale=["#7CB342", "#405C88"],
            )
            st.plotly_chart(fig_new_loc, use_container_width=True)
    else:
        st.info("No new customer records in this date range.")


if __name__ == "__main__":
    run_dashboard()
