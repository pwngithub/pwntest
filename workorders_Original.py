
import streamlit as st
import pandas as pd
import plotly.express as px
import os
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import requests  # <-- for GitHub upload

# =================================================
# GITHUB HELPERS FOR WORK ORDERS
# =================================================
def get_github_config_workorders():
    """
    Read GitHub config from st.secrets["github"] but
    ALWAYS push into the 'workorders/' folder in the repo,
    so we don't interfere with fiber.py using 'fiber/'.
    """
    try:
        gh_cfg = st.secrets["github"]
        token = gh_cfg["token"]
        repo = gh_cfg["repo"]
        branch = gh_cfg.get("branch", "main")
        # Force remote folder to 'workorders/' for this app
        remote_prefix = "workorders/"
        return token, repo, branch, remote_prefix
    except Exception:
        st.warning("GitHub secrets not configured correctly under [github].")
        return None, None, None, None


def upload_workorders_file_to_github(filename: str, file_bytes: bytes):
    """
    Upload or update a workorders CSV file in the 'workorders/' directory
    of the configured GitHub repo.
    """
    token, repo, branch, remote_prefix = get_github_config_workorders()
    if not token or not repo:
        return  # No GitHub config, silently skip

    remote_path = remote_prefix.rstrip("/") + "/" + filename
    api_url = f"https://api.github.com/repos/{repo}/contents/{remote_path}"
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github+json"
    }

    # Check if file already exists to get its SHA
    sha = None
    get_resp = requests.get(api_url, headers=headers)
    if get_resp.status_code == 200:
        try:
            sha = get_resp.json().get("sha")
        except Exception:
            sha = None

    import base64
    content_b64 = base64.b64encode(file_bytes).decode("utf-8")

    payload = {
        "message": f"Add/update {filename} via Work Orders Dashboard",
        "content": content_b64,
        "branch": branch,
    }
    if sha:
        payload["sha"] = sha

    put_resp = requests.put(api_url, headers=headers, json=payload)
    if put_resp.status_code in (200, 201):
        st.sidebar.success(f"Pushed to GitHub: {repo}/{remote_path}")
    else:
        st.sidebar.error(
            f"GitHub upload failed ({put_resp.status_code}): {put_resp.text}"
        )


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
    # SECTION 1: WORK ORDERS FILE MANAGEMENT
    # =================================================
    st.sidebar.header("📁 Work Orders File")
    saved_folder = "saved_uploads"
    os.makedirs(saved_folder, exist_ok=True)

    mode = st.sidebar.radio(
        "Select Mode",
        ["Upload New Work Orders File", "Load Existing Work Orders File"],
        key="wo_mode"
    )
    df = None

    if mode == "Upload New Work Orders File":
        uploaded_file = st.sidebar.file_uploader("Upload Work Orders CSV", type=["csv"])
        custom_filename = st.sidebar.text_input(
            "Enter filename to save (no extension):",
            key="wo_filename"
        )

        if uploaded_file and custom_filename:
            # Save locally
            save_path = os.path.join(saved_folder, custom_filename + ".csv")
            file_bytes = uploaded_file.getvalue()
            with open(save_path, "wb") as f:
                f.write(file_bytes)
            st.sidebar.success(f"File saved as: {custom_filename}.csv")

            # Upload to GitHub in workorders/ folder
            try:
                upload_workorders_file_to_github(custom_filename + ".csv", file_bytes)
            except Exception as e:
                st.sidebar.error(f"GitHub upload error: {e}")

            # Load into DataFrame
            df = pd.read_csv(save_path)

        elif uploaded_file:
            st.sidebar.warning("Please enter a file name to save.")
    else:
        saved_files = [f for f in os.listdir(saved_folder) if f.endswith(".csv")]
        if not saved_files:
            st.warning("No saved files found. Please upload one first.")
            st.stop()
        selected_file = st.sidebar.selectbox("Select a saved file", saved_files, key="wo_select")
        if selected_file:
            df = pd.read_csv(os.path.join(saved_folder, selected_file))
        if st.sidebar.button("🗑 Delete Selected Work Orders File"):
            os.remove(os.path.join(saved_folder, selected_file))
            st.sidebar.success(f"Deleted {selected_file}")
            st.rerun()

    if df is None:
        st.info("Please upload or load a Work Orders file to begin.")
        st.stop()

    # --- Data Cleaning and Preparation ---
    date_cols = [
        col for col in df.columns
        if str(col).lower() in ["date when", "date", "work date", "completed", "completion date"]
    ]
    if not date_cols:
        st.error("No date column found. Please include a 'Date When', 'Date', or 'Completed' column in your CSV.")
        st.stop()

    date_col = date_cols[0]
    df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
    df = df.dropna(subset=[date_col])
    df["Day"] = df[date_col].dt.date

    if "Techinician" in df.columns and "Technician" not in df.columns:
        df.rename(columns={"Techinician": "Technician"}, inplace=True)

    min_day, max_day = df["Day"].min(), df["Day"].max()

    # --- Filters ---
    st.subheader("F I L T E R S")
    start_date, end_date = st.date_input(
        "📅 Date Range",
        [min_day, max_day],
        min_value=min_day,
        max_value=max_day
    )
    df_filtered = df[(df["Day"] >= start_date) & (df["Day"] <= end_date)]

    if not df_filtered.empty:
        if 'Work Type' in df_filtered.columns and 'Technician' in df_filtered.columns:
            techs = sorted(df_filtered["Technician"].unique())
            work_types = sorted(df_filtered["Work Type"].unique())
            col1, col2 = st.columns(2)
            with col1:
                selected_techs = st.multiselect("👨‍🔧 Select Technician(s)", techs, default=techs)
            with col2:
                selected_work_types = st.multiselect("📋 Select Work Type(s)", work_types, default=work_types)
            df_filtered = df_filtered[
                df_filtered["Technician"].isin(selected_techs)
                & df_filtered["Work Type"].isin(selected_work_types)
            ]
        else:
            st.warning("Missing 'Technician' or 'Work Type' columns for filtering.")

    if df_filtered.empty:
        st.warning("No data available for the selected filters.")
        st.stop()

    # =====================================================
    # ROBUST COLUMN CHECK
    # =====================================================
    required_cols = ['WO#', 'Duration', 'Technician', 'Work Type']
    missing_cols = [col for col in required_cols if col not in df_filtered.columns]
    if missing_cols:
        st.error(f"❌ **Error:** Your CSV file is missing required columns: **{', '.join(missing_cols)}**")
        st.stop()

    # =====================================================
    # SECTION 2: KPIs
    # =====================================================
    st.markdown("### 📌 Work Orders KPIs")
    
    df_kpi = df_filtered.dropna(subset=['Duration'])

    if df_kpi.empty:
        st.warning("No work orders with duration data found in the selected date range.")
    else:
        try:
            total_jobs = df_kpi["WO#"].nunique()
            tech_count = df_kpi["Technician"].nunique()
            avg_jobs_per_tech = total_jobs / tech_count if tech_count else 0

            # --- KPI Display ---
            k1, k2, k3 = st.columns(3)
            k1.metric("🔧 Total Jobs (with duration)", total_jobs)
            k2.metric("👨‍🔧 Technicians", tech_count)
            k3.metric("📈 Avg Jobs per Tech", f"{avg_jobs_per_tech:.1f}")
            
        except Exception as e:
            st.error(f"An error occurred while calculating main KPIs: {e}")

    # =====================================================
    # MODIFIED SECTION: Bar chart for Overall Average by Work Type
    # =====================================================
    st.markdown("### 📊 Overall Average Duration by Work Type")
    df_avg_calc = df_filtered.dropna(subset=['Duration'])

    if df_avg_calc.empty:
        st.warning("No data with duration to calculate work type averages.")
    else:
        try:
            df_avg_calc['Duration_Mins'] = pd.to_numeric(
                df_avg_calc['Duration'].astype(str).str.extract(r"(\d+\.?\d*)")[0],
                errors='coerce'
            )
            tech_work_type_avg = df_avg_calc.groupby(['Work Type', 'Technician'])['Duration_Mins'].mean().reset_index()

            final_work_type_avg = tech_work_type_avg.groupby('Work Type')['Duration_Mins'].mean().reset_index()
            final_work_type_avg.rename(
                columns={'Duration_Mins': 'Overall Average Duration (mins)'},
                inplace=True
            )
            
            # Create a new bar chart for the overall average
            fig_overall_avg = px.bar(
                final_work_type_avg,
                x='Work Type',
                y='Overall Average Duration (mins)',
                title="Overall Average Job Time by Work Type",
                template="plotly_dark",
                labels={'Overall Average Duration (mins)': 'Avg Duration (mins)'}
            )
            fig_overall_avg.update_traces(marker_color='#8BC53F')  # Use a distinct color
            st.plotly_chart(fig_overall_avg, use_container_width=True)

        except Exception as e:
            st.error(f"Could not create Overall Average by Work Type chart: {e}")

    # =====================================================
    # SECTION 3: CHARTS
    # =====================================================
    st.markdown("### 📊 Work Orders Charts by Technician")
    df_charts = df_filtered.dropna(subset=['Duration']) 

    if df_charts.empty:
        st.warning("No work orders with duration data found to create charts.")
    else:
        try:
            grouped_overall = (
                df_charts.groupby(["Technician", "Work Type"])
                .agg(
                    Total_Jobs=("WO#", "nunique"),
                    Average_Duration_Mins=(
                        "Duration",
                        lambda x: pd.to_numeric(
                            x.astype(str).str.extract(r"(\d+\.?\d*)")[0], errors='coerce'
                        ).mean()
                    )
                )
                .reset_index()
            )

            fig1 = px.bar(
                grouped_overall,
                x="Work Type",
                y="Total_Jobs",
                color="Technician",
                title="Jobs by Work Type & Technician",
                template="plotly_dark"
            )
            st.plotly_chart(fig1, use_container_width=True)

            fig2 = px.bar(
                grouped_overall,
                x="Work Type",
                y="Average_Duration_Mins",
                color="Technician",
                title="Avg Duration by Work Type & Technician (mins)",
                template="plotly_dark",
                labels={'Average_Duration_Mins': 'Avg Duration (mins)'}
            )
            st.plotly_chart(fig2, use_container_width=True)
        except Exception as e:
            st.error(f"An error occurred while creating charts: {e}")

    st.markdown("---")
    
    # =====================================================
    # SECTION 4: INSTALLATION REWORK ANALYSIS
    # =====================================================
    st.markdown("<h2 style='color:#8BC53F;'>🔁 Installation Rework Analysis</h2>", unsafe_allow_html=True)
    re_mode = st.sidebar.radio(
        "Select Mode for Installation Rework File",
        ["Upload New File", "Load Existing File"],
        key="re_mode"
    )
    df_rework = None

    if re_mode == "Upload New File":
        re_file = st.sidebar.file_uploader(
            "Upload Installation Assessment File (CSV or TXT)",
            type=["csv", "txt"]
        )
        re_filename = st.sidebar.text_input(
            "Enter name to save (no extension):",
            key="re_filename"
        )

        if re_file and re_filename:
            save_path = os.path.join(saved_folder, re_filename + ".csv")
            file_bytes_re = re_file.getvalue()
            with open(save_path, "wb") as f:
                f.write(file_bytes_re)
            st.sidebar.success(f"File saved as: {re_filename}.csv")

            # NEW: upload rework file to GitHub workorders/ folder
            try:
                upload_workorders_file_to_github(re_filename + ".csv", file_bytes_re)
            except Exception as e:
                st.sidebar.error(f"GitHub upload error (rework file): {e}")

            df_rework = pd.read_csv(save_path, header=None)
        elif re_file:
            st.sidebar.warning("Please enter a file name to save.")
    else:
        saved_files = [f for f in os.listdir(saved_folder) if f.endswith(".csv")]
        if saved_files:
            selected_re_file = st.sidebar.selectbox(
                "Select saved file",
                saved_files,
                key="re_select"
            )
            if selected_re_file:
                df_rework = pd.read_csv(
                    os.path.join(saved_folder, selected_re_file),
                    header=None
                )
        else:
            st.sidebar.warning("No saved files found for Installation Rework.")

    if df_rework is not None and not df_rework.empty:
        try:
            parsed_rows = []
            for _, row in df_rework.iterrows():
                values = row.tolist()
                if len(values) > 1 and str(values[1]).startswith("Install"):
                    base_subset = [values[i] for i in [0, 2, 3, 4] if i < len(values)]
                else:
                    base_subset = [values[i] for i in [0, 1, 2, 3] if i < len(values)]
                while len(base_subset) < 4:
                    base_subset.append(None)
                parsed_rows.append(base_subset)

            df_combined = pd.DataFrame(
                parsed_rows,
                columns=["Technician", "Total_Installations", "Rework", "Rework_Percentage"]
            )
            df_combined["Technician"] = (
                df_combined["Technician"].astype(str).str.replace('"', '').str.strip()
            )
            df_combined["Total_Installations"] = pd.to_numeric(
                df_combined["Total_Installations"], errors="coerce"
            )
            df_combined["Rework"] = pd.to_numeric(
                df_combined["Rework"], errors="coerce"
            )
            df_combined["Rework_Percentage"] = (
                df_combined["Rework_Percentage"]
                .astype(str)
                .str.replace("%", "")
                .str.replace('"', "")
                .str.strip()
            )
            df_combined["Rework_Percentage"] = pd.to_numeric(
                df_combined["Rework_Percentage"], errors="coerce"
            )
            df_combined.dropna(
                subset=["Technician", "Total_Installations"],
                inplace=True
            )
            df_combined = df_combined.sort_values(
                "Total_Installations",
                ascending=False
            )

            st.markdown("### 📌 Installation Rework KPIs")
            total_jobs_rw = df_combined["Total_Installations"].sum()
            total_repeats = df_combined["Rework"].sum()
            avg_repeat_pct = df_combined["Rework_Percentage"].mean()

            c1, c2, c3 = st.columns(3)
            c1.metric("🏗️ Total Installations", int(total_jobs_rw))
            c2.metric("🔁 Total Reworks", int(total_repeats))
            c3.metric("📈 Avg Rework %", f"{avg_repeat_pct:.1f}%")

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
                .map(color_rework, subset=['Rework_Percentage'])
                .format({
                    'Rework_Percentage': '{:.1f}%',
                    'Total_Installations': '{:.0f}',
                    'Rework': '{:.0f}'
                })
            )
            st.dataframe(styled_table)

            st.markdown("### 📊 Installations (Bars) vs Rework % (Line)")
            fig_combo = make_subplots(specs=[[{"secondary_y": True}]])
            fig_combo.add_trace(
                go.Bar(
                    x=df_combined["Technician"],
                    y=df_combined["Total_Installations"],
                    name="Total Installations",
                    marker_color="#00BFFF"
                ),
                secondary_y=False
            )
            fig_combo.add_trace(
                go.Scatter(
                    x=df_combined["Technician"],
                    y=df_combined["Rework_Percentage"],
                    name="Rework %",
                    mode="lines+markers",
                    line=dict(color="#FF6347", width=3)
                ),
                secondary_y=True
            )
            fig_combo.add_hline(
                y=avg_repeat_pct,
                line_dash="dash",
                line_color="cyan",
                annotation_text=f"Avg Rework % ({avg_repeat_pct:.1f}%)",
                annotation_font_color="cyan",
                secondary_y=True
            )
            fig_combo.update_layout(
                title_text="Technician Total Installations vs Rework %",
                template="plotly_dark",
                xaxis_title="Technician",
                yaxis_title="Total Installations",
                legend=dict(x=0.01, y=0.99, bgcolor="rgba(0,0,0,0)"),
                bargap=0.25
            )
            fig_combo.update_yaxes(title_text="Total Installations", secondary_y=False)
            fig_combo.update_yaxes(title_text="Rework %", secondary_y=True)
            st.plotly_chart(fig_combo, use_container_width=True)

            csv_rework = df_combined.to_csv(index=False).encode("utf-8")
            st.download_button(
                "⬇️ Download Installation Rework Summary CSV",
                data=csv_rework,
                file_name="installation_rework_summary.csv",
                mime="text/csv"
            )

        except Exception as e:
            st.error(f"Error parsing installation rework file: {e}")


if __name__ == "__main__":
    run_workorders_dashboard()
