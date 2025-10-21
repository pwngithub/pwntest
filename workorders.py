import streamlit as st
import pandas as pd
import plotly.express as px
import os
import sqlite3
from datetime import datetime

# ----------------------------------------
# SAFE INITIALIZATION
# ----------------------------------------
st.set_page_config(page_title="PBB Work Orders Dashboard", layout="wide", initial_sidebar_state="expanded")

# Determine persistent path (works on Streamlit Cloud or locally)
if os.path.exists("/mount/data"):
    BASE_FOLDER = "/mount/data/pbb_workorders"
else:
    BASE_FOLDER = os.path.join(os.path.expanduser("~"), "pbb_workorders")

os.makedirs(BASE_FOLDER, exist_ok=True)
SAVED_FOLDER = os.path.join(BASE_FOLDER, "saved_uploads")
os.makedirs(SAVED_FOLDER, exist_ok=True)
DB_PATH = os.path.join(BASE_FOLDER, "uploads.db")

# SQLite setup
conn = sqlite3.connect(DB_PATH)
conn.execute("""
    CREATE TABLE IF NOT EXISTS uploads (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        filename TEXT UNIQUE,
        path TEXT,
        uploaded_at TEXT
    )
""")
conn.commit()

# ----------------------------------------
# PAGE STYLING
# ----------------------------------------
st.markdown("""
<style>
.stApp { background-color: #0E1117; }
div[data-testid="metric-container"] {
    background-color: #262730; border: 1px solid #3c3c3c;
    padding: 15px; border-radius: 10px;
    box-shadow: 0 4px 8px rgba(0,0,0,0.4);
    color: #FAFAFA;
}
.main-title { color: #FFFFFF; text-align: center; font-weight: bold; }
.logo-container { text-align: center; margin-bottom: 20px; }
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div class='logo-container'>
  <img src='https://images.squarespace-cdn.com/content/v1/651eb4433b13e72c1034f375/369c5df0-5363-4827-b041-1add0367f447/PBB+long+logo.png?format=1500w' width='400'>
</div>
""", unsafe_allow_html=True)
st.markdown("<h1 class='main-title'>🛠 Pioneer Broadband Work Orders Dashboard</h1>", unsafe_allow_html=True)
st.markdown("<hr>", unsafe_allow_html=True)

# ----------------------------------------
# SIDEBAR: FILE MANAGEMENT
# ----------------------------------------
st.sidebar.header("📁 File Management")
mode = st.sidebar.radio("Select Mode", ["Upload New File", "Load Existing File"])
df = None

# --- Upload Mode ---
if mode == "Upload New File":
    uploaded_file = st.sidebar.file_uploader("Upload Technician Workflow CSV", type=["csv"])
    custom_filename = st.sidebar.text_input("Enter a name to save this file as (without extension):")

    if uploaded_file and custom_filename:
        save_path = os.path.join(SAVED_FOLDER, custom_filename + ".csv")
        try:
            with open(save_path, "wb") as f:
                f.write(uploaded_file.getbuffer())
            conn.execute(
                "INSERT OR REPLACE INTO uploads (filename, path, uploaded_at) VALUES (?, ?, ?)",
                (custom_filename + ".csv", save_path, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            )
            conn.commit()
            st.sidebar.success(f"✅ File saved to: {save_path}")
            df = pd.read_csv(save_path)
        except Exception as e:
            st.sidebar.error(f"❌ Error saving file: {e}")
    elif uploaded_file and not custom_filename:
        st.sidebar.warning("Please enter a name before saving.")

# --- Load Mode ---
elif mode == "Load Existing File":
    saved_files = [row[0] for row in conn.execute("SELECT filename FROM uploads ORDER BY uploaded_at DESC").fetchall()]
    if not saved_files:
        st.warning("No saved files found. Please upload one first.")
        st.stop()

    selected_file = st.sidebar.selectbox("Select a saved file to load", saved_files)
    if selected_file:
        path_row = conn.execute("SELECT path FROM uploads WHERE filename=?", (selected_file,)).fetchone()
        if path_row and os.path.exists(path_row[0]):
            st.sidebar.info(f"📂 Loaded from: {path_row[0]}")
            try:
                df = pd.read_csv(path_row[0])
            except Exception as e:
                st.error(f"Error reading file: {e}")
                st.stop()
        else:
            st.error("⚠️ File missing on disk. Please re-upload.")
            st.stop()

    # Delete File Option
    st.sidebar.markdown("---")
    st.sidebar.subheader("🗑 Delete a Saved File")
    file_to_delete = st.sidebar.selectbox("Select a file to delete", ["-"] + saved_files)
    if st.sidebar.button("Delete Selected File"):
        if file_to_delete and file_to_delete != "-":
            path_row = conn.execute("SELECT path FROM uploads WHERE filename=?", (file_to_delete,)).fetchone()
            if path_row and os.path.exists(path_row[0]):
                os.remove(path_row[0])
            conn.execute("DELETE FROM uploads WHERE filename=?", (file_to_delete,))
            conn.commit()
            st.sidebar.success(f"'{file_to_delete}' deleted.")
            st.experimental_rerun()

# --- Stop early if no DataFrame loaded ---
if df is None:
    st.info("Please upload or load a file to view data.")
    st.stop()

# ----------------------------------------
# DATA PROCESSING
# ----------------------------------------
df["Date When"] = pd.to_datetime(df["Date When"], errors="coerce")
df = df.dropna(subset=["Date When"])
df["Day"] = df["Date When"].dt.date
if "Techinician" in df.columns and "Technician" not in df.columns:
    df.rename(columns={"Techinician": "Technician"}, inplace=True)

min_day, max_day = df["Day"].min(), df["Day"].max()
st.subheader("F I L T E R S")
start_date, end_date = st.date_input("📅 Date Range", [min_day, max_day], min_value=min_day, max_value=max_day)

df_filtered = df[(df["Day"] >= start_date) & (df["Day"] <= end_date)]

if not df_filtered.empty:
    techs = sorted(df_filtered["Technician"].unique().tolist())
    work_types = sorted(df_filtered["Work Type"].unique().tolist())
    col1, col2 = st.columns(2)
    with col1:
        selected_techs = st.multiselect("👨‍🔧 Select Technician(s)", techs, default=techs)
    with col2:
        selected_work_types = st.multiselect("📋 Select Work Type(s)", work_types, default=work_types)
    df_filtered = df_filtered[df_filtered["Technician"].isin(selected_techs) & df_filtered["Work Type"].isin(selected_work_types)]

if df_filtered.empty:
    st.warning("No data for selected filters.")
    st.stop()

# ----------------------------------------
# KPI SECTION
# ----------------------------------------
st.markdown("### 📌 Key Performance Indicators")
total_jobs = df_filtered["WO#"].nunique()
duration_series = pd.to_numeric(df_filtered["Duration"].str.extract(r"(\d+\.?\d*)")[0], errors="coerce")
avg_duration = duration_series.mean() or 0
tech_count = df_filtered["Technician"].nunique()
avg_jobs_per_tech = total_jobs / tech_count if tech_count else 0
num_days = (end_date - start_date).days + 1
total_entries = df_filtered["WO#"].count()
max_duration = duration_series.max() or 0
min_duration = duration_series.min() or 0

kpi1, kpi2, kpi3 = st.columns(3)
kpi1.metric("🔧 Total Jobs", total_jobs)
kpi2.metric("👨‍🔧 Technicians", tech_count)
kpi3.metric("📈 Avg Jobs per Tech", f"{avg_jobs_per_tech:.1f}")
kpi4, kpi5, kpi6 = st.columns(3)
kpi4.metric("🕒 Avg Duration (hrs)", f"{avg_duration:.2f}")
kpi5.metric("⏱️ Longest Duration (hrs)", f"{max_duration:.2f}")
kpi6.metric("⏱️ Shortest Duration (hrs)", f"{min_duration:.2f}")

# ----------------------------------------
# CHARTS
# ----------------------------------------
grouped_overall = (df_filtered.groupby(["Technician", "Work Type"])
                   .agg(Total_Jobs=("WO#", "nunique"),
                        Average_Duration=("Duration", lambda x: pd.to_numeric(x.str.extract(r"(\d+\.?\d*)")[0], errors="coerce").mean()))
                   .reset_index())

tab1, tab2 = st.tabs(["📊 Charts", "📤 Export"])
with tab1:
    fig1 = px.bar(grouped_overall, x="Work Type", y="Total_Jobs", color="Technician", title="Jobs by Work Type & Technician", template="plotly_dark")
    st.plotly_chart(fig1, use_container_width=True)
    fig2 = px.bar(grouped_overall, x="Work Type", y="Average_Duration", color="Technician", title="Avg Duration by Work Type & Technician", template="plotly_dark")
    st.plotly_chart(fig2, use_container_width=True)

with tab2:
    csv = grouped_overall.to_csv(index=False).encode("utf-8")
    st.download_button("Download Summary CSV", data=csv, file_name="workorders_summary.csv", mime="text/csv")
    st.dataframe(grouped_overall, use_container_width=True)
