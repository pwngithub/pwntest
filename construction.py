import streamlit as st
import pandas as pd
import plotly.express as px
import json
import requests

def run_construction_dashboard():
    # Pioneer theme styling
    st.markdown(
        '''
        <style>
            .main {background-color: #ffffff;}
            .block-container {padding-top: 2rem;}
            h1, h2, h3 {color: #375EAB;}
            .stMetric > div > div {background-color: #8BC53F; color: white; border-radius: 0.25rem; padding: 0.25rem;}
        </style>
        ''',
        unsafe_allow_html=True
    )

    st.image("https://www.pioneerbroadband.net/sites/all/themes/pioneer/images/logo.png", width=300)
    st.title("Construction Dashboard")

    def load_from_jotform():
        api_key = "22179825a79dba61013e4fc3b9d30fa4"
        form_id = "230173417525047"
        url = f"https://api.jotform.com/form/{form_id}/submissions?apiKey={api_key}&limit=1000"
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        
        submissions = []
        for item in data["content"]:
            answers = item.get("answers", {})
            submission_date = item.get("created_at", None)
            record = {"Submission Date": submission_date}
            for ans in answers.values():
                name = ans.get("name")
                answer = ans.get("answer")
                if name and answer is not None:
                    record[name] = answer
            submissions.append(record)
        
        df = pd.DataFrame(submissions)
        return df

    df = load_from_jotform()
    df.columns = df.columns.str.strip()
    df["Submission Date"] = pd.to_datetime(df["Submission Date"], errors="coerce")
    df = df.dropna(subset=["Submission Date"])

    min_date = df["Submission Date"].min().date()
    max_date = df["Submission Date"].max().date()

    start_date, end_date = st.date_input(
        "📅 Select date range",
        value=(min_date, max_date),
        min_value=min_date,
        max_value=max_date
    )

    df = df[(df["Submission Date"].dt.date >= start_date) & (df["Submission Date"].dt.date <= end_date)]

    weeks_in_range = max(1, ((end_date - start_date).days + 1) / 7)

    selected_projects = st.multiselect(
        "Filter by Project(s)",
        options=df["projectOr"].dropna().unique(),
        default=df["projectOr"].dropna().unique()
    )
    selected_techs = st.multiselect(
        "Filter by Technician(s)",
        options=df["whoFilled"].dropna().unique(),
        default=df["whoFilled"].dropna().unique()
    )

    df = df[df["projectOr"].isin(selected_projects) & df["whoFilled"].isin(selected_techs)]

    def extract_json_footage(df_partial, column, new_col):
        df_out = df_partial.copy()
        df_out[new_col] = 0
        for idx, val in df_out[column].dropna().items():
            try:
                items = json.loads(val)
                for item in items:
                    footage_str = item.get("Footage", "0").replace(",", "").strip()
                    if footage_str.isdigit():
                        df_out.at[idx, new_col] += int(footage_str)
            except:
                continue
        return df_out

    lash_df = extract_json_footage(df[df["typeA45"].notna()], "typeA45", "LashFootage")
    pull_df = extract_json_footage(df[df["fiberPull"].notna()], "fiberPull", "PullFootage")
    strand_df = extract_json_footage(df[df["standInfo"].notna()], "standInfo", "StrandFootage")

    lash_total = lash_df["LashFootage"].sum()
    pull_total = pull_df["PullFootage"].sum()
    strand_total = strand_df["StrandFootage"].sum()
    total_projects = df["projectOr"].nunique()
    total_hours = pd.to_numeric(df['workHours'], errors='coerce').sum()

    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Lash Footage", f"{lash_total:,}")
    col2.metric("Pull Footage", f"{pull_total:,}")
    col3.metric("Strand Footage", f"{strand_total:,}")
    col4.metric("Projects", f"{total_projects}")
    col5.metric("Total Hours", f"{total_hours:,.2f}")


    st.markdown("---")
    st.header("Average Lash, Pull, Strand per Truck per Week (Filtered Range)")

    lash_group = lash_df.groupby("whatTruck")["LashFootage"].sum().reset_index()
    pull_group = pull_df.groupby("whatTruck")["PullFootage"].sum().reset_index()
    strand_group = strand_df.groupby("whatTruck")["StrandFootage"].sum().reset_index()

    merged = pd.merge(lash_group, pull_group, on="whatTruck", how="outer")
    merged = pd.merge(merged, strand_group, on="whatTruck", how="outer")
    merged = merged.fillna(0)

    merged["LashPerWeek"] = merged["LashFootage"] / weeks_in_range
    merged["PullPerWeek"] = merged["PullFootage"] / weeks_in_range
    merged["StrandPerWeek"] = merged["StrandFootage"] / weeks_in_range

    melted = pd.melt(
        merged,
        id_vars=["whatTruck"],
        value_vars=["LashPerWeek", "PullPerWeek", "StrandPerWeek"],
        var_name="Type",
        value_name="AvgFootagePerWeek"
    )

    fig_avg_truck = px.bar(
        melted,
        x="AvgFootagePerWeek",
        y="whatTruck",
        color="Type",
        barmode="group",
        orientation="h",
        title="Average Lash, Pull, Strand per Truck per Week (Filtered Range)",
        template="plotly_dark",
        color_discrete_map={
            "LashPerWeek": "#375EAB",
            "PullPerWeek": "#8BC53F",
            "StrandPerWeek": "#999999"
        }
    )
    fig_avg_truck.update_traces(texttemplate='%{x:.0f}', textposition='auto', marker_line_width=0.5)
    st.plotly_chart(fig_avg_truck, use_container_width=True)

    # --- START: New Graph for Total Footage per Truck ---

    st.header("Total Lash, Pull, & Strand Footage per Truck (Filtered Range)")

    melted_totals = pd.melt(
        merged,
        id_vars=["whatTruck"],
        value_vars=["LashFootage", "PullFootage", "StrandFootage"],
        var_name="Type",
        value_name="TotalFootage"
    )

    fig_total_truck = px.bar(
        melted_totals,
        x="TotalFootage",
        y="whatTruck",
        color="Type",
        barmode="group",
        orientation="h",
        title="Total Lash, Pull, & Strand Footage per Truck (Filtered Range)",
        template="plotly_dark",
        color_discrete_map={
            "LashFootage": "#375EAB",
            "PullFootage": "#8BC53F",
            "StrandFootage": "#999999"
        }
    )
    fig_total_truck.update_traces(texttemplate='%{x:,.0f}', textposition='auto', marker_line_width=0.5)
    st.plotly_chart(fig_total_truck, use_container_width=True)

    # --- END: New Graph for Total Footage per Truck ---

    st.header("Total Average per Week (All Trucks Combined)")

    total_lash_per_week = merged["LashFootage"].sum() / weeks_in_range
    total_pull_per_week = merged["PullFootage"].sum() / weeks_in_range
    total_strand_per_week = merged["StrandFootage"].sum() / weeks_in_range

    total_df = pd.DataFrame({
        "Type": ["Lash", "Pull", "Strand"],
        "AvgPerWeek": [total_lash_per_week, total_pull_per_week, total_strand_per_week]
    })

    fig_totals = px.bar(
        total_df,
        x="Type",
        y="AvgPerWeek",
        color="Type",
        template="plotly_dark",
        color_discrete_map={
            "Lash": "#375EAB",
            "Pull": "#8BC53F",
            "Strand": "#999999"
        },
        title="Total Average per Week (All Trucks Combined)"
    )
    fig_totals.update_traces(texttemplate='%{y:.0f}', textposition='auto', marker_line_width=0.5)
    st.plotly_chart(fig_totals, use_container_width=True)

    st.markdown("---")
    st.header("📋 Detailed Work Table")
    st.dataframe(df[["Submission Date", "projectOr", "whoFilled", "whatTruck", "workHours", "typeA45", "fiberPull", "standInfo"]])

if __name__ == "__main__":
    run_construction_dashboard()
