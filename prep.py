
import streamlit as st
import pandas as pd
import plotly.express as px

def run(df):
    st.title("Preps Report Debug View")

    if df.empty:
        st.warning("The DataFrame is empty. No submissions found or fetch failed.")
        return

    # Show debug info
    st.subheader("Data Preview")
    st.write(df.head())

    st.subheader("Column Names")
    st.write(list(df.columns))

    # Show submission count
    st.metric("Total Submissions", len(df))

    # Try plotting a basic submission timeline if 'Submission Date' exists
    date_col = next((c for c in df.columns if "date" in c.lower()), None)
    if date_col:
        df[date_col] = pd.to_datetime(df[date_col], errors='coerce')
        daily = df.groupby(df[date_col].dt.date).size().reset_index(name="count")
        fig = px.bar(daily, x=date_col, y="count", title="Submissions Over Time")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No date column found for charting. Please check form field names.")
