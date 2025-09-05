
import streamlit as st
import pandas as pd
import plotly.express as px

def run(df):
    st.title("📋 Preps Report")

    st.sidebar.success("✅ Preps Report Loaded")
    st.sidebar.write("Data shape:", df.shape)

    if df.empty:
        st.warning("No data was returned from JotForm. Please check API key, form ID, or submission status.")
        return

    st.sidebar.write("Columns:", list(df.columns))

    # Show a small preview
    st.subheader("Submission Preview")
    st.dataframe(df.head())

    # Safe date column guess
    date_col = next((c for c in df.columns if "date" in c.lower()), None)
    if date_col:
        try:
            df[date_col] = pd.to_datetime(df[date_col], errors='coerce')
            daily = df.groupby(df[date_col].dt.date).size().reset_index(name="count")
            fig = px.bar(daily, x=date_col, y="count", title="Submissions Over Time")
            st.plotly_chart(fig, use_container_width=True)
        except Exception as e:
            st.error(f"Chart failed to render: {e}")
    else:
        st.info("No column with 'date' in name found to plot submission timeline.")
