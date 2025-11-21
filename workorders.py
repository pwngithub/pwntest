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
    token, repo, branch, remote_prefix = get_github_config_workorders()
    if not token or not repo:
        return None
    api_url = f"https://api.github.com/repos/{repo}/contents/{remote_prefix}{filename}"
    headers = {"Authorization": f"token {token}"}
    resp = requests.get(api_url, headers=headers)
    if resp.status_code != 200:
        return None
    j = resp.json()
    if j.get("download_url"):
        raw = requests.get(j["download_url"])
        file_bytes = raw.content
    else:
        file_bytes = base64.b64decode(j["content"])
    local_folder = "saved_uploads"
    os.makedirs(local_folder, exist_ok=True)
    local_path = os.path.join(local_folder, filename)
    with open(local_path, "wb") as f:
        f.write(file_bytes)
    return local_path


def upload_workorders_file_to_github(filename: str, file_bytes: bytes):
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
        "message": f"Add/update {filename} via Work Orders Dashboard",
        "content": content_b64,
        "branch": branch,
    }
    if sha:
        payload["sha"] = sha
    put_resp = requests.put(api_url, headers=headers, json=payload)
    if put_resp.status_code in (200, 201):
        st.sidebar.success(f"Pushed: {filename}")
    else:
        st.sidebar.error(f"Upload failed: {put_resp.status_code}")


# =================================================
# MAIN DASHBOARD
# =================================================

def run_workorders_dashboard():
    st.set_page_config(page_title="PBB Work Orders Dashboard", layout="wide", initial_sidebar_state="expanded")

    # Custom CSS
    st.markdown("""
    <style>
    .stApp {background-color: #0E1117;}
    div[data-testid="metric-container"] {background-color: #262730;border: 1px solid #3c3c3c;padding: 15px;border-radius: 10px;
        box-shadow: 0 4px 8px rgba(0,0,0,0.4);transition: transform 0.2s;color: #FAFAFA;}
    div[data-testid="metric-container"]:hover {transform: scale(1.05);border-color: #8BC53F;}
    .logo-container {text-align:center;margin-bottom:20px;}
    .main-title {color:#FFFFFF;text-align:center;font-weight:bold;}
    </style>
    """, unsafe_allow_html=True)

    # Logo + Title
    st.markdown("""
    <div class='logo-container'>
        <img src='https://images.squarespace-cdn.com/content/v1/651eb4433b13e72c1034f375/369c5df0-5363-4827-b041-1add0367f447/PBB+long+logo.png?format=1500w' width='400'>
    </div>
    """, unsafe_allow_html=True)
    st.markdown("<h1 class='main-title'>Pioneer Broadband Work Orders Dashboard</h1>", unsafe_allow_html=True)
    st.markdown("<hr>", unsafe_allow_html=True)

    saved_folder = "saved_uploads"
    os.makedirs(saved_folder, exist_ok=True)

    # =================================================
    # LOAD WORK ORDERS
    # =================================================
    st.sidebar.header("Work Orders File")
    mode = st.sidebar.radio("Select Mode", ["Upload New Work Orders File", "Load Existing Work Orders File"], key="wo_mode")
    df = None

    if mode == "Upload New Work Orders File":
        uploaded_file = st.sidebar.file_uploader("Upload Work Orders CSV", type=["csv"], key="wo_upload")
        custom_filename = st.sidebar.text_input("Save as (no extension):", key="wo_filename")
        if uploaded_file and custom_filename:
            file_bytes = uploaded_file.getvalue()
            filename = custom_filename.strip() + ".csv"
            local_path = os.path.join(saved_folder, filename)
            with open(local_path, "wb") as f:
                f.write(file_bytes)
            upload_workorders_file_to_github(filename, file_bytes)
            df = pd.read_csv(local_path)
    else:
        github_files = list_github_workorders()
        if not github_files:
            st.error("No files found in GitHub/workorders/"); st.stop()
        selected_file = st.sidebar.selectbox("Select Work Orders File", github_files, key="wo_select_github")
        if selected_file:
            local_path = download_github_workorder_file(selected_file)
            if local_path:
                df = pd.read_csv(local_path)

    if df is None:
        st.info("Please upload or select a work orders file.")
        st.stop()

    # =================================================
    # STANDARDIZE TECHNICIAN NAMES (THIS FIXES CAMERON CALLNAN)
    # =================================================
    def standardize_tech_name(s):
        return (s.astype(str)
                .str.strip()
                .str.replace(r"\s+", " ", regex=True)
                .str.title()
                .str.replace(r"\.$", "", regex=True)
                .str.replace(r"\s*\(.*\)$", "", regex=True)
                .replace({"Cameron Callan": "Cameron Callnan", "Cam Callnan": "Cameron Callnan", "Cameron Callnan ": "Cameron Callnan"})
                )

    if "Techinician" in df.columns:
        df.rename(columns={"Techinician": "Technician"}, inplace=True)
    if "Technician" in df.columns:
        df["Technician"] = standardize_tech_name(df["Technician"])

    # =================================================
    # DATE & FILTERS
    # =================================================
    date_cols = [c for c in df.columns if str(c).lower() in ["date when","date","work date","completed","completion date"]]
    if not date_cols:
        st.error("No date column found."); st.stop()
    date_col = date_cols[0]
    df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
    df = df.dropna(subset=[date_col])
    df["Day"] = df[date_col].dt.date

    min_day, max_day = df["Day"].min(), df["Day"].max()
    st.subheader("F I L T E R S")
    start_date, end_date = st.date_input("Date Range", [min_day, max_day], min_value=min_day, max_value=max_day)
    df_filtered = df[(df["Day"] >= start_date) & (df["Day"] <= end_date)]

    if "Technician" in df_filtered.columns and "Work Type" in df_filtered.columns:
        techs = sorted(df_filtered["Technician"].dropna().unique())
        wtypes = sorted(df_filtered["Work Type"].dropna().unique())
        col1, col2 = st.columns(2)
        with col1:
            selected_techs = st.multiselect("Technician(s)", techs, default=techs)
        with col2:
            selected_wtypes = st.multiselect("Work Type(s)", wtypes, default=wtypes)
        df_filtered = df_filtered[df_filtered["Technician"].isin(selected_techs) & df_filtered["Work Type"].isin(selected_wtypes)]

    required = ['WO#', 'Duration', 'Technician', 'Work Type']
    if any(c not in df_filtered.columns for c in required):
        st.error(f"Missing columns: {[c for c in required if c not in df_filtered.columns]}"); st.stop()

    # =================================================
    # KPIs (NOW SHOWS 8 TECHS)
    # =================================================
    st.markdown("### Work Orders KPIs")
    kpi = df_filtered.dropna(subset=['WO#', 'Technician'])
    total_jobs = kpi["WO#"].nunique()
    tech_count = kpi["Technician"].nunique()   # ← Cameron is now here!
    avg_jobs = total_jobs / tech_count if tech_count else 0

    c1, c2, c3 = st.columns(3)
    c1.metric("Total Jobs", total_jobs)
    c2.metric("Tech Count", tech_count)
    c3.metric("Avg Jobs per Tech", f"{avg_jobs:.1f}")

    # Charts
    df_avg = df_filtered.copy()
    df_avg["Duration_Mins"] = pd.to_numeric(df_avg["Duration"].astype(str).str.extract(r"(\d+\.?\d*)")[0], errors="coerce")
    df_avg = df_avg.dropna(subset=["Duration_Mins"])

    if not df_avg.empty:
        grouped = df_avg.groupby(["Technician", "Work Type"]).agg(Total_Jobs=("WO#", "nunique"), Avg_Duration=("Duration_Mins", "mean")).reset_index()
        fig1 = px.bar(grouped, x="Work Type", y="Total_Jobs", color="Technician", title="Jobs by Work Type & Technician", template="plotly_dark")
        fig2 = px.bar(grouped, x="Work Type", y="Avg_Duration", color="Technician", title="Avg Duration by Work Type & Tech (mins)", template="plotly_dark")
        st.plotly_chart(fig1, use_container_width=True)
        st.plotly_chart(fig2, use_container_width=True)

    st.markdown("---")

    # =================================================
    # INSTALLATION REWORK (NAMES NOW MATCH)
    # =================================================
    st.markdown("<h2 style='color:#8BC53F;'>Installation Rework Analysis</h2>", unsafe_allow_html=True)
    re_mode = st.sidebar.radio("Rework File", ["Upload New File", "Load Existing File"], key="re_mode")
    df_rework = None

    if re_mode == "Upload New File":
        file = st.sidebar.file_uploader("Upload Assessment File", type=["csv","txt"], key="re_up")
        name = st.sidebar.text_input("Save as (no extension):", key="re_name")
        if file and name:
            data = file.getvalue()
            path = os.path.join(saved_folder, name.strip() + ".csv")
            with open(path, "wb") as f: f.write(data)
            upload_workorders_file_to_github(name.strip() + ".csv", data)
            df_rework = pd.read_csv(path, header=None)
    else:
        files = list_github_workorders()
        if files:
            sel = st.sidebar.selectbox("Select Rework File", files, key="re_sel")
            if sel:
                path = download_github_workorder_file(sel)
                if path:
                    df_rework = pd.read_csv(path, header=None)

    if df_rework is not None and not df_rework.empty:
        try:
            rows = []
            for _, row in df_rework.iterrows():
                v = row.tolist()
                if len(v) > 1 and str(v[1]).startswith("Install"):
                    base = [v[i] for i in [0,2,3,4] if i < len(v)]
                else:
                    base = [v[i] for i in [0,1,2,3] if i < len(v)]
                while len(base) < 4: base.append(None)
                rows.append(base)

            df_re = pd.DataFrame(rows, columns=["Technician", "Total_Installations", "Rework", "Rework_Percentage"])
            df_re["Technician"] = standardize_tech_name(df_re["Technician"])

            df_re["Total_Installations"] = pd.to_numeric(df_re["Total_Installations"], errors="coerce")
            df_re["Rework"] = pd.to_numeric(df_re["Rework"], errors="coerce")
            df_re["Rework_Percentage"] = pd.to_numeric(df_re["Rework_Percentage"].astype(str).str.replace(r"[^\d.]", "", regex=True), errors="coerce")
            df_re.dropna(subset=["Technician", "Total_Installations"], inplace=True)
            df_re = df_re.sort_values("Total_Installations", ascending=False)

            total_i = df_re["Total_Installations"].sum()
            total_r = df_re["Rework"].sum()
            avg_p = df_re["Rework_Percentage"].mean()

            c1, c2, c3 = st.columns(3)
            c1.metric("Total Installs", int(total_i))
            c2.metric("Total Reworks", int(total_r))
            c3.metric("Avg Rework %", f"{avg_p:.1f}%")

            def color(val):
                if pd.isna(val): return ""
                return "background-color:#3CB371;color:white" if val < 5 else "background-color:#FFD700;color:black" if val < 10 else "background-color:#FF6347;color:white"

            st.dataframe(df_re.style.map(color, subset=["Rework_Percentage"]).format({"Rework_Percentage": "{:.1f}%"}), use_container_width=True)

            fig = make_subplots(specs=[[{"secondary_y": True}]])
            fig.add_trace(go.Bar(x=df_re["Technician"], y=df_re["Total_Installations"], name="Installs", marker_color="#00BFFF"), secondary_y=False)
            fig.add_trace(go.Scatter(x=df_re["Technician"], y=df_re["Rework_Percentage"], name="Rework %", mode="lines+markers", line=dict(color="#FF6347", width=3)), secondary_y=True)
            fig.add_hline(y=avg_p, line_dash="dash", line_color="cyan", annotation_text=f"Avg {avg_p:.1f}%", secondary_y=True)
            fig.update_layout(title="Installations vs Rework %", template="plotly_dark")
            st.plotly_chart(fig, use_container_width=True)

            st.download_button("Download Rework CSV", df_re.to_csv(index=False).encode(), "rework_summary.csv", "text/csv")

        except Exception as e:
            st.error(f"Rework error: {e}")

    # Debug (remove after confirming)
    with st.expander("Debug – Technician Names", expanded=False):
        st.write("Work Orders:", sorted(df["Technician"].unique()))
        if 'df_re' in locals():
            st.write("Rework File:", sorted(df_re["Technician"].unique()))

if __name__ == "__main__":
    run_workorders_dashboard()
