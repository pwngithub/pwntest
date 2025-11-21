import streamlit as st
import pandas as pd
import plotly.express as px
import os
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import requests
import base64

# =================================================
# GITHUB HELPERS
# =================================================
def get_github_config_workorders():
    try:
        gh_cfg = st.secrets["github"]
        return gh_cfg["token"], gh_cfg["repo"], gh_cfg.get("branch", "main"), "workorders/"
    except:
        st.warning("GitHub secrets not configured.")
        return None, None, None, None

def list_github_workorders():
    token, repo, branch, prefix = get_github_config_workorders()
    if not token: return []
    url = f"https://api.github.com/repos/{repo}/contents/{prefix}"
    r = requests.get(url, headers={"Authorization": f"token {token}"})
    if r.status_code != 200: return []
    return [f["name"] for f in r.json() if f["type"] == "file" and f["name"].endswith(".csv")]

def download_github_workorder_file(filename):
    token, repo, branch, prefix = get_github_config_workorders()
    if not token: return None
    url = f"https://api.github.com/repos/{repo}/contents/{prefix}{filename}"
    r = requests.get(url, headers={"Authorization": f"token {token}"})
    if r.status_code != 200: return None
    j = r.json()
    content = base64.b64decode(j["content"]) if "content" in j else requests.get(j["download_url"]).content
    os.makedirs("saved_uploads", exist_ok=True)
    path = os.path.join("saved_uploads", filename)
    with open(path, "wb") as f: f.write(content)
    return path

def upload_workorders_file_to_github(filename: str, file_bytes: bytes):
    token, repo, branch, prefix = get_github_config_workorders()
    if not token: return
    url = f"https://api.github.com/repos/{repo}/contents/{prefix}{filename}"
    headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github+json"}
    r = requests.get(url, headers=headers)
    sha = r.json().get("sha") if r.status_code == 200 else None
    payload = {"message": f"Update {filename}", "content": base64.b64encode(file_bytes).decode(), "branch": branch}
    if sha: payload["sha"] = sha
    requests.put(url, headers=headers, json=payload)

# =================================================
# MAIN APP
# =================================================
def run_workorders_dashboard():
    st.set_page_config(page_title="PBB Work Orders", layout="wide", initial_sidebar_state="expanded")
    
    # Styling
    st.markdown("<style>.stApp{background:#0E1117;} .block-container{padding-top:2rem;}</style>", unsafe_allow_html=True)
    st.image("https://images.squarespace-cdn.com/content/v1/651eb4433b13e72c1034f375/369c5df0-5363-4827-b041-1add0367f447/PBB+long+logo.png?format=1500w", width=400, use_container_width=True)
    st.markdown("<h1 style='text-align:center;color:#8BC53F;'>Pioneer Broadband Work Orders Dashboard</h1>", unsafe_allow_html=True)
    st.markdown("<hr>", unsafe_allow_html=True)

    saved_folder = "saved_uploads"
    os.makedirs(saved_folder, exist_ok=True)

    # =================================================
    # LOAD WORK ORDERS (FIXED: tries header=None first)
    # =================================================
    st.sidebar.header("Work Orders File")
    mode = st.sidebar.radio("Mode", ["Upload New", "Load from GitHub"], key="mode")

    df = None
    if mode == "Upload New":
        uploaded = st.sidebar.file_uploader("Upload CSV", type="csv")
        name = st.sidebar.text_input("Save as (no extension)")
        if uploaded and name:
            bytes_data = uploaded.getvalue()
            path = os.path.join(saved_folder, f"{name.strip()}.csv")
            with open(path, "wb") as f: f.write(bytes_data)
            upload_workorders_file_to_github(f"{name.strip()}.csv", bytes_data)
            # Try with header first, fall back to no header
            try:
                df = pd.read_csv(path)
            except:
                df = pd.read_csv(path, header=None)
    else:
        files = list_github_workorders()
        if not files:
            st.error("No files in GitHub/workorders/"); st.stop()
        selected = st.sidebar.selectbox("Select file", files)
        path = download_github_workorder_file(selected)
        if path:
            try:
                df = pd.read_csv(path)
            except:
                df = pd.read_csv(path, header=None)

    if df is None or df.empty:
        st.info("Please upload or select a work orders file.")
        st.stop()

    # If no header, assume first row is data and assign generic column names
    if df.columns.astype(str).str.contains('^0$|^Unnamed').any() or len(df.columns) < 5:
        df = pd.read_csv(path, header=None)  # force no header
        expected_cols = ["WO#", "Date", "Technician", "Work Type", "Duration", "Status", "Notes"]
        df.columns = expected_cols[:len(df.columns)] + [f"Col{i}" for i in range(len(df.columns), 20)]

    # =================================================
    # STANDARDIZE TECHNICIAN NAMES (CAMERON FIX)
    # =================================================
    tech_col = next((c for c in df.columns if str(c).lower() in ["technician", "tech", "techinician"]), None)
    if tech_col:
        df.rename(columns={tech_col: "Technician"}, inplace=True)
        df["Technician"] = (df["Technician"]
                            .astype(str)
                            .str.strip()
                            .str.replace(r"\s+", " ", regex=True)
                            .str.title()
                            .str.replace(r"\.$", "", regex=True)
                            .str.replace(r"\s*\(.*\)$", "", regex=True)
                            .replace({"Cameron Callan": "Cameron Callnan", "Cam Callnan": "Cameron Callnan"}))
    else:
        st.error("No Technician column found."); st.stop()

    # Date column
    date_col = next((c for c in df.columns if "date" in str(c).lower()), None)
    if not date_col:
        st.error("No date column found."); st.stop()
    df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
    df = df.dropna(subset=[date_col])
    df["Day"] = df[date_col].dt.date

    # Filters
    start_date, end_date = st.date_input("Date Range", [df["Day"].min(), df["Day"].max()],
                                        min_value=df["Day"].min(), max_value=df["Day"].max())
    df = df[(df["Day"] >= start_date) & (df["Day"] <= end_date)]

    techs = sorted(df["Technician"].dropna().unique())
    work_types = sorted(df["Work Type"].dropna().unique()) if "Work Type" in df.columns else []
    col1, col2 = st.columns(2)
    with col1: selected_techs = st.multiselect("Technician(s)", techs, default=techs)
    with col2: selected_types = st.multiselect("Work Type(s)", work_types, default=work_types) if work_types else None
    df = df[df["Technician"].isin(selected_techs)]
    if work_types:
        df = df[df["Work Type"].isin(selected_types)]

    # =================================================
    # KPIs (NOW SHOWS 8)
    # =================================================
    st.markdown("### Work Orders KPIs")
    total_jobs = df["WO#"].nunique()
    tech_count = df["Technician"].nunique()
    avg = total_jobs / tech_count if tech_count else 0

    c1, c2, c3 = st.columns(3)
    c1.metric("Total Jobs", total_jobs)
    c2.metric("Tech Count", tech_count)
    c3.metric("Avg Jobs/Tech", f"{avg:.1f}")

    # =================================================
    # CHARTS — CAMERON NOW APPEARS
    # =================================================
    st.markdown("### Jobs by Work Type & Technician")
    chart_data = df.groupby(["Technician", "Work Type"], as_index=False)["WO#"].nunique()
    chart_data.rename(columns={"WO#": "Total_Jobs"}, inplace=True)

    fig = px.bar(chart_data, x="Work Type", y="Total_Jobs", color="Technician",
                 title="Jobs Completed by Work Type & Technician",
                 template="plotly_dark", text="Total_Jobs")
    fig.update_traces(textposition="outside")
    fig.update_layout(legend=dict(title="Technician", itemsizing="constant"))
    st.plotly_chart(fig, use_container_width=True)

    # Duration chart
    if "Duration" in df.columns:
        st.markdown("### Average Duration by Work Type & Technician")
        df_dur = df.copy()
        df_dur["Mins"] = pd.to_numeric(df_dur["Duration"].astype(str).str.extract(r"(\d+\.?\d*)")[0], errors="coerce")
        df_dur = df_dur.dropna(subset=["Mins"])
        if not df_dur.empty:
            dur = df_dur.groupby(["Technician", "Work Type"], as_index=False)["Mins"].mean()
            fig2 = px.bar(dur, x="Work Type", y="Mins", color="Technician",
                          title="Average Duration (minutes)", template="plotly_dark")
            st.plotly_chart(fig2, use_container_width=True)

    # =================================================
    # DEBUG (you can delete later)
    # =================================================
    with st.expander("Debug – All Technicians Found", expanded=False):
        st.write("Technicians in data:", sorted(df["Technician"].unique()))
        st.write(f"Total unique: {df['Technician'].nunique()}")

if __name__ == "__main__":
    run_workorders_dashboard()
