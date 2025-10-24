import streamlit as st
import pandas as pd
import plotly.express as px
import os
from plotly.subplots import make_subplots
import plotly.graph_objects as go
import re


def run_workorders_dashboard():
    st.set_page_config(
        page_title="PBB Work Orders Dashboard",
        layout="wide",
        initial_sidebar_state="expanded"
    )

    # --- Custom CSS ---
    st.markdown("""
    <style>
    .stApp {background-color: #0E1117;}
    div[data-testid="metric-container"] {
        background-color: #262730;
        border: 1px solid #3c3c3c;
        padding: 15px;
        border-radius: 10px;
        box-shadow: 0 4px 8px rgba(0,0,0,0.4);
        transition: transform 0.2s;
        color: #FAFAFA;
    }
    div[data-testid="metric-container"]:hover {
        transform: scale(1.05);
        border-color: #8BC53F;
    }
    div[data-testid="metric-container"] > label {color: #A0A0A0;}
    .logo-container {text-align:center;margin-bottom:20px;}
    .main-title {color:#FFFFFF;text-align:center;font-weight:bold;}
    </style>
    """, unsafe_allow_html=True)

    # --- Logo + Title ---
    st.markdown("""
    <div class='logo-container'>
        <img src='https://images.squarespace-cdn.com/content/v1/651eb4433b13e72c1034f375/
        369c5df0-5363-4827-b041-1add0367f447/PBB+long+logo.png?format=1500w' width='400'>
    </div>
    """, unsafe_allow_html=True)
    st.markdown("<h1 class='main-title'>🛠 Pioneer Broadband Work Orders Dashboard</h1>", unsafe_allow_html=True)
    st.markdown("<hr>", unsafe_allow_html=True)

    # =================================================
    # SIDEBAR FILE MANAGEMENT
    # =================================================
    st.sidebar.header("📂 Data Files")
    saved_folder = "saved_uploads"
    os.makedirs(saved_folder, exist_ok=True)

    # --- Work Orders Upload ---
    st.sidebar.subheader("🧾 Work Orders File")
    mode_wo = st.sidebar.radio("Mode:", ["Upload New", "Load Existing"], key="wo_mode")
    df = None

    if mode_wo == "Upload New":
        uploaded_wo = st.sidebar.file_uploader("Upload Tech Workflow CSV", type=["csv"], key="wo_upload")
        custom_wo_name = st.sidebar.text_input("Save as (no extension):", key="wo_name")
        if uploaded_wo and custom_wo_name:
            save_path = os.path.join(saved_folder, custom_wo_name + ".csv")
            with open(save_path, "wb") as f:
                f.write(uploaded_wo.getbuffer())
            st.sidebar.success(f"✅ File saved as: {custom_wo_name}.csv")
            df = pd.read_csv(save_path)

            # Fix common column typos
            if "Techinician" in df.columns and "Technician" not in df.columns:
                df.rename(columns={"Techinician": "Technician"}, inplace=True)
        elif uploaded_wo:
            st.sidebar.warning("Please enter a filename before saving.")
    else:
        saved_files = [f for f in os.listdir(saved_folder) if f.endswith(".csv")]
        selected_wo = st.sidebar.selectbox("Select Saved File", saved_files, key="wo_select")
        if selected_wo:
            df = pd.read_csv(os.path.join(saved_folder, selected_wo))

            # Fix common column typos
            if "Techinician" in df.columns and "Technician" not in df.columns:
                df.rename(columns={"Techinician": "Technician"}, inplace=True)

    # --- Rework Upload ---
    st.sidebar.subheader("🔁 Installation Rework File")
    mode_re = st.sidebar.radio("Mode:", ["Upload New", "Load Existing"], key="re_mode")
    df_rework = None

    if mode_re == "Upload New":
        uploaded_re = st.sidebar.file_uploader("Upload Installation Assessment (CSV/TXT)", type=["csv", "txt"], key="re_upload")
        custom_re_name = st.sidebar.text_input("Save as (no extension):", key="re_name")
        if uploaded_re and custom_re_name:
            save_path = os.path.join(saved_folder, custom_re_name + ".csv")
            with open(save_path, "wb") as f:
                f.write(uploaded_re.getbuffer())
            st.sidebar.success(f"✅ Rework File saved as: {custom_re_name}.csv")
            df_rework = pd.read_csv(save_path, header=None)
        elif uploaded_re:
            st.sidebar.warning("Please enter a filename before saving.")
    else:
        saved_files = [f for f in os.listdir(saved_folder) if f.endswith(".csv")]
        selected_re = st.sidebar.selectbox("Select Rework File", saved_files, key="re_select")
        if selected_re:
            df_rework = pd.read_csv(os.path.join(saved_folder, selected_re), header=None)

    st.markdown("---")

    # =====================================================
    # 🧾 WORK ORDERS SECTION
    # =====================================================
    if "df" in locals() and df is not None and not df.empty:
        with st.expander("🧾 Work Orders Dashboard", expanded=True):

            # --- Identify correct work type column ---
            type_candidates = [c for c in df.columns if c.strip().lower() in ["type", "work type", "wo type"]]
            if not type_candidates:
                st.error("⚠️ No 'Work Type' or 'Type' column found in the uploaded file.")
                st.stop()
            type_col = type_candidates[0]

            # --- Identify a valid date column ---
            date_cols = [c for c in df.columns if str(c).lower() in ["date when", "date", "work date", "completed", "completion date"]]
            if not date_cols:
                st.error("⚠️ No date column found. Please include a date field.")
                st.stop()

            date_col = date_cols[0]
            df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
            df = df.dropna(subset=[date_col])
            df["Day"] = df[date_col].dt.date

            # --- Filters ---
            min_day, max_day = df["Day"].min(), df["Day"].max()
            st.subheader("📅 Filters")
            start_date, end_date = st.date_input("Select Date Range:", [min_day, max_day], min_value=min_day, max_value=max_day)
            df_filtered = df[(df["Day"] >= start_date) & (df["Day"] <= end_date)]

            techs = sorted(df_filtered["Technician"].unique())
            types = sorted(df_filtered[type_col].unique())
            col1, col2 = st.columns(2)
            with col1:
                selected_techs = st.multiselect("👨‍🔧 Technicians", techs, default=techs)
            with col2:
                selected_types = st.multiselect(f"📋 {type_col}", types, default=types)
            df_filtered = df_filtered[df_filtered["Technician"].isin(selected_techs) & df_filtered[type_col].isin(selected_types)]

            if df_filtered.empty:
                st.warning("No data matches your filters.")
            else:
                # --- Clean work type ---
                df_filtered[type_col] = (
                    df_filtered[type_col]
                    .astype(str)
                    .str.replace(r"[:_\-]+", " ", regex=True)
                    .str.replace(r"\s+", " ", regex=True)
                    .str.strip()
                    .str.upper()
                )

                # --- Duration Parser ---
                def parse_duration(val):
                    if pd.isna(val):
                        return None
                    val = str(val).strip().lower().replace(" ", "")
                    if re.match(r"^\d+:\d+$", val):
                        try:
                            h, m = val.split(":")
                            return float(h) * 60 + float(m)
                        except Exception:
                            return None
                    match = re.match(r"(?:(\d+(?:\.\d+)?)h(?:r|rs)?)?(?:(\d+(?:\.\d+)?)m(?:in|ins)?)?", val)
                    if match:
                        h = float(match.group(1)) if match.group(1) else 0
                        m = float(match.group(2)) if match.group(2) else 0
                        if h == 0 and m == 0:
                            return None
                        return h * 60 + m
                    if "h" in val:
                        try:
                            num = float(re.findall(r"[\d\.]+", val)[0])
                            return num * 60
                        except Exception:
                            return None
                    if "m" in val:
                        try:
                            num = float(re.findall(r"[\d\.]+", val)[0])
                            return num
                        except Exception:
                            return None
                    try:
                        num = float(val)
                        return num if num > 0 else None
                    except Exception:
                        return None

                df_filtered["Duration_Num"] = df_filtered["Duration"].apply(parse_duration)

                # --- KPIs ---
                total_jobs = df_filtered["WO#"].nunique()
                avg_duration = df_filtered["Duration_Num"].mean()
                max_duration = df_filtered["Duration_Num"].max()
                min_duration = df_filtered["Duration_Num"].min()
                tech_count = df_filtered["Technician"].nunique()
                avg_jobs_per_tech = total_jobs / tech_count if tech_count else 0

                st.markdown("""
                <div style='margin-top:10px;margin-bottom:10px;padding:10px 15px;border-radius:10px;
                            background:linear-gradient(90deg,#1c1c1c 0%,#004aad 100%);'>
                    <h3 style='color:white;margin:0;'>📊 Work Orders KPIs</h3>
                </div>
                """, unsafe_allow_html=True)

                c1, c2, c3 = st.columns(3)
                c1.metric("🔧 Total Jobs", total_jobs)
                c2.metric("👨‍🔧 Technicians", tech_count)
                c3.metric("📈 Avg Jobs per Tech", f"{avg_jobs_per_tech:.1f}")

                c4, c5, c6 = st.columns(3)
                c4.metric("🕒 Avg Duration (min)", f"{avg_duration:.1f}")
                c5.metric("⏱️ Longest Duration (min)", f"{max_duration:.1f}")
                c6.metric("⚡ Shortest Duration (min)", f"{min_duration:.1f}")

                # --- Average Duration by Work Type ---
                avg_by_type = (
                    df_filtered.groupby(type_col, as_index=False)["Duration_Num"]
                    .mean()
                    .rename(columns={"Duration_Num": "Avg_Duration_Min"})
                    .sort_values("Avg_Duration_Min", ascending=False)
                )
                overall_avg = df_filtered["Duration_Num"].mean()

                st.markdown(f"""
                <div style='margin-top:18px;margin-bottom:10px;padding:10px 15px;border-radius:10px;
                            background:linear-gradient(90deg,#1c1c1c 0%,#5AA9E6 100%);'>
                    <h4 style='color:white;margin:0;'>⏳ Average Duration by {type_col} (Minutes)</h4>
                </div>
                """, unsafe_allow_html=True)

                fig = px.bar(
                    avg_by_type,
                    x=type_col,
                    y="Avg_Duration_Min",
                    text="Avg_Duration_Min",
                    color="Avg_Duration_Min",
                    color_continuous_scale="Viridis",
                    template="plotly_dark"
                )
                fig.add_hline(
                    y=overall_avg,
                    line_dash="dash",
                    line_color="cyan",
                    annotation_text=f"Overall Avg ({overall_avg:.1f} min)",
                    annotation_font_color="cyan"
                )
                fig.update_traces(texttemplate='%{text:.1f} min', textposition='outside')
                st.plotly_chart(fig, use_container_width=True)

                # --- Pivot: Avg Duration per Technician per Work Type ---
                all_techs = sorted(df_filtered["Technician"].unique())
                all_types = sorted(df_filtered[type_col].unique())

                pivot = (
                    df_filtered.pivot_table(
                        index="Technician",
                        columns=type_col,
                        values="Duration_Num",
                        aggfunc="mean"
                    )
                    .reindex(index=all_techs, columns=all_types)
                )

                pivot = pivot.replace({None: pd.NA, "None": pd.NA}).astype("Float64")
                pivot["Overall Avg (min)"] = pivot.mean(axis=1, skipna=True).astype("Float64").round(1)
                pivot = pivot.sort_values("Overall Avg (min)", ascending=False)

                styled = (
                    pivot.style
                    .format("{:.1f}", na_rep="—")
                    .background_gradient(cmap="viridis", axis=None)
                )

                st.markdown(f"""
                <div style='margin-top:25px;margin-bottom:10px;padding:10px 15px;border-radius:10px;
                            background:linear-gradient(90deg,#1c1c1c 0%,#8BC53F 100%);'>
                    <h4 style='color:white;margin:0;'>👨‍🔧 Average Duration per Technician per {type_col} (Minutes)</h4>
                </div>
                """, unsafe_allow_html=True)
                st.dataframe(styled, use_container_width=True)
    else:
        st.info("📁 Please upload or select a Tech Workflow file to view the Work Orders dashboard.")
