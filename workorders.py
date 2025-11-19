import streamlit as st
import pandas as pd
import plotly.express as px
import os
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import requests
import base64
from datetime import datetime

# =================================================
# GITHUB HELPERS FOR WORK ORDERS
# =================================================

def get_github_config_workorders():
    """
    Load GitHub secrets and force the folder to workorders/.
    """
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
    """
    Download a file from GitHub/workorders/.
    Handles both base64 content and raw download_url for large files.
    Saves the file to saved_uploads/ and returns the local path.
    """
    token, repo, branch, remote_prefix = get_github_config_workorders()
    if not token or not repo:
        return None

    api_url = f"https://api.github.com/repos/{repo}/contents/{remote_prefix}{filename}"
    headers = {"Authorization": f"token {token}"}

    resp = requests.get(api_url, headers=headers)
    if resp.status_code != 200:
        return None

    j = resp.json()

    # Use download_url if available
    if j.get("download_url"):
        raw = requests.get(j["download_url"])
        file_bytes = raw.content
    else:
        file_bytes = base64.b64decode(j["content"])

    # Save local copy (cache)
    local_folder = "saved_uploads"
    os.makedirs(local_folder, exist_ok=True)
    local_path = os.path.join(local_folder, filename)

    with open(local_path, "wb") as f:
        f.write(file_bytes)

    return local_path


def upload_workorders_file_to_github(filename: str, file_bytes: bytes):
    """
    Upload or update a CSV file into GitHub/workorders/.
    """
    token, repo, branch, remote_prefix = get_github_config_workorders()
    if not token or not repo:
        return

    remote_path = remote_prefix.rstrip("/") + "/" + filename
    api_url = f"https://api.github.com/repos/{repo}/contents/{remote_path}"
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github+json"
    }

    sha = None
    get_resp = requests.get(api_url, headers=headers)
    if get_resp.status_code == 200:
        sha = get_resp.json().get("sha")

    content_b64 = base64.b64encode(file_bytes).decode("utf-8")

    payload = {
        "message": f"Add/update {filename}",
        "content": content_b64,
        "branch": branch,
    }
    if sha:
        payload["sha"] = sha

    put_resp = requests.put(api_url, headers=headers, json=payload)
    if put_resp.status_code in (200, 201):
        st.sidebar.success(f"Pushed to GitHub: {repo}/{remote_path}")
    else:
        st.sidebar.error(f"GitHub upload failed: {put_resp.status_code} - {put_resp.text}")



# =================================================
# MAIN DASHBOARD
# =================================================

def run_workorders_dashboard():
    st.set_page_config(page_title="PBB Work Orders Dashboard", layout="wide")

    # ------------------ Styling ------------------
    st.markdown("""
    <style>
    .stApp {background-color: #0E1117;}
    div[data-testid="metric-container"] {
        background-color: #262730;
        border: 1px solid #3c3c3c;
        padding: 15px;
        border-radius: 10px;
        color: #FAFAFA;
    }
    div[data-testid="metric-container"]:hover {
        transform: scale(1.05);
        border-color: #8BC53F;
    }
    </style>
    """, unsafe_allow_html=True)

    # ------------------ Title ------------------
    st.image(
        "https://images.squarespace-cdn.com/content/v1/651eb4433b13e72c1034f375/"
        "369c5df0-5363-4827-b041-1add0367f447/PBB+long+logo.png?format=1500w",
        width=350
    )
    st.markdown("<h1 style='text-align:center;color:white;'>🛠 Pioneer Broadband Work Orders Dashboard</h1>",
                unsafe_allow_html=True)
    st.markdown("---")

    saved_folder = "saved_uploads"
    os.makedirs(saved_folder, exist_ok=True)

    # =========================================================
    # WORK ORDERS FILE SELECT
    # =========================================================
    st.sidebar.header("📁 Work Orders File")

    mode = st.sidebar.radio(
        "Select Mode",
        ["Upload New Work Orders File", "Load Existing Work Orders File"],
        key="wo_mode"
    )

    df = None

    # Upload new file
    if mode == "Upload New Work Orders File":
        uploaded_file = st.sidebar.file_uploader("Upload Work Orders CSV", type=["csv"], key="wo_upload")
        custom_filename = st.sidebar.text_input("Enter filename (no extension):", key="wo_filename")

        if uploaded_file and custom_filename:
            filename = custom_filename + ".csv"
            file_bytes = uploaded_file.getvalue()

            # Save to local
            local_path = os.path.join(saved_folder, filename)
            with open(local_path, "wb") as f:
                f.write(file_bytes)

            # Upload to GitHub
            upload_workorders_file_to_github(filename, file_bytes)

            df = pd.read_csv(local_path)

    # Load from GitHub
    else:
        github_files = list_github_workorders()

        if not github_files:
            st.error("No Work Orders files found in GitHub/workorders/")
            st.stop()

        selected_file = st.sidebar.selectbox("Select Work Orders File", github_files, key="wo_select")
        local_path = download_github_workorder_file(selected_file)
        df = pd.read_csv(local_path)

    if df is None:
        st.info("Upload or load a Work Orders file to continue.")
        st.stop()

    # =========================================================
    # DATA CLEANING
    # =========================================================

    # Fix Technician label if misspelled
    if "Techinician" in df.columns:
        df.rename(columns={"Techinician": "Technician"}, inplace=True)

    # Identify date column
    date_cols = [
        col for col in df.columns
        if col.lower() in ["date when", "date", "current date", "work date", "completed"]
    ]
    if not date_cols:
        st.error("No date-related column was found.")
        st.stop()

    date_col = date_cols[0]
    df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
    df.dropna(subset=[date_col], inplace=True)
    df["Day"] = df[date_col].dt.date

    min_day, max_day = df["Day"].min(), df["Day"].max()

    # FILTERS
    st.subheader("F I L T E R S")
    start_date, end_date = st.date_input(
        "📅 Date Range", [min_day, max_day], min_value=min_day, max_value=max_day
    )

    df_filtered = df[(df["Day"] >= start_date) & (df["Day"] <= end_date)]

    if df_filtered.empty:
        st.warning("No Work Orders in selected range.")
        st.stop()

    # Technician filter
    if "Technician" in df_filtered.columns:
        techs = sorted(df_filtered["Technician"].dropna().unique())
        selected_techs = st.multiselect("👨‍🔧 Select Technician(s)", techs, default=techs)

        df_filtered = df_filtered[df_filtered["Technician"].isin(selected_techs)]

    if df_filtered.empty:
        st.warning("No data after filters.")
        st.stop()

    # Ensure required columns exist
    required_cols = ["WO#", "Technician", "Work Type", "Duration", "Current Date", "Date When", "Tech Status"]
    missing_cols = [c for c in required_cols if c not in df.columns]
    # (DON'T STOP FOR NOW — Some CSVs may not have all of these)

    # =========================================================
    # NEW: TRAVEL TIME CALCULATION (Enroute → Arrived)
    # =========================================================

    def extract_travel_times(df):
        """
        Calculate travel times:
        FIRST Enroute -> FIRST Arrived for each WO# per Technician.
        """

        travel_entries = []

        grouped = df.sort_values("Current Date").groupby(["WO#", "Technician"])

        for (wo, tech), group in grouped:
            enroute_times = group[group["Tech Status"] == "Enroute"]["Current Date"]
            arrived_times = group[group["Tech Status"] == "Arrived"]["Current Date"]

            if len(enroute_times) > 0 and len(arrived_times) > 0:
                start_time = enroute_times.min()
                end_time = arrived_times.min()

                travel_minutes = (end_time - start_time).total_seconds() / 60

                if travel_minutes > 0:
                    travel_entries.append({
                        "WO#": wo,
                        "Technician": tech,
                        "Travel_Minutes": travel_minutes
                    })

        return pd.DataFrame(travel_entries)

    df_travel = extract_travel_times(df_filtered)

    # =========================================================
    # NEW: JOBS-PER-MILE CALCULATION
    # =========================================================

    def parse_distance(val):
        if pd.isna(val):
            return None
        s = str(val).lower().replace("miles", "").replace("mile", "").strip()
        try:
            return float(s)
        except:
            return None

    df_filtered["Miles"] = df_filtered["Distance"].apply(parse_distance)

    # Unique jobs per technician
    job_counts = df_filtered.groupby("Technician")["WO#"].nunique().reset_index()
    job_counts.rename(columns={"WO#": "Total_Jobs"}, inplace=True)

    # Sum miles per technician
    miles_per_tech = df_filtered.groupby("Technician")["Miles"].sum().reset_index()
    miles_per_tech.rename(columns={"Miles": "Total_Miles"}, inplace=True)

    # Merge jobs + miles
    df_jobs_per_mile = job_counts.merge(miles_per_tech, on="Technician", how="left")

    # Calculate KPI values
    df_jobs_per_mile["Jobs_Per_Mile"] = df_jobs_per_mile["Total_Jobs"] / df_jobs_per_mile["Total_Miles"]
    df_jobs_per_mile["Miles_Per_Job"] = df_jobs_per_mile["Total_Miles"] / df_jobs_per_mile["Total_Jobs"]

    # Overall metrics
    overall_jobs = df_filtered["WO#"].nunique()
    overall_miles = df_filtered["Miles"].sum()

    overall_jobs_per_mile = overall_jobs / overall_miles if overall_miles > 0 else 0
    overall_miles_per_job = overall_miles / overall_jobs if overall_jobs > 0 else 0

    # =========================================================
    # DISPLAY KPIs
    # =========================================================

    st.markdown("### 📌 Work Orders KPIs")

    k1, k2, k3 = st.columns(3)
    k1.metric("🔧 Total Jobs", df_filtered["WO#"].nunique())
    k2.metric("👨‍🔧 Technicians", df_filtered["Technician"].nunique())
    k3.metric("🛣 Total Miles Driven", f"{overall_miles:.1f} miles")

    # ---------- Travel Time KPIs ----------
    if not df_travel.empty:
        avg_travel = df_travel["Travel_Minutes"].mean()
        fastest = df_travel["Travel_Minutes"].min()
        slowest = df_travel["Travel_Minutes"].max()

        t1, t2, t3 = st.columns(3)
        t1.metric("⏱ Avg Travel Time", f"{avg_travel:.1f} mins")
        t2.metric("⚡ Fastest Travel", f"{fastest:.1f} mins")
        t3.metric("🐢 Longest Travel", f"{slowest:.1f} mins")

    # ---------- Jobs Per Mile KPIs ----------
    jm1, jm2 = st.columns(2)
    jm1.metric("🚗 Overall Jobs Per Mile", f"{overall_jobs_per_mile:.3f}")
    jm2.metric("🛣 Overall Miles Per Job", f"{overall_miles_per_job:.2f}")

    # =========================================================
    # CHART: Avg Travel Time Per Technician
    # =========================================================

    if not df_travel.empty:
        df_tt = df_travel.groupby("Technician")["Travel_Minutes"].mean().reset_index()

        fig_tt = px.bar(
            df_tt,
            x="Technician",
            y="Travel_Minutes",
            title="Average Travel Time Per Technician",
            template="plotly_dark",
            color="Travel_Minutes",
        )
        fig_tt.update_layout(yaxis_title="Avg Travel (mins)")
        st.plotly_chart(fig_tt, use_container_width=True)

    # =========================================================
    # CHART: Jobs Per Mile Per Technician
    # =========================================================

    fig_jpm = px.bar(
        df_jobs_per_mile,
        x="Technician",
        y="Jobs_Per_Mile",
        title="Jobs Per Mile by Technician",
        template="plotly_dark",
        color="Jobs_Per_Mile"
    )
    fig_jpm.update_layout(yaxis_title="Jobs Per Mile")
    st.plotly_chart(fig_jpm, use_container_width=True)

    # =========================================================
    # INSTALLATION REWORK SECTION (UNCHANGED)
    # =========================================================

    st.markdown("---")
    st.markdown("<h2 style='color:#8BC53F;'>🔁 Installation Rework Analysis</h2>", unsafe_allow_html=True)

    re_mode = st.sidebar.radio(
        "Installation Rework File",
        ["Upload New File", "Load Existing File"],
        key="re_mode_file"
    )
    df_rework = None

    # Upload new
    if re_mode == "Upload New File":
        re_file = st.sidebar.file_uploader(
            "Upload Installation Assessment File",
            type=["csv", "txt"],
            key="re_upload_file"
        )
        re_filename = st.sidebar.text_input(
            "Enter name to save (no extension):",
            key="re_filename_input"
        )

        if re_file and re_filename:
            filename = re_filename + ".csv"
            bytes_re = re_file.getvalue()

            local_path = os.path.join(saved_folder, filename)
            with open(local_path, "wb") as f:
                f.write(bytes_re)

            upload_workorders_file_to_github(filename, bytes_re)

            df_rework = pd.read_csv(local_path, header=None)

    else:
        github_files = list_github_workorders()

        if github_files:
            selected = st.sidebar.selectbox(
                "Select Installation Rework File", github_files,
                key="re_select_file"
            )
            local = download_github_workorder_file(selected)
            df_rework = pd.read_csv(local, header=None)

    # -------- Parse and visualize rework --------
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

            df_combined["Technician"] = df_combined["Technician"].astype(str).str.strip().str.replace('"', '')
            df_combined["Total_Installations"] = pd.to_numeric(df_combined["Total_Installations"], errors="coerce")
            df_combined["Rework"] = pd.to_numeric(df_combined["Rework"], errors="coerce")
            df_combined["Rework_Percentage"] = (
                df_combined["Rework_Percentage"].astype(str)
                .str.replace("%", "").str.replace('"', "").str.strip()
            )
            df_combined["Rework_Percentage"] = pd.to_numeric(df_combined["Rework_Percentage"], errors="coerce")

            df_combined.dropna(subset=["Technician", "Total_Installations"], inplace=True)
            df_combined = df_combined.sort_values("Total_Installations", ascending=False)

            st.markdown("### 📌 Installation Rework KPIs")
            t1, t2, t3 = st.columns(3)
            t1.metric("🏗️ Total Installations", int(df_combined["Total_Installations"].sum()))
            t2.metric("🔁 Total Reworks", int(df_combined["Rework"].sum()))
            t3.metric("📈 Avg Rework %", f"{df_combined['Rework_Percentage'].mean():.1f}%")

            # TABLE
            def color_rework(val):
                if pd.isna(val): return ""
                if val < 5: return "background-color:#3CB371;color:white;"
                if val < 10: return "background-color:#FFD700;color:black;"
                return "background-color:#FF6347;color:white;"

            styled_table = (
                df_combined.style
                .map(color_rework, subset=["Rework_Percentage"])
                .format({
                    "Rework_Percentage": "{:.1f}%",
                    "Total_Installations": "{:.0f}",
                    "Rework": "{:.0f}",
                })
            )
            st.dataframe(styled_table)

            # COMBO CHART
            st.markdown("### 📊 Installations vs Rework %")
            fig = make_subplots(specs=[[{"secondary_y": True}]])
            fig.add_trace(go.Bar(
                x=df_combined["Technician"],
                y=df_combined["Total_Installations"],
                name="Total Installations",
                marker_color="#00BFFF",
            ), secondary_y=False)
            fig.add_trace(go.Scatter(
                x=df_combined["Technician"],
                y=df_combined["Rework_Percentage"],
                name="Rework %",
                mode="lines+markers",
                line=dict(color="#FF6347", width=3),
            ), secondary_y=True)
            fig.update_layout(
                title="Technician Installations vs Rework %",
                template="plotly_dark",
                xaxis_title="Technician",
            )
            st.plotly_chart(fig, use_container_width=True)

        except Exception as e:
            st.error(f"Error parsing installation rework: {e}")


# RUN APP
if __name__ == "__main__":
    run_workorders_dashboard()
