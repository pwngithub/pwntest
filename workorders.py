import streamlit as st
import pandas as pd
import plotly.express as px
import os
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import requests
import base64

# =================================================
# GITHUB HELPERS FOR WORK ORDERS
# =================================================

def get_github_config_workorders():
    """Load GitHub secrets and force folder to workorders/."""
    try:
        gh_cfg = st.secrets["github"]
        token = gh_cfg["token"]
        repo = gh_cfg["repo"]
        branch = gh_cfg.get("branch", "main")
        remote_prefix = "workorders/"
        return token, repo, branch, remote_prefix
    except Exception:
        st.warning("GitHub secrets not configured correctly under [github].")
        return None, None, None, None


def list_github_workorders():
    """Return a list of CSV files inside GitHub/workorders/."""
    token, repo, branch, remote_prefix = get_github_config_workorders()
    if not token or not repo:
        return []

    api_url = f"https://api.github.com/repos/{repo}/contents/{remote_prefix}"
    headers = {"Authorization": f"token {token}"}

    resp = requests.get(api_url, headers=headers)
    if resp.status_code != 200:
        return []

    files = resp.json()
    return [f["name"] for f in files if f["type"] == "file" and f["name"].endswith(".csv")]


def download_github_workorder_file(filename):
    """Download a file from GitHub/workorders/ and save to local cache."""
    token, repo, branch, remote_prefix = get_github_config_workorders()
    if not token or not repo:
        return None

    api_url = f"https://api.github.com/repos/{repo}/contents/{remote_prefix}{filename}"
    headers = {"Authorization": f"token {token}"}

    resp = requests.get(api_url, headers=headers)
    if resp.status_code != 200:
        return None

    file_bytes = base64.b64decode(resp.json()["content"])

    # Save to local cache
    local_folder = "saved_uploads"
    os.makedirs(local_folder, exist_ok=True)
    local_path = os.path.join(local_folder, filename)

    with open(local_path, "wb") as f:
        f.write(file_bytes)

    return local_path


def upload_workorders_file_to_github(filename: str, file_bytes: bytes):
    """Upload or update a CSV file into GitHub/workorders/."""
    token, repo, branch, remote_prefix = get_github_config_workorders()
    if not token or not repo:
        return

    remote_path = remote_prefix.rstrip("/") + "/" + filename
    api_url = f"https://api.github.com/repos/{repo}/contents/{remote_path}"
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github+json"
    }

    # Get SHA if file exists
    sha = None
    get_resp = requests.get(api_url, headers=headers)
    if get_resp.status_code == 200:
        sha = get_resp.json().get("sha")

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


# =================================================
# MAIN DASHBOARD
# =================================================

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

    saved_folder = "saved_uploads"
    os.makedirs(saved_folder, exist_ok=True)

    # =================================================
    # WORK ORDERS MANAGEMENT
    # =================================================
    st.sidebar.header("📁 Work Orders File")

    mode = st.sidebar.radio(
        "Select Mode",
        ["Upload New Work Orders File", "Load Existing Work Orders File"],
        key="wo_mode"
    )
    df = None

    # -------------------------
    # UPLOAD NEW FILE
    # -------------------------
    if mode == "Upload New Work Orders File":
        uploaded_file = st.sidebar.file_uploader(
            "Upload Work Orders CSV", type=["csv"], key="wo_upload"
        )
        custom_filename = st.sidebar.text_input(
            "Enter filename to save (no extension):",
            key="wo_filename"
        )

        if uploaded_file and custom_filename:
            file_bytes = uploaded_file.getvalue()
            filename = custom_filename + ".csv"

            # Save to local cache
            local_path = os.path.join(saved_folder, filename)
            with open(local_path, "wb") as f:
                f.write(file_bytes)

            st.sidebar.success(f"Saved locally: {filename}")

            # Upload to GitHub
            try:
                upload_workorders_file_to_github(filename, file_bytes)
            except Exception as e:
                st.sidebar.error(f"GitHub upload failed: {e}")

            df = pd.read_csv(local_path)

        elif uploaded_file:
            st.sidebar.warning("Please enter a filename.")

    # -------------------------
    # LOAD EXISTING FROM GITHUB
    # -------------------------
    else:
        github_files = list_github_workorders()

        if not github_files:
            st.error("No work order files found in GitHub/workorders/.")
            st.stop()

        selected_file = st.sidebar.selectbox(
            "Select Work Orders File (GitHub)",
            github_files,
            key="wo_select_github"
        )

        if selected_file:
            local_path = download_github_workorder_file(selected_file)
            if not local_path:
                st.error("Failed to download file from GitHub.")
                st.stop()

            df = pd.read_csv(local_path)

    if df is None:
        st.info("Upload or load a Work Orders file to continue.")
        st.stop()

    # =================================================
    # DATA CLEANING + FILTERS
    # =================================================

    date_cols = [
        col for col in df.columns
        if str(col).lower() in ["date when", "date", "work date", "completed", "completion date"]
    ]
    if not date_cols:
        st.error("No date column found in CSV.")
        st.stop()

    date_col = date_cols[0]
    df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
    df = df.dropna(subset=[date_col])
    df["Day"] = df[date_col].dt.date

    if "Techinician" in df.columns:
        df.rename(columns={"Techinician": "Technician"}, inplace=True)

    min_day, max_day = df["Day"].min(), df["Day"].max()

    st.subheader("F I L T E R S")
    start_date, end_date = st.date_input(
        "📅 Date Range", [min_day, max_day],
        min_value=min_day, max_value=max_day
    )
    df_filtered = df[(df["Day"] >= start_date) & (df["Day"] <= end_date)]

    if df_filtered.empty:
        st.warning("No data available for selected date range.")
        st.stop()

    # Filter by tech + work type
    if "Technician" in df_filtered.columns and "Work Type" in df_filtered.columns:
        techs = sorted(df_filtered["Technician"].unique())
        wtypes = sorted(df_filtered["Work Type"].unique())

        col1, col2 = st.columns(2)
        with col1:
            selected_techs = st.multiselect("👨‍🔧 Technician(s)", techs, default=techs)
        with col2:
            selected_wtypes = st.multiselect("📋 Work Type(s)", wtypes, default=wtypes)

        df_filtered = df_filtered[
            df_filtered["Technician"].isin(selected_techs)
            & df_filtered["Work Type"].isin(selected_wtypes)
        ]

    if df_filtered.empty:
        st.warning("No data for selected filters.")
        st.stop()

    # =================================================
    # REQUIRED COLUMNS
    # =================================================
    required_cols = ['WO#', 'Duration', 'Technician', 'Work Type']
    missing = [c for c in required_cols if c not in df_filtered.columns]
    if missing:
        st.error(f"Missing columns: {', '.join(missing)}")
        st.stop()

    # =================================================
    # KPIs
    # =================================================
    st.markdown("### 📌 Work Orders KPIs")
    df_kpi = df_filtered.dropna(subset=['Duration'])

    if not df_kpi.empty:
        total_jobs = df_kpi["WO#"].nunique()
        tech_count = df_kpi["Technician"].nunique()
        avg_jobs = total_jobs / tech_count if tech_count else 0

        k1, k2, k3 = st.columns(3)
        k1.metric("🔧 Total Jobs", total_jobs)
        k2.metric("👨‍🔧 Tech Count", tech_count)
        k3.metric("📈 Avg Jobs per Tech", f"{avg_jobs:.1f}")
    else:
        st.warning("No duration data found.")

    # =================================================
    # OVERALL AVG DURATION
    # =================================================
    st.markdown("### 📊 Overall Average Duration by Work Type")

    df_avg = df_filtered.dropna(subset=['Duration'])

    if not df_avg.empty:
        df_avg["Duration_Mins"] = pd.to_numeric(
            df_avg["Duration"].astype(str).str.extract(r"(\d+\.?\d*)")[0],
            errors="coerce"
        )

        tech_group = df_avg.groupby(['Work Type', 'Technician'])['Duration_Mins'].mean().reset_index()
        final_avg = tech_group.groupby('Work Type')['Duration_Mins'].mean().reset_index()
        final_avg.rename(columns={'Duration_Mins': 'Avg Duration (mins)'}, inplace=True)

        fig = px.bar(
            final_avg, x="Work Type", y="Avg Duration (mins)",
            title="Overall Average Job Time by Work Type",
            template="plotly_dark"
        )
        fig.update_traces(marker_color="#8BC53F")
        st.plotly_chart(fig, use_container_width=True)

    # =================================================
    # CHARTS
    # =================================================
    st.markdown("### 📊 Work Orders Charts by Technician")

    if not df_avg.empty:
        grouped = (
            df_avg.groupby(["Technician", "Work Type"])
            .agg(
                Total_Jobs=("WO#", "nunique"),
                Avg_Duration=("Duration_Mins", "mean")
            )
            .reset_index()
        )

        fig1 = px.bar(
            grouped,
            x="Work Type", y="Total_Jobs", color="Technician",
            title="Jobs by Work Type & Technician",
            template="plotly_dark"
        )
        st.plotly_chart(fig1, use_container_width=True)

        fig2 = px.bar(
            grouped,
            x="Work Type", y="Avg_Duration", color="Technician",
            title="Avg Duration by Work Type & Technician (mins)",
            template="plotly_dark"
        )
        st.plotly_chart(fig2, use_container_width=True)

    st.markdown("---")

    # =================================================
    # INSTALLATION REWORK ANALYSIS
    # =================================================
    st.markdown("<h2 style='color:#8BC53F;'>🔁 Installation Rework Analysis</h2>", unsafe_allow_html=True)

    re_mode = st.sidebar.radio(
        "Installation Rework File",
        ["Upload New File", "Load Existing File"],
        key="re_mode"
    )
    df_rework = None

    # -------------------------
    # UPLOAD NEW REWORK FILE
    # -------------------------
    if re_mode == "Upload New File":
        re_file = st.sidebar.file_uploader(
            "Upload Installation Assessment File", type=["csv", "txt"],
            key="re_upload"
        )
        re_filename = st.sidebar.text_input(
            "Enter name to save (no extension):",
            key="re_filename"
        )

        if re_file and re_filename:
            bytes_re = re_file.getvalue()
            filename = re_filename + ".csv"

            # Save to local
            local_path = os.path.join(saved_folder, filename)
            with open(local_path, "wb") as f:
                f.write(bytes_re)

            # Upload to GitHub/workorders/
            try:
                upload_workorders_file_to_github(filename, bytes_re)
            except Exception as e:
                st.sidebar.error(f"Rework file upload error: {e}")

            df_rework = pd.read_csv(local_path, header=None)

    # -------------------------
    # LOAD EXISTING (GITHUB ONLY)
    # -------------------------
    else:
        github_files = list_github_workorders()

        if not github_files:
            st.warning("No rework files found in GitHub/workorders/")
        else:
            selected = st.sidebar.selectbox(
                "Select Installation Rework File (GitHub)",
                github_files,
                key="re_select_github"
            )
            if selected:
                local = download_github_workorder_file(selected)
                df_rework = pd.read_csv(local, header=None)

    # =================================================
    # PARSE REWORK FILE
    # =================================================
    if df_rework is not None and not df_rework.empty:
        try:
            parsed_rows = []
            for _, row in df_rework.iterrows():
                values = row.tolist()
                if len(values) > 1 and str(values[1]).startswith("Install"):
                    base = [values[i] for i in [0, 2, 3, 4] if i < len(values)]
                else:
                    base = [values[i] for i in [0, 1, 2, 3] if i < len(values)]
                while len(base) < 4:
                    base.append(None)
                parsed_rows.append(base)

            df_combined = pd.DataFrame(
                parsed_rows,
                columns=["Technician", "Total_Installations", "Rework", "Rework_Percentage"]
            )

            # Cleanup
            df_combined["Technician"] = df_combined["Technician"].astype(str).str.replace('"', '').str.strip()
            df_combined["Total_Installations"] = pd.to_numeric(df_combined["Total_Installations"], errors="coerce")
            df_combined["Rework"] = pd.to_numeric(df_combined["Rework"], errors="coerce")
            df_combined["Rework_Percentage"] = (
                df_combined["Rework_Percentage"].astype(str)
                .str.replace("%", "").str.replace('"', "").str.strip()
            )
            df_combined["Rework_Percentage"] = pd.to_numeric(df_combined["Rework_Percentage"], errors="coerce")
            df_combined.dropna(subset=["Technician", "Total_Installations"], inplace=True)

            df_combined = df_combined.sort_values("Total_Installations", ascending=False)

            # KPIs
            st.markdown("### 📌 Installation Rework KPIs")
            total_inst = df_combined["Total_Installations"].sum()
            total_re = df_combined["Rework"].sum()
            avg_pct = df_combined["Rework_Percentage"].mean()

            c1, c2, c3 = st.columns(3)
            c1.metric("🏗️ Total Installations", int(total_inst))
            c2.metric("🔁 Total Reworks", int(total_re))
            c3.metric("📈 Avg Rework %", f"{avg_pct:.1f}%")

            # Table
            def color_rework(val):
                if pd.isna(val):
                    return ""
                elif val < 5:
                    return "background-color:#3CB371;color:white;"
                elif val < 10:
                    return "background-color:#FFD700;color:black;"
                else:
                    return "background-color:#FF6347;color:white;"

            styled = (
                df_combined.style
                .map(color_rework, subset=['Rework_Percentage'])
                .format({
                    'Rework_Percentage': '{:.1f}%',
                    'Total_Installations': '{:.0f}',
                    'Rework': '{:.0f}'
                })
            )
            st.dataframe(styled)

            # Chart
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
                y=avg_pct, line_dash="dash", line_color="cyan",
                annotation_text=f"Avg Rework % ({avg_pct:.1f}%)",
                annotation_font_color="cyan",
                secondary_y=True
            )
            fig_combo.update_layout(
                title_text="Technician Total Installations vs Rework %",
                template="plotly_dark",
                xaxis_title="Technician",
                bargap=0.25
            )
            st.plotly_chart(fig_combo, use_container_width=True)

            # Download button
            csv_rework = df_combined.to_csv(index=False).encode("utf-8")
            st.download_button(
                "⬇️ Download Installation Rework Summary CSV",
                data=csv_rework,
                file_name="installation_rework_summary.csv",
                mime="text/csv",
                key="download_summary"
            )

        except Exception as e:
            st.error(f"Error parsing installation rework file: {e}")


# RUN APP
if __name__ == "__main__":
    run_workorders_dashboard()
