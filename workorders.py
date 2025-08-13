
import streamlit as st
import pandas as pd
import plotly.express as px
import os
from datetime import timedelta

def run_workorders_dashboard():
    st.set_page_config(page_title="Technician Dashboard", layout="wide")

    st.markdown("""
    <div style='text-align:center;'>
    <img src='https://images.squarespace-cdn.com/content/v1/651eb4433b13e72c1034f375/369c5df0-5363-4827-b041-1add0367f447/PBB+long+logo.png?format=1500w' width='500'>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("<h1 style='color:#4A648C;text-align:center;'>🛠 Pioneer Broadband Work Orders Dashboard</h1>", unsafe_allow_html=True)
    st.markdown("<hr>", unsafe_allow_html=True)

    # Create folder for saved uploads
    saved_folder = "saved_uploads"
    os.makedirs(saved_folder, exist_ok=True)

    mode = st.radio("Select Mode", ["Upload New File", "Load Existing File"])

    if mode == "Upload New File":
        uploaded_file = st.file_uploader("Upload Technician Workflow CSV", type=["csv"])
        custom_filename = st.text_input("Enter a name to save this file as (without extension):")

        if uploaded_file and custom_filename:
            save_path = os.path.join(saved_folder, custom_filename + ".csv")
            with open(save_path, "wb") as f:
                f.write(uploaded_file.read())
            st.success(f"File saved as: {save_path}")
            df = pd.read_csv(save_path)

        elif uploaded_file and not custom_filename:
            st.warning("Please enter a file name to save.")

        else:
            return

    else:  # Load from existing saved files
        saved_files = [f for f in os.listdir(saved_folder) if f.endswith(".csv")]
        if not saved_files:
            st.warning("No saved files found. Please upload one first.")
            return
        selected_file = st.selectbox("Select a saved file to load", saved_files)

        st.markdown("### 🗑 Delete a Saved File")
        file_to_delete = st.selectbox("Select a file to delete", saved_files, key="delete_file")
        if st.button("Delete Selected File"):
            os.remove(os.path.join(saved_folder, file_to_delete))
            st.success(f"{file_to_delete} has been deleted.")
            st.experimental_rerun()

        df = pd.read_csv(os.path.join(saved_folder, selected_file))

    df["Date When"] = pd.to_datetime(df["Date When"], errors="coerce")
    df = df.dropna(subset=["Date When"])
    df["Day"] = df["Date When"].dt.date

    min_day = df["Day"].min()
    max_day = df["Day"].max()
    default_start = max_date - timedelta(days=29)
    if default_start < min_date:
        default_start = min_date
    start_date, end_date = st.date_input("📅 Select date range", value=(default_start, max_date), min_value=min_date, max_value=max_date)
    df = df[(df["Day"] >= start_date) & (df["Day"] <= end_date)]

    
    total_jobs = df["WO#"].nunique()
    avg_duration = pd.to_numeric(df["Duration"].str.extract(r"(\d+\.?\d*)")[0], errors="coerce").mean() or 0
    unique_statuses = df["Tech Status"].nunique()
    tech_count = df["Techinician"].nunique()
    avg_jobs_per_tech = total_jobs / tech_count if tech_count else 0
    num_days = (end_date - start_date).days + 1

    st.markdown("### 📌 Key Performance Indicators")
    k1, k2, k3, k4, k5, k6 = st.columns(6)
    k1.metric("🔧 Total Jobs", total_jobs)
    k2.metric("🕒 Avg Duration (hrs)", f"{avg_duration:.2f}")
    k3.metric("📋 Unique Statuses", unique_statuses)
    k4.metric("👨‍🔧 Total Technicians", tech_count)
    k5.metric("📈 Jobs per Technician", f"{avg_jobs_per_tech:.1f}")
    k6.metric("📆 Days Covered", num_days)

    total_entries = df["WO#"].count()
    duration_series = pd.to_numeric(df["Duration"].str.extract(r"(\d+\.?\d*)")[0], errors="coerce")
    max_duration = duration_series.max() or 0
    min_duration = duration_series.min() or 0

    k7, k8, k9 = st.columns(3)
    k7.metric("🧾 Total Entries", total_entries)
    k8.metric("⏱️ Longest Duration (hrs)", f"{max_duration:.2f}")
    k9.metric("⏱️ Shortest Duration (hrs)", f"{min_duration:.2f}")


    st.markdown("---")

    grouped_overall = (df.groupby(["Techinician", "Work Type"])
                       .agg(Total_Jobs=("WO#", "nunique"),
                            Average_Duration=("Duration", lambda x: pd.to_numeric(x.str.extract(r"(\d+\.?\d*)")[0], errors="coerce").mean()))
                       .reset_index())

    fig1 = px.bar(grouped_overall, x="Work Type", y="Total_Jobs",
                  color="Techinician", title="Total Jobs by Work Type",
                  color_discrete_sequence=["#8BC53F"])
    fig1.update_layout(plot_bgcolor='white', title_font_color="#4A648C")
    st.plotly_chart(fig1, use_container_width=True)

    fig2 = px.bar(grouped_overall, x="Work Type", y="Average_Duration",
                  color="Techinician", title="Avg Duration by Work Type",
                  color_discrete_sequence=["#8BC53F"])
    fig2.update_layout(plot_bgcolor='white', title_font_color="#4A648C")
    st.plotly_chart(fig2, use_container_width=True)

    st.markdown("### 🗂 Breakout Table: Daily Summary")
    df_daily = (df.groupby(["Techinician", "Day", "Work Type"])
                .agg(Jobs_Completed=("WO#", "nunique"),
                     Total_Entries=("WO#", "count"),
                     Avg_Duration=("Duration", lambda x: pd.to_numeric(x.str.extract(r"(\d+\.?\d*)")[0], errors="coerce").mean()))
                .reset_index())
    st.dataframe(df_daily, use_container_width=True)

    st.markdown("### 📤 Export Overall Summary")
    csv = grouped_overall.to_csv(index=False).encode('utf-8')
    st.download_button("Download Summary CSV", data=csv, file_name="workorders_summary.csv", mime="text/csv")