import streamlit as st
import pandas as pd
import plotly.express as px
import os

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
    # SECTION 1: WORK ORDERS DASHBOARD (unchanged)
    # =================================================
    st.sidebar.header("📁 Work Orders File")
    saved_folder = "saved_uploads"
    os.makedirs(saved_folder, exist_ok=True)

    mode = st.sidebar.radio("Select Mode", ["Upload New Work Orders File", "Load Existing Work Orders File"], key="wo_mode")
    df = None

    if mode == "Upload New Work Orders File":
        uploaded_file = st.sidebar.file_uploader("Upload Work Orders CSV", type=["csv"])
        custom_filename = st.sidebar.text_input("Enter filename to save (no extension):", key="wo_filename")

        if uploaded_file and custom_filename:
            save_path = os.path.join(saved_folder, custom_filename + ".csv")
            with open(save_path, "wb") as f:
                f.write(uploaded_file.getbuffer())
            st.sidebar.success(f"File saved as: {custom_filename}.csv")
            df = pd.read_csv(save_path)
        elif uploaded_file:
            st.sidebar.warning("Please enter a file name to save.")
    else:
        saved_files = [f for f in os.listdir(saved_folder) if f.endswith(".csv")]
        if not saved_files:
            st.warning("No saved files found. Please upload one first.")
            return
        selected_file = st.sidebar.selectbox("Select a saved file", saved_files, key="wo_select")
        if selected_file:
            df = pd.read_csv(os.path.join(saved_folder, selected_file))
        if st.sidebar.button("🗑 Delete Selected Work Orders File"):
            os.remove(os.path.join(saved_folder, selected_file))
            st.sidebar.success(f"Deleted {selected_file}")
            st.experimental_rerun()

    if df is None:
        st.info("Please upload or load a Work Orders file to begin.")
        return

    # --- Work Orders data processing & KPIs ---
    df["Date When"] = pd.to_datetime(df["Date When"], errors="coerce")
    df = df.dropna(subset=["Date When"])
    df["Day"] = df["Date When"].dt.date

    if "Techinician" in df.columns and "Technician" not in df.columns:
        df.rename(columns={"Techinician": "Technician"}, inplace=True)

    min_day, max_day = df["Day"].min(), df["Day"].max()

    st.subheader("F I L T E R S")
    start_date, end_date = st.date_input("📅 Date Range", [min_day, max_day],
                                         min_value=min_day, max_value=max_day)
    df_filtered = df[(df["Day"] >= start_date) & (df["Day"] <= end_date)]
    if not df_filtered.empty:
        techs = sorted(df_filtered["Technician"].unique())
        work_types = sorted(df_filtered["Work Type"].unique())
        col1, col2 = st.columns(2)
        with col1:
            selected_techs = st.multiselect("👨‍🔧 Select Technician(s)", techs, default=techs)
        with col2:
            selected_work_types = st.multiselect("📋 Select Work Type(s)", work_types, default=work_types)
        df_filtered = df_filtered[
            df_filtered["Technician"].isin(selected_techs) &
            df_filtered["Work Type"].isin(selected_work_types)
        ]
    if df_filtered.empty:
        st.warning("No data available for the selected filters.")
        return

    st.markdown("### 📌 Work Orders KPIs")
    duration = pd.to_numeric(df_filtered["Duration"].str.extract(r"(\d+\.?\d*)")[0], errors="coerce")
    total_jobs = df_filtered["WO#"].nunique()
    avg_duration = duration.mean() or 0
    tech_count = df_filtered["Technician"].nunique()
    avg_jobs_per_tech = total_jobs / tech_count if tech_count else 0
    max_duration = duration.max() or 0
    min_duration = duration.min() or 0

    k1, k2, k3 = st.columns(3)
    k1.metric("🔧 Total Jobs", total_jobs)
    k2.metric("👨‍🔧 Technicians", tech_count)
    k3.metric("📈 Avg Jobs per Tech", f"{avg_jobs_per_tech:.1f}")

    k4, k5, k6 = st.columns(3)
    k4.metric("🕒 Avg Duration (hrs)", f"{avg_duration:.2f}")
    k5.metric("⏱️ Longest Duration (hrs)", f"{max_duration:.2f}")
    k6.metric("⚡ Shortest Duration (hrs)", f"{min_duration:.2f}")

    grouped_overall = (
        df_filtered.groupby(["Technician", "Work Type"])
        .agg(Total_Jobs=("WO#", "nunique"),
             Average_Duration=("Duration", lambda x: pd.to_numeric(
                 x.str.extract(r"(\d+\.?\d*)")[0], errors="coerce").mean()))
        .reset_index()
    )

    avg_duration_by_worktype = (
        df_filtered.groupby("Work Type")
        .agg(Average_Duration=("Duration", lambda x: pd.to_numeric(
            x.str.extract(r"(\d+\.?\d*)")[0], errors="coerce").mean()))
        .reset_index()
    )

    st.subheader("📊 Work Orders Charts")
    fig1 = px.bar(grouped_overall, x="Work Type", y="Total_Jobs",
                  color="Technician", title="Jobs by Work Type & Technician", template="plotly_dark")
    st.plotly_chart(fig1, use_container_width=True)

    fig2 = px.bar(grouped_overall, x="Work Type", y="Average_Duration",
                  color="Technician", title="Avg Duration by Work Type & Technician", template="plotly_dark")
    st.plotly_chart(fig2, use_container_width=True)

    st.markdown("---")

    # =====================================================
    # SECTION 2: TECHNICIAN RE-WORK ANALYSIS (UPDATED)
    # =====================================================
    st.markdown("<h2 style='color:#8BC53F;'>🔁 Technician Re-Work Analysis</h2>", unsafe_allow_html=True)

    re_mode = st.sidebar.radio("Select Mode for Re-Work File",
                               ["Upload New Re-Work File", "Load Existing Re-Work File"],
                               key="re_mode")
    df_rework = None

    if re_mode == "Upload New Re-Work File":
        re_file = st.sidebar.file_uploader("Upload Technician Assessment File (CSV or TXT)",
                                           type=["csv", "txt"])
        re_filename = st.sidebar.text_input("Enter name to save (no extension):", key="re_filename")

        if re_file and re_filename:
            save_path = os.path.join(saved_folder, re_filename + ".csv")
            with open(save_path, "wb") as f:
                f.write(re_file.getbuffer())
            st.sidebar.success(f"Re-Work File saved as: {re_filename}.csv")
            df_rework = pd.read_csv(save_path, header=None)
        elif re_file:
            st.sidebar.warning("Please enter a file name to save.")
    else:
        saved_files = [f for f in os.listdir(saved_folder) if f.endswith(".csv")]
        if saved_files:
            selected_re_file = st.sidebar.selectbox("Select saved Re-Work file", saved_files, key="re_select")
            df_rework = pd.read_csv(os.path.join(saved_folder, selected_re_file), header=None)
        else:
            st.sidebar.warning("No saved files found for Re-Work.")

    # --- Parse Re-Work File ---
    if df_rework is not None and not df_rework.empty:
        try:
            # Determine which rows start with "Install" in column 1
            df_rework["col1_str"] = df_rework[1].astype(str)
            install_mask = df_rework["col1_str"].str.startswith("Install", na=False)

            # Split into two groups
            df_install = df_rework[install_mask].iloc[:, [0, 2, 3, 4]]
            df_noninstall = df_rework[~install_mask].iloc[:, [0, 1, 2, 3]]

            # Combine back
            df_combined = pd.concat([df_install, df_noninstall], ignore_index=True)
            df_combined.columns = ["Technician", "Total_Jobs", "Rework", "Rework_Percentage"]

            # Clean & convert
            df_combined["Technician"] = df_combined["Technician"].astype(str).str.replace('"', '').str.strip()
            df_combined["Total_Jobs"] = pd.to_numeric(df_combined["Total_Jobs"], errors="coerce")
            df_combined["Rework"] = pd.to_numeric(df_combined["Rework"], errors="coerce")
            df_combined["Rework_Percentage"] = (
                df_combined["Rework_Percentage"].astype(str)
                .str.replace("%", "")
                .str.replace('"', "")
                .str.strip()
            )
            df_combined["Rework_Percentage"] = pd.to_numeric(df_combined["Rework_Percentage"], errors="coerce")

            # Display KPIs
            st.markdown("### 📌 Re-Work KPIs")
            total_jobs_rw = df_combined["Total_Jobs"].sum()
            total_repeats = df_combined["Rework"].sum()
            avg_repeat_pct = df_combined["Rework_Percentage"].mean()

            c1, c2, c3 = st.columns(3)
            c1.metric("🔧 Total Jobs", int(total_jobs_rw))
            c2.metric("🔁 Total Reworks", int(total_repeats))
            c3.metric("📈 Avg Rework %", f"{avg_repeat_pct:.1f}%")

            st.markdown("### 🧾 Re-Work Summary Table")
            st.dataframe(df_combined, use_container_width=True)

            st.markdown("### 📊 Rework % by Technician")
            fig_re = px.bar(df_combined.sort_values("Rework_Percentage", ascending=False),
                            x="Technician", y="Rework_Percentage",
                            title="Technician Rework % (Sorted Highest to Lowest)",
                            text="Rework_Percentage",
                            color="Rework_Percentage", template="plotly_dark",
                            color_continuous_scale="Viridis")
            fig_re.update_traces(textposition="outside")
            st.plotly_chart(fig_re, use_container_width=True)

            # Combined comparison with Work Orders
            if df is not None:
                merged = pd.merge(
                    grouped_overall.groupby("Technician")["Average_Duration"].mean().reset_index(),
                    df_combined[["Technician", "Rework_Percentage"]],
                    on="Technician", how="inner"
                )
                st.markdown("### ⚙️ Work Orders vs Re-Work Comparison")
                fig_combined = px.bar(
                    merged.melt(id_vars="Technician", value_vars=["Average_Duration", "Rework_Percentage"]),
                    x="Technician", y="value", color="variable",
                    barmode="group",
                    title="Avg Duration vs Rework % by Technician",
                    template="plotly_dark"
                )
                st.plotly_chart(fig_combined, use_container_width=True)

            # Download option
            csv_rework = df_combined.to_csv(index=False).encode("utf-8")
            st.download_button("⬇️ Download Re-Work Summary CSV",
                               data=csv_rework,
                               file_name="rework_summary.csv",
                               mime="text/csv")

        except Exception as e:
            st.error(f"Error parsing re-work file: {e}")
    else:
        st.info("Upload or load a Re-Work (Technician Assessment) file to see analysis.")
