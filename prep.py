
def run_preps_dashboard(df=None):
    import streamlit as st
    import pandas as pd
    import plotly.express as px
    from jotform_client import fetch_preps_data

    # Load directly from API if df not passed
    if df is None:
        df = fetch_preps_data(form_id="210823797836164")
    if df is None or df.empty:
        st.error("No data loaded for Preps.")
        return

    st.markdown("<h1 style='color:#405C88;'>📝 Preps Dashboard</h1>", unsafe_allow_html=True)

    # --- Sidebar Filters ---
    st.sidebar.header("Filters")
    date_range = st.sidebar.date_input("Select Date Range", [])
    tech_filter = st.sidebar.multiselect("Technician", options=df["technician"].dropna().unique() if "technician" in df else [])
    other_emp_filter = st.sidebar.multiselect("Other Employee", options=df["other_employee"].dropna().unique() if "other_employee" in df else [])
    closure_type_filter = st.sidebar.multiselect("Closure Type", options=df["closure_type"].dropna().unique() if "closure_type" in df else [])
    splice_type_filter = st.sidebar.multiselect("Splice Type", options=df["splice_type"].dropna().unique() if "splice_type" in df else [])
    project_filter = st.sidebar.multiselect("Project", options=df["project"].dropna().unique() if "project" in df else [])

    # --- Apply Filters ---
    if date_range and "date" in df:
        df = df[(pd.to_datetime(df["date"]).dt.date >= date_range[0]) & (pd.to_datetime(df["date"]).dt.date <= date_range[-1])]
    if tech_filter and "technician" in df:
        df = df[df["technician"].isin(tech_filter)]
    if other_emp_filter and "other_employee" in df:
        df = df[df["other_employee"].isin(other_emp_filter)]
    if closure_type_filter and "closure_type" in df:
        df = df[df["closure_type"].isin(closure_type_filter)]
    if splice_type_filter and "splice_type" in df:
        df = df[df["splice_type"].isin(splice_type_filter)]
    if project_filter and "project" in df:
        df = df[df["project"].isin(project_filter)]

    # --- KPIs ---
    total_splices = len(df)
    total_fiber = df["fiber_count"].sum() if "fiber_count" in df else 0
    closures_worked = df["closure_type"].nunique() if "closure_type" in df else 0
    total_fats = df["fat"].nunique() if "fat" in df else 0
    total_scs = df["card"].nunique() if "card" in df else 0

    kpi1, kpi2, kpi3, kpi4, kpi5 = st.columns(5)
    kpi1.metric("Total Splice Events", total_splices)
    kpi2.metric("Total Fiber Count", total_fiber)
    kpi3.metric("Closures Worked", closures_worked)
    kpi4.metric("Total FATs", total_fats)
    kpi5.metric("Total SCs", total_scs)

    # --- Visuals ---
    if "closure_type" in df and "splice_type" in df:
        pivot = df.groupby(["closure_type", "splice_type"]).size().reset_index(name="count")
        st.plotly_chart(px.bar(pivot, x="closure_type", y="count", color="splice_type", barmode="group",
                               title="Closure Type by Splice Type with Splice Count"), use_container_width=True)

    if "technician" in df and "date" in df:
        tech_daily = df.groupby([pd.to_datetime(df["date"]).dt.date, "technician"]).size().reset_index(name="count")
        st.plotly_chart(px.line(tech_daily, x="date", y="count", color="technician",
                                title="Technician Daily Productivity"), use_container_width=True)

    if "project" in df and "technician" in df:
        proj_tech = df.groupby(["project", "technician"]).size().reset_index(name="count")
        st.plotly_chart(px.bar(proj_tech, x="project", y="count", color="technician", barmode="stack",
                               title="Projects by Technician"), use_container_width=True)

    # --- Export ---
    st.download_button("Download Filtered Data", data=df.to_csv(index=False), file_name="preps_filtered.csv", mime="text/csv")
