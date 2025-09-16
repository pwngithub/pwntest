
def run_preps_dashboard(df=None):
    import streamlit as st
    import plotly.express as px

    if df is None or df.empty:
        st.error("No data provided to Preps dashboard.")
        return

    st.markdown("<h1 style='color:#405C88;'>📝 Preps Dashboard</h1>", unsafe_allow_html=True)

    # --- KPIs ---
    total_records = len(df)
    unique_techs = df["technician"].nunique() if "technician" in df else 0
    fiber_yes = (df["fiber_connected"] == "Yes").sum() if "fiber_connected" in df else 0
    fiber_pct = round((fiber_yes / total_records * 100), 1) if total_records > 0 else 0

    kpi1, kpi2, kpi3 = st.columns(3)
    kpi1.metric("Total Records", total_records)
    kpi2.metric("Unique Technicians", unique_techs)
    kpi3.metric("% Fiber Connected", f"{fiber_pct}%")

    # --- Charts ---
    if "technician" in df:
        tech_counts = df["technician"].value_counts().reset_index()
        tech_counts.columns = ["Technician", "Count"]
        st.plotly_chart(px.bar(tech_counts, x="Technician", y="Count",
                               title="Records per Technician",
                               color="Count", color_continuous_scale="Blues"),
                        use_container_width=True)

    if "fiber_connected" in df:
        fiber_counts = df["fiber_connected"].value_counts().reset_index()
        fiber_counts.columns = ["Fiber Connected", "Count"]
        st.plotly_chart(px.pie(fiber_counts, names="Fiber Connected", values="Count",
                               title="Fiber Connected Distribution"),
                        use_container_width=True)

    if "fat" in df:
        fat_counts = df["fat"].value_counts().reset_index().head(10)
        fat_counts.columns = ["FAT", "Count"]
        st.plotly_chart(px.bar(fat_counts, x="FAT", y="Count",
                               title="Top FATs (Top 10)",
                               color="Count", color_continuous_scale="Greens"),
                        use_container_width=True)
