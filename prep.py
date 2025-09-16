
def run_preps_dashboard(df=None):
    import streamlit as st
    import pandas as pd
    import plotly.express as px

    if df is None:
        st.error("No data provided to Preps dashboard.")
        return

    st.markdown("<h1 style='color:#405C88;'>📝 Preps Dashboard</h1>", unsafe_allow_html=True)
    st.markdown("This dashboard analyzes Preps submissions from JotForm.")

    st.write("### Data Overview")
    st.write(df.head())

    # Example KPIs
    st.metric("Total Records", len(df))
    if "Technician" in df.columns:
        st.metric("Unique Technicians", df["Technician"].nunique())

    # Example Visualization
    if "Technician" in df.columns:
        tech_summary = df["Technician"].value_counts().reset_index()
        tech_summary.columns = ["Technician", "Count"]
        fig = px.bar(tech_summary, x="Technician", y="Count",
                     title="Work Orders per Technician",
                     color="Count", color_continuous_scale=["#7CB342","#405C88"])
        st.plotly_chart(fig, use_container_width=True)
