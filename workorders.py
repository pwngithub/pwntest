
import streamlit as st
import pandas as pd
import plotly.express as px
import os





def run_workorders_dashboard():
    import streamlit as st
    import pandas as pd
    import plotly.express as px

    st.markdown("<h1 style='color:#405C88;'>📋 Work Orders Dashboard</h1>", unsafe_allow_html=True)
    st.markdown("Enhanced dashboard with filters for technicians, work order types, and date range.")

    # --- File Uploader ---
    uploaded_file = st.file_uploader("📂 Upload a Work Orders CSV", type=["csv"])
    if uploaded_file is not None:
        df = pd.read_csv(uploaded_file)
    else:
        st.warning("⚠️ Please upload a Work Orders CSV file.")
        return

    # --- Parse Duration & Distance ---
    if "Duration" in df.columns:
        df["Duration (mins)"] = df["Duration"].astype(str).str.replace(" mins", "", regex=False).astype(float)
    if "Distance" in df.columns:
        df["Distance (miles)"] = df["Distance"].astype(str).str.replace(" miles", "", regex=False).astype(float)

    # --- Handle Date Column Robustly ---
    date_col = None
    for candidate in ["Date When", "Date", "Submission Date", "Created At"]:
        if candidate in df.columns:
            date_col = candidate
            break
    if date_col:
        df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
        df = df.dropna(subset=[date_col])
        df["Month"] = df[date_col].dt.to_period("M").astype(str)

    # --- Sidebar Filters ---
    st.sidebar.header("🔎 Filters")

    if date_col:
        min_date, max_date = df[date_col].min(), df[date_col].max()
        start_date, end_date = st.sidebar.date_input("Date Range", [min_date, max_date])
        df = df[(df[date_col] >= pd.to_datetime(start_date)) & (df[date_col] <= pd.to_datetime(end_date))]

    if "Work Type" in df.columns:
        work_types = st.sidebar.multiselect("Work Type", df["Work Type"].unique(), default=df["Work Type"].unique())
        df = df[df["Work Type"].isin(work_types)]

    if "Techinician" in df.columns:
        techs = st.sidebar.multiselect("Technician", df["Techinician"].unique(), default=df["Techinician"].unique())
        df = df[df["Techinician"].isin(techs)]

    # --- KPIs ---
    total_orders = len(df)
    finalized = len(df[df['Current State'].str.lower() == 'finalized']) if 'Current State' in df.columns else 0
    scheduled = len(df[df['Current State'].str.lower() == 'scheduled']) if 'Current State' in df.columns else 0
    avg_duration = df["Duration (mins)"].mean() if "Duration (mins)" in df.columns else 0
    avg_distance = df["Distance (miles)"].mean() if "Distance (miles)" in df.columns else 0
    avg_per_tech = df.groupby("Techinician").size().mean() if "Techinician" in df.columns else 0

    col1, col2, col3 = st.columns(3)
    col1.metric("📑 Total Orders", total_orders)
    col2.metric("✅ Finalized", finalized)
    col3.metric("⏳ Scheduled", scheduled)

    col4, col5, col6 = st.columns(3)
    col4.metric("⏱️ Avg Duration (mins)", f"{avg_duration:.1f}")
    col5.metric("📍 Avg Distance (miles)", f"{avg_distance:.1f}")
    col6.metric("👷 Avg Orders/Technician", f"{avg_per_tech:.1f}")

    # --- Download Processed File ---
    csv_export = df.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="💾 Download Processed Work Orders CSV",
        data=csv_export,
        file_name="workorders_processed.csv",
        mime="text/csv",
    )

    st.markdown("---")

    # --- Visualizations ---

    # Work Orders by Type (Bar Chart)
    if "Work Type" in df.columns:
        type_summary = df["Work Type"].value_counts().reset_index()
        type_summary.columns = ["Work Type", "Count"]
        fig_type = px.bar(type_summary, x="Work Type", y="Count",
                          title="Work Orders by Type",
                          color="Count", color_continuous_scale=["#7CB342","#405C88"])
        st.plotly_chart(fig_type, use_container_width=True)

    # Avg Duration by Work Type (Bar Chart)
    if "Work Type" in df.columns and "Duration (mins)" in df.columns:
        dur_summary = df.groupby("Work Type")["Duration (mins)"].mean().reset_index()
        fig_dur = px.bar(dur_summary, x="Work Type", y="Duration (mins)",
                         title="Average Duration by Work Type",
                         color="Duration (mins)", color_continuous_scale=["#7CB342","#405C88"])
        st.plotly_chart(fig_dur, use_container_width=True)

    # Technician Productivity (Bar Chart)
    if "Techinician" in df.columns:
        tech_summary = df["Techinician"].value_counts().reset_index()
        tech_summary.columns = ["Technician", "Count"]
        fig_tech = px.bar(tech_summary, x="Technician", y="Count",
                          title="Work Orders per Technician",
                          color="Count", color_continuous_scale=["#7CB342","#405C88"])
        st.plotly_chart(fig_tech, use_container_width=True)

    # Distance vs Duration Scatter Plot
    if "Distance (miles)" in df.columns and "Duration (mins)" in df.columns:
        fig_scatter = px.scatter(df, x="Distance (miles)", y="Duration (mins)",
                                 title="Distance vs Duration",
                                 color="Work Type" if "Work Type" in df.columns else None,
                                 color_discrete_sequence=px.colors.qualitative.Set2)
        st.plotly_chart(fig_scatter, use_container_width=True)
