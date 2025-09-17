
import streamlit as st
import pandas as pd
from jotform_client import fetch_jotform_data

def run_prep_dashboard():
    st.title("Fiber Prep Report")

    form_id = "210823797836164"
    try:
        data = fetch_jotform_data(form_id)
        if not data or len(data) == 0:
            st.warning("No data available from JotForm.")
            return

        df = pd.DataFrame(data)

        # Flatten nested fields
        df = df.applymap(lambda x: x.get("answer") if isinstance(x, dict) and "answer" in x else x)

        # Normalize and extract relevant fields
        df["Tech"] = df["Technician Name"].astype(str).str.strip()
        df["Date"] = pd.to_datetime(df["Submission Date"], errors="coerce")

        # Extract drop size from Inventory Items
        df["Drop Size"] = df["Inventory Items"].astype(str).str.extract(r"(500' Drop|750' Drop|1000' Drop)")
        df = df.dropna(subset=["Tech", "Date", "Drop Size"])

        # Show KPIs
        st.subheader("KPIs")
        st.metric("Total Preps", len(df))
        st.metric("Unique Techs", df["Tech"].nunique())
        st.metric("Date Range", f"{df['Date'].min().date()} to {df['Date'].max().date()}")

        # Visuals
        st.subheader("Preps Over Time")
        st.bar_chart(df.groupby("Date").size())

        st.subheader("Preps per Technician")
        st.bar_chart(df["Tech"].value_counts())

        st.subheader("Drop Size Count")
        st.bar_chart(df["Drop Size"].value_counts())

        st.subheader("Drop Size by Technician")
        st.bar_chart(df.groupby(["Tech", "Drop Size"]).size().unstack().fillna(0))

    except Exception as e:
        st.error(f"Failed to load Prep data: {e}")
