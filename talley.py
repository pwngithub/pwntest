
import streamlit as st

def run_talley(df):
    st.title("Tally Report")

    if df is None or df.empty:
        st.warning("No Tally data available.")
        return

    st.success(f"Loaded Tally data: {df.shape[0]} rows")
    st.dataframe(df)
