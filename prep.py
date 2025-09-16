
def run_preps_dashboard(df=None):
    import streamlit as st
    import pandas as pd
    from pandas import json_normalize
    import plotly.express as px

    if df is None or len(df) == 0:
        st.error("No data provided to Preps dashboard.")
        return

    st.markdown("<h1 style='color:#405C88;'>📝 Preps Dashboard</h1>", unsafe_allow_html=True)

    # Flatten JotForm JSON
    try:
        df_flat = json_normalize(df, sep="_")
    except Exception as e:
        st.error(f"Failed to normalize data: {e}")
        return

    st.write("### Flattened Data Preview")
    st.dataframe(df_flat.head())

    # --- KPIs ---
    st.metric("Total Records", len(df_flat))

    if "answers_Technician_answer" in df_flat.columns:
        st.metric("Unique Technicians", df_flat["answers_Technician_answer"].nunique())

        # Visualization
        tech_summary = df_flat["answers_Technician_answer"].value_counts().reset_index()
        tech_summary.columns = ["Technician", "Count"]
        fig = px.bar(tech_summary, x="Technician", y="Count",
                     title="Preps per Technician",
                     color="Count", color_continuous_scale=["#7CB342","#405C88"])
        st.plotly_chart(fig, use_container_width=True)

    else:
        st.info("Technician column not found yet. Check flattened data preview above to identify available fields.")
