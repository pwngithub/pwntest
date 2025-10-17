import streamlit as st
import pandas as pd
import altair as alt
from datetime import datetime
from branding import get_colors, apply_theme

def run_workorders_dashboard():
    # Apply theme
    apply_theme()
    colors = get_colors()

    # --- PAGE HEADER ---
    st.markdown(
        f"<h1 style='color:{colors['text']}; text-align:center; margin-bottom:10px;'>🧾 Work Orders Dashboard</h1>",
        unsafe_allow_html=True
    )
    st.markdown("<hr style='border:1px solid #8BC53F; margin-bottom:20px;'>", unsafe_allow_html=True)

    # --- FILE UPLOAD ---
    uploaded_file = st.sidebar.file_uploader("📁 Upload Work Orders CSV", type=["csv"])
    if uploaded_file is None:
        st.info("📤 Upload a CSV file to begin exploring Work Orders.")
        return

    # --- LOAD & CLEAN DATA ---
    df = pd.read_csv(uploaded_file)
    df.columns = df.columns.str.strip().str.title()

    # Detect Date Column
    date_col = next((col for col in df.columns if "date" in col.lower()), None)
    if date_col is None:
        st.error("⚠️ No date column found in uploaded file. Please include a column with 'Date' in the name.")
        return

    # Convert numeric fields
    for col in ["Duration"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    # --- SIDEBAR FILTERS ---
    st.sidebar.markdown("### 🔍 Filter Options")
    df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
    min_date, max_date = df[date_col].min(), df[date_col].max()
    start_date, end_date = st.sidebar.date_input(
        "📅 Select Date Range",
        [min_date, max_date] if pd.notna(min_date) and pd.notna(max_date) else [datetime.today(), datetime.today()]
    )

    techs = df["Technician"].unique() if "Technician" in df.columns else []
    selected_techs = st.sidebar.multiselect("👷 Select Technician(s)", options=techs, default=techs)

    work_types = df["Work Type"].unique() if "Work Type" in df.columns else []
    selected_types = st.sidebar.multiselect("⚙️ Select Work Type(s)", options=work_types, default=work_types)

    # --- FILTER DATA ---
    mask = (df[date_col] >= pd.Timestamp(start_date)) & (df[date_col] <= pd.Timestamp(end_date))
    if "Technician" in df.columns:
        mask &= df["Technician"].isin(selected_techs)
    if "Work Type" in df.columns:
        mask &= df["Work Type"].isin(selected_types)

    filtered_df = df.loc[mask].copy()
    if filtered_df.empty:
        st.warning("No records match your filters.")
        return

    # --- KPI CARDS ---
    total_jobs = len(filtered_df)
    total_duration = filtered_df["Duration"].sum() if "Duration" in filtered_df.columns else 0
    avg_duration = filtered_df["Duration"].mean() if "Duration" in filtered_df.columns else 0
    unique_techs = filtered_df["Technician"].nunique() if "Technician" in filtered_df.columns else 0

    card_style = (
        "background-color:#1c1c1c; border:1px solid #003865; border-radius:12px; "
        "padding:15px; color:white; text-align:center; box-shadow:0 2px 6px rgba(0,0,0,0.3);"
    )

    col1, col2, col3, col4 = st.columns(4)
    col1.markdown(f"<div style='{card_style}'><h4>Total Work Orders</h4><h2 style='color:#8BC53F'>{total_jobs:,}</h2></div>", unsafe_allow_html=True)
    col2.markdown(f"<div style='{card_style}'><h4>Total Duration</h4><h2 style='color:#8BC53F'>{total_duration:.1f} hrs</h2></div>", unsafe_allow_html=True)
    col3.markdown(f"<div style='{card_style}'><h4>Average Duration</h4><h2 style='color:#8BC53F'>{avg_duration:.2f} hrs</h2></div>", unsafe_allow_html=True)
    col4.markdown(f"<div style='{card_style}'><h4>Active Technicians</h4><h2 style='color:#8BC53F'>{unique_techs}</h2></div>", unsafe_allow_html=True)

    st.markdown("<hr style='border:1px solid #8BC53F; margin:25px 0;'>", unsafe_allow_html=True)

    # --- CHART: Work Orders by Technician (HORIZONTAL) ---
    st.subheader("📈 Work Orders by Technician")
    if "Technician" in filtered_df.columns:
        chart = (
            alt.Chart(filtered_df)
            .mark_bar(color="#003865", cornerRadiusTopLeft=4, cornerRadiusTopRight=4)
            .encode(
                y=alt.Y("Technician:N", sort="-x", title="Technician"),
                x=alt.X("count():Q", title="Work Order Count"),
                tooltip=["Technician", "count()"]
            )
            .properties(height=400)
        )
        st.altair_chart(chart, use_container_width=True)

    # --- CHART: Average Duration by Work Type (HORIZONTAL) ---
    if "Work Type" in filtered_df.columns and "Duration" in filtered_df.columns:
        st.subheader("🕒 Average Duration by Work Type")
        avg_chart = (
            alt.Chart(filtered_df)
            .mark_bar(color="#8BC53F", cornerRadiusTopLeft=4, cornerRadiusTopRight=4)
            .encode(
                y=alt.Y("Work Type:N", sort="-x", title="Work Type"),
                x=alt.X("mean(Duration):Q", title="Average Duration (hrs)"),
                tooltip=["Work Type", "mean(Duration)"]
            )
            .properties(height=400)
        )
        st.altair_chart(avg_chart, use_container_width=True)

    # --- SUMMARY TABLE ---
    st.markdown("<hr style='border:1px solid #003865; margin:25px 0;'>", unsafe_allow_html=True)
    st.subheader("📊 Work Order Summary Table")

    display_cols = [col for col in [date_col, "Technician", "Work Type", "Duration", "Status"] if col in filtered_df.columns]
    st.dataframe(
        filtered_df[display_cols].style.set_table_styles(
            [
                {"selector": "thead th", "props": [("background-color", "#003865"), ("color", "white"), ("font-weight", "bold")]},
                {"selector": "tbody tr:nth-child(even)", "props": [("background-color", "#2a2a2a")]},
                {"selector": "tbody tr:nth-child(odd)", "props": [("background-color", "#1c1c1c")]},
            ]
        ),
        use_container_width=True
    )
