import streamlit as st
import pandas as pd
import numpy as np

def run_kpi_test():
    st.set_page_config(layout="wide")

    st.title("KPI Logic Test")
    st.info("This page uses built-in sample data to test the KPI display logic.")

    # --- 1. Create a Perfect, Sample DataFrame ---
    # This replaces your file upload.
    data = {
        'Technician': ['Brandon Barton', 'Jake Murray', 'Cam Cullinan', 'Brandon Barton', 'Jake Murray', 'Cam Cullinan', 'Brandon Barton'],
        'Work Type': ['DCO', 'ACT', 'DCO', 'SRO', 'DCO', 'ACT', 'DCO'],
        'WO#': [101, 102, 103, 104, 105, 106, 107],
        'Duration': [1.5, 2.0, 0.75, 3.1, 1.2, 2.5, 1.0] # <-- The crucial column with numeric data
    }
    df_filtered = pd.DataFrame(data)

    st.markdown("### Sample Data Being Used:")
    st.dataframe(df_filtered)

    # =====================================================
    # SECTION 2: KPIs (Using the sample data)
    # =====================================================
    st.markdown("### 📌 Work Orders KPIs")
    
    try:
        # --- KPI Calculations ---
        # Note: The '.str.extract' part is removed because 'Duration' is already a number
        duration = df_filtered["Duration"] 
        total_jobs = df_filtered["WO#"].nunique()
        avg_duration = duration.mean() or 0
        max_duration = duration.max() or 0
        min_duration = duration.min() or 0
        tech_count = df_filtered["Technician"].nunique()
        avg_jobs_per_tech = total_jobs / tech_count if tech_count else 0
        
        # New KPI calculation
        avg_duration_per_type = df_filtered.groupby('Work Type')['Duration'].mean()
        combined_avg_duration_by_type = avg_duration_per_type.mean() or 0

        # --- KPI Display ---
        st.success("✅ KPI Calculation Complete. Displaying metrics now.")
        
        k1, k2, k3 = st.columns(3)
        k1.metric("🔧 Total Jobs", total_jobs)
        k2.metric("👨‍🔧 Technicians", tech_count)
        k3.metric("📈 Avg Jobs per Tech", f"{avg_jobs_per_tech:.1f}")

        k4, k5, k6, k7 = st.columns(4)
        k4.metric("🕒 Avg Duration (hrs)", f"{avg_duration:.2f}")
        k5.metric("⏱️ Longest Duration (hrs)", f"{max_duration:.2f}")
        k6.metric("⚡ Shortest Duration (hrs)", f"{min_duration:.2f}")
        k7.metric("📋 Avg by Work Type (hrs)", f"{combined_avg_duration_by_type:.2f}")

    except Exception as e:
        st.error(f"A critical error occurred even with perfect data: {e}")

# Run the test function
run_kpi_test()
