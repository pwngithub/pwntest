# --- KPIs ---
    st.markdown("### 📌 Work Orders KPIs")
    duration = pd.to_numeric(df_filtered["Duration"].str.extract(r"(\d+\.?\d*)")[0], errors="coerce")
    total_jobs = df_filtered["WO#"].nunique()
    avg_duration = duration.mean() or 0
    max_duration = duration.max() or 0
    min_duration = duration.min() or 0
    tech_count = df_filtered["Technician"].nunique()
    avg_jobs_per_tech = total_jobs / tech_count if tech_count else 0

    # --- New KPI Calculation: Combined Average Duration per Work Type ---
    # Create a temporary numeric duration column for calculation
    df_calc = df_filtered.copy()
    df_calc['Duration_numeric'] = pd.to_numeric(df_calc['Duration'].str.extract(r'(\d+\.?\d*)')[0], errors='coerce')
    # Group by 'Work Type' and calculate the mean duration for each type
    avg_duration_per_type = df_calc.groupby('Work Type')['Duration_numeric'].mean()
    # Calculate the average of those averages
    combined_avg_duration_by_type = avg_duration_per_type.mean() or 0

    k1, k2, k3 = st.columns(3)
    k1.metric("🔧 Total Jobs", total_jobs)
    k2.metric("👨‍🔧 Technicians", tech_count)
    k3.metric("📈 Avg Jobs per Tech", f"{avg_jobs_per_tech:.1f}")

    k4, k5, k6, k7 = st.columns(4)
    k4.metric("🕒 Avg Duration (hrs)", f"{avg_duration:.2f}")
    k5.metric("⏱️ Longest Duration (hrs)", f"{max_duration:.2f}")
    k6.metric("⚡ Shortest Duration (hrs)", f"{min_duration:.2f}")
    k7.metric("📋 Avg by Work Type (hrs)", f"{combined_avg_duration_by_type:.2f}")
