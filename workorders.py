import streamlit as st
import pandas as pd
import plotly.express as px
import os
from plotly.subplots import make_subplots
import plotly.graph_objects as go

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
        uploaded_wo = st.sidebar.file_uploader("Upload Work Orders CSV", type=["csv"], key="wo_upload")
        custom_wo_name = st.sidebar.text_input("Save as (no extension):", key="wo_name")
        if uploaded_wo and custom_wo_name:
            save_path = os.path.join(saved_folder, custom_wo_name + ".csv")
            with open(save_path, "wb") as f:
                f.write(uploaded_wo.getbuffer())
            st.sidebar.success(f"✅ Work Orders saved as: {custom_wo_name}.csv")
            df = pd.read_csv(save_path)
        elif uploaded_wo:
            st.sidebar.warning("Please enter a filename before saving.")
    else:
        saved_files = [f for f in os.listdir(saved_folder) if f.endswith(".csv")]
        selected_wo = st.sidebar.selectbox("Select Work Orders File", saved_files, key="wo_select")
        if selected_wo:
            df = pd.read_csv(os.path.join(saved_folder, selected_wo))

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
    if df is not None:
        with st.expander("🧾 Work Orders Dashboard", expanded=True):

            # --- Auto-detect date column ---
            date_cols = [col for col in df.columns if str(col).lower() in ["date when", "date", "work date", "completed", "completion date"]]
            if not date_cols:
                st.error("⚠️ No date column found. Please include 'Date When' or 'Date' column.")
                st.stop()
            date_col = date_cols[0]
            df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
            df = df.dropna(subset=[date_col])
            df["Day"] = df[date_col].dt.date

            if "Techinician" in df.columns and "Technician" not in df.columns:
                df.rename(columns={"Techinician": "Technician"}, inplace=True)

            # --- Filters ---
            min_day, max_day = df["Day"].min(), df["Day"].max()
            st.subheader("📅 Filters")
            start_date, end_date = st.date_input("Select Date Range:", [min_day, max_day], min_value=min_day, max_value=max_day)
            df_filtered = df[(df["Day"] >= start_date) & (df["Day"] <= end_date)]

            techs = sorted(df_filtered["Technician"].unique())
            work_types = sorted(df_filtered["Work Type"].unique())
            col1, col2 = st.columns(2)
            with col1:
                selected_techs = st.multiselect("👨‍🔧 Technicians", techs, default=techs)
            with col2:
                selected_work_types = st.multiselect("📋 Work Types", work_types, default=work_types)
            df_filtered = df_filtered[df_filtered["Technician"].isin(selected_techs) & df_filtered["Work Type"].isin(selected_work_types)]

            if df_filtered.empty:
                st.warning("No data matches your filters.")
            else:
                # --- KPI Header ---
                st.markdown("""
                <div style='margin-top:10px; margin-bottom:10px; padding:10px 15px; border-radius:10px;
                            background:linear-gradient(90deg, #1c1c1c 0%, #004aad 100%);'>
                    <h3 style='color:white; margin:0;'>📊 Work Orders KPIs</h3>
                </div>
                """, unsafe_allow_html=True)

                # --- KPI Calculations ---
                duration = pd.to_numeric(df_filtered["Duration"].str.extract(r"(\d+\.?\d*)")[0], errors="coerce")
                total_jobs = df_filtered["WO#"].nunique()
                avg_duration = duration.mean() or 0
                max_duration = duration.max() or 0
                min_duration = duration.min() or 0
                tech_count = df_filtered["Technician"].nunique()
                avg_jobs_per_tech = total_jobs / tech_count if tech_count else 0

                k1, k2, k3 = st.columns(3)
                k1.metric("🔧 Total Jobs", total_jobs)
                k2.metric("👨‍🔧 Technicians", tech_count)
                k3.metric("📈 Avg Jobs per Tech", f"{avg_jobs_per_tech:.1f}")

                k4, k5, k6 = st.columns(3)
                k4.metric("🕒 Avg Duration (hrs)", f"{avg_duration:.2f}")
                k5.metric("⏱️ Longest Duration (hrs)", f"{max_duration:.2f}")
                k6.metric("⚡ Shortest Duration (hrs)", f"{min_duration:.2f}")

                # --- Overall Average Duration by Work Order Type (Minutes) ---
                st.markdown("""
                <div style='margin-top:18px; margin-bottom:10px; padding:10px 15px; border-radius:10px;
                            background:linear-gradient(90deg, #1c1c1c 0%, #5AA9E6 100%);'>
                    <h4 style='color:white; margin:0;'>⏳ Overall Average Duration by Work Order Type (Minutes)</h4>
                </div>
                """, unsafe_allow_html=True)

                avg_by_type = (
                    df_filtered.groupby("Work Type")["Duration"]
                    .apply(lambda x: pd.to_numeric(x.str.extract(r'(\d+\.?\d*)')[0], errors='coerce').mean())
                    .reset_index(name="Avg_Duration_Hrs")
                )
                avg_by_type["Avg_Duration_Min"] = avg_by_type["Avg_Duration_Hrs"] * 60
                avg_by_type = avg_by_type.sort_values("Avg_Duration_Min", ascending=False)
                overall_avg = avg_by_type["Avg_Duration_Min"].mean()

                fig_avg_worktype = px.bar(
                    avg_by_type,
                    x="Work Type",
                    y="Avg_Duration_Min",
                    text="Avg_Duration_Min",
                    color="Avg_Duration_Min",
                    color_continuous_scale="Viridis",
                    title="Overall Average Duration by Work Order Type (Minutes)",
                    template="plotly_dark"
                )
                fig_avg_worktype.add_hline(
                    y=overall_avg,
                    line_dash="dash",
                    line_color="cyan",
                    annotation_text=f"Overall Avg ({overall_avg:.0f} min)",
                    annotation_font_color="cyan"
                )
                fig_avg_worktype.update_traces(texttemplate='%{text:.0f} min', textposition='outside')
                fig_avg_worktype.update_layout(
                    xaxis_title="Work Order Type",
                    yaxis_title="Average Duration (Minutes)",
                    uniformtext_minsize=8,
                    uniformtext_mode='hide'
                )
                st.plotly_chart(fig_avg_worktype, use_container_width=True)

                                # --- Average Duration per Technician per Work Order Type (Minutes) ---
                st.markdown("""
                <div style='margin-top:25px; margin-bottom:10px; padding:10px 15px; border-radius:10px;
                            background:linear-gradient(90deg, #1c1c1c 0%, #8BC53F 100%);'>
                    <h4 style='color:white; margin:0;'>👨‍🔧 Average Duration per Technician per Work Order Type (Minutes)</h4>
                </div>
                """, unsafe_allow_html=True)

                # Convert duration column to numeric (already in minutes)
                df_filtered["Duration_Num"] = pd.to_numeric(
                    df_filtered["Duration"].str.extract(r"(\d+\.?\d*)")[0],
                    errors="coerce"
                )

                # Create pivot table
                pivot_table = (
                    df_filtered.pivot_table(
                        index="Technician",
                        columns="Work Type",
                        values="Duration_Num",
                        aggfunc="mean"
                    )
                    .round(1)
                    .fillna(0)
                )

                # Add overall average column (minutes)
                pivot_table["Overall Avg (min)"] = pivot_table.mean(axis=1)
                pivot_table = pivot_table.sort_values("Overall Avg (min)", ascending=False)

                # Format + style
                styled_pivot = (
                    pivot_table.style
                    .format("{:.1f}")
                    .background_gradient(cmap="viridis", axis=None)
                )

                st.dataframe(styled_pivot, use_container_width=True)

                # --- Divider ---
                st.markdown("""
                <hr style='border: 0; height: 3px; background-image: linear-gradient(to right, #004aad, #8BC53F, #004aad); margin:30px 0;'>
                """, unsafe_allow_html=True)

                # --- Charts ---
                grouped = (
                    df_filtered.groupby(["Technician", "Work Type"])
                    .agg(
                        Total_Jobs=("WO#", "nunique"),
                        Avg_Duration=("Duration", lambda x: pd.to_numeric(x.str.extract(r"(\d+\.?\d*)")[0], errors="coerce").mean())
                    )
                    .reset_index()
                )
                st.subheader("📊 Work Orders Charts")
                fig1 = px.bar(grouped, x="Work Type", y="Total_Jobs", color="Technician",
                              title="Jobs by Work Type & Technician", template="plotly_dark")
                st.plotly_chart(fig1, use_container_width=True)

                    # --- Average Duration per Technician per Work Type Table ---
                st.markdown("""
                <div style='margin-top:25px; margin-bottom:10px; padding:10px 15px; border-radius:10px;
                            background:linear-gradient(90deg, #1c1c1c 0%, #8BC53F 100%);'>
                    <h4 style='color:white; margin:0;'>👨‍🔧 Average Duration per Technician per Work Order Type (hrs)</h4>
                </div>
                """, unsafe_allow_html=True)

                # Create pivot of average duration (hrs)
                df_filtered["Duration_Num"] = pd.to_numeric(
                    df_filtered["Duration"].str.extract(r"(\d+\.?\d*)")[0],
                    errors="coerce"
                )

                pivot_table = (
                    df_filtered.pivot_table(
                        index="Technician",
                        columns="Work Type",
                        values="Duration_Num",
                        aggfunc="mean"
                    )
                    .round(2)
                    .fillna(0)
                )

                # Sort technicians by overall average duration
                pivot_table["Overall Avg (hrs)"] = pivot_table.mean(axis=1)
                pivot_table = pivot_table.sort_values("Overall Avg (hrs)", ascending=False)

                st.dataframe(
                    pivot_table.style.format("{:.2f}").background_gradient(
                        cmap="viridis", axis=None
                    ),
                    use_container_width=True
                )


    # =====================================================
    # 🔁 INSTALLATION REWORK SECTION
    # =====================================================
    if df_rework is not None and not df_rework.empty:
        with st.expander("🔁 Installation Rework Analysis", expanded=False):
            try:
                parsed_rows = []
                for _, row in df_rework.iterrows():
                    values = row.tolist()
                    if str(row[1]).startswith("Install"):
                        base_subset = [values[i] for i in [0, 2, 3, 4] if i < len(values)]
                    else:
                        base_subset = [values[i] for i in [0, 1, 2, 3] if i < len(values)]
                    while len(base_subset) < 4:
                        base_subset.append(None)
                    parsed_rows.append(base_subset)

                df_combined = pd.DataFrame(parsed_rows, columns=["Technician", "Total_Installations", "Rework", "Rework_Percentage"])
                df_combined["Technician"] = df_combined["Technician"].astype(str).str.replace('"', '').str.strip()
                df_combined["Total_Installations"] = pd.to_numeric(df_combined["Total_Installations"], errors="coerce")
                df_combined["Rework"] = pd.to_numeric(df_combined["Rework"], errors="coerce")
                df_combined["Rework_Percentage"] = pd.to_numeric(
                    df_combined["Rework_Percentage"].astype(str).str.replace("%", "").str.strip(), errors="coerce"
                )
                df_combined = df_combined.sort_values("Total_Installations", ascending=False)

                # --- Header ---
                st.markdown("""
                <div style='margin-top:10px; margin-bottom:10px; padding:10px 15px; border-radius:10px;
                            background:linear-gradient(90deg, #1c1c1c 0%, #8BC53F 100%);'>
                    <h3 style='color:white; margin:0;'>📊 Installation Rework KPIs</h3>
                </div>
                """, unsafe_allow_html=True)

                total_installs = df_combined["Total_Installations"].sum()
                total_repeats = df_combined["Rework"].sum()
                avg_repeat_pct = df_combined["Rework_Percentage"].mean()

                c1, c2, c3 = st.columns(3)
                c1.metric("🏗️ Total Installations", int(total_installs))
                c2.metric("🔁 Total Reworks", int(total_repeats))
                c3.metric("📈 Avg Rework %", f"{avg_repeat_pct:.1f}%")

                # --- Divider ---
                st.markdown("""
                <hr style='border: 0; height: 3px; background-image: linear-gradient(to right, #8BC53F, #004aad, #8BC53F); margin:30px 0;'>
                """, unsafe_allow_html=True)

                # --- Visualized Table ---
                st.markdown("### 🧾 Installation Rework Summary Table (Visualized)")
                def color_rework(val):
                    if pd.isna(val):
                        return ''
                    elif val < 5:
                        return 'background-color: #3CB371; color: white;'
                    elif val < 10:
                        return 'background-color: #FFD700; color: black;'
                    else:
                        return 'background-color: #FF6347; color: white;'

                styled_table = (
                    df_combined.style
                    .applymap(color_rework, subset=['Rework_Percentage'])
                    .format({
                        'Rework_Percentage': '{:.1f}%',
                        'Total_Installations': '{:.0f}',
                        'Rework': '{:.0f}'
                    })
                )
                st.dataframe(styled_table, use_container_width=True)

                # --- Combined Bar + Line Chart ---
                st.markdown("### 📊 Installations (Bars) vs Rework % (Line)")
                fig_combo = make_subplots(specs=[[{"secondary_y": True}]])
                fig_combo.add_trace(go.Bar(
                    x=df_combined["Technician"],
                    y=df_combined["Total_Installations"],
                    name="Total Installations",
                    marker_color="#00BFFF"
                ), secondary_y=False)
                fig_combo.add_trace(go.Scatter(
                    x=df_combined["Technician"],
                    y=df_combined["Rework_Percentage"],
                    name="Rework %",
                    mode="lines+markers",
                    line=dict(color="#FF6347", width=3)
                ), secondary_y=True)
                fig_combo.add_hline(
                    y=avg_repeat_pct,
                    line_dash="dash",
                    line_color="cyan",
                    annotation_text=f"Avg Rework % ({avg_repeat_pct:.1f}%)",
                    annotation_font_color="cyan",
                    secondary_y=True
                )
                fig_combo.update_layout(
                    title="Technician Total Installations vs Rework %",
                    template="plotly_dark",
                    xaxis_title="Technician",
                    yaxis_title="Total Installations",
                    bargap=0.25
                )
                fig_combo.update_yaxes(title_text="Total Installations", secondary_y=False)
                fig_combo.update_yaxes(title_text="Rework %", secondary_y=True)
                st.plotly_chart(fig_combo, use_container_width=True)

                # --- Download Button ---
                csv_rework = df_combined.to_csv(index=False).encode("utf-8")
                st.download_button(
                    "⬇️ Download Installation Rework Summary CSV",
                    data=csv_rework,
                    file_name="installation_rework_summary.csv",
                    mime="text/csv"
                )

            except Exception as e:
                st.error(f"Error parsing installation rework file: {e}")
