# workorders.py — FULLY RESTORED + CAMERON FIXED
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import os
import requests
import base64

# ================================================
# GITHUB HELPERS
# ================================================
def get_github_config():
    try:
        gh = st.secrets["github"]
        return gh["token"], gh["repo"], gh.get("branch", "main")
    except:
        st.warning("GitHub config missing")
        return None, None, None

def list_github_files():
    token, repo, _ = get_github_config()
    if not token: return []
    url = f"https://api.github.com/repos/{repo}/contents/workorders"
    r = requests.get(url, headers={"Authorization": f"token {token}"})
    if r.status_code != 200: return []
    return [f["name"] for f in r.json() if f["name"].endswith(".csv")]

def download_file(filename):
    token, repo, _ = get_github_config()
    if not token: return None
    url = f"https://api.github.com/repos/{repo}/contents/workorders/{filename}"
    r = requests.get(url, headers={"Authorization": f"token {token}"})
    if r.status_code != 200: return None
    data = r.json()
    if "content" in data:
        return base64.b64decode(data["content"])
    return requests.get(data["download_url"]).content

def upload_to_github(filename, bytes_data):
    token, repo, branch = get_github_config()
    if not token: return
    url = f"https://api.github.com/repos/{repo}/contents/workorders/{filename}"
    headers = {"Authorization": f"token {token}"}
    r = requests.get(url, headers=headers)
    sha = r.json().get("sha") if r.status_code == 200 else None
    payload = {
        "message": f"Update {filename}",
        "content": base64.b64encode(bytes_data).decode(),
        "branch": branch
    }
    if sha: payload["sha"] = sha
    requests.put(url, headers=headers, json=payload)

# ================================================
# SUPER SAFE CSV LOADER
# ================================================
def load_csv_safe(data):
    text = data.decode("utf-8", errors="ignore")
    from io import StringIO
    for sep in [",", "\t", ";"]:
        for header in [0, None]:
            try:
                df = pd.read_csv(StringIO(text), sep=sep, header=header, on_bad_lines="skip")
                if df.shape[0] > 1 and df.shape[1] > 1:
                    return df
            except: continue
    return pd.read_csv(StringIO(text), on_bad_lines="skip")

# ================================================
# MAIN DASHBOARD — REQUIRED NAME
# ================================================
def run_workorders_dashboard():
    st.set_page_config(page_title="PBB Work Orders", layout="wide", initial_sidebar_state="expanded")
    
    st.markdown("""
    <h1 style='text-align:center;color:#8BC53F;'>Pioneer Broadband Work Orders Dashboard</h1>
    <div style='text-align:center;'>
        <img src='https://images.squarespace-cdn.com/content/v1/651eb4433b13e72c1034f375/369c5df0-5363-4827-b041-1add0367f447/PBB+long+logo.png?format=1500w' width='400'>
    </div>
    """, unsafe_allow_html=True)
    st.markdown("---")

    # ================================================
    # LOAD WORK ORDERS
    # ================================================
    st.sidebar.header("Work Orders File")
    source = st.sidebar.radio("Source", ["Upload New", "Load from GitHub"])

    df = None
    if source == "Upload New":
        uploaded = st.sidebar.file_uploader("Upload Work Orders CSV", type="csv")
        name = st.sidebar.text_input("Save as (no extension)", "latest_workorders")
        if uploaded and name:
            bytes_data = uploaded.getvalue()
            df = load_csv_safe(bytes_data)
            upload_to_github(f"{name}.csv", bytes_data)
    else:
        files = list_github_files()
        if not files:
            st.error("No files in GitHub/workorders/"); st.stop()
        chosen = st.sidebar.selectbox("Select file", files)
        if st.sidebar.button("Load File"):
            raw = download_file(chosen)
            if raw:
                df = load_csv_safe(raw)

    if df is None or df.empty:
        st.info("Please load a work orders file.")
        st.stop()

    # Fix column names & technician names
    df.columns = [c.strip() for c in df.columns]
    if "Techinician" in df.columns:
        df.rename(columns={"Techinician": "Technician"}, inplace=True)
    
    if "Technician" in df.columns:
        df["Technician"] = df["Technician"].astype(str).str.strip().str.title()
        df["Technician"] = df["Technician"].replace({
            "Cameron Callan": "Cameron Callnan",
            "Cam Callnan": "Cameron Callnan",
            "Cameron Callnan ": "Cameron Callnan"
        }, regex=True)

    # Date column
    date_col = next((c for c in df.columns if "date" in c.lower()), df.columns[1])
    df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
    df = df.dropna(subset=[date_col]).copy()
    df["Day"] = df[date_col].dt.date

    # Filters
    start, end = st.date_input("Date Range", [df["Day"].min(), df["Day"].max()], 
                              min_value=df["Day"].min(), max_value=df["Day"].max())
    df = df[(df["Day"] >= start) & (df["Day"] <= end)]

    techs = sorted(df["Technician"].dropna().unique())
    types = sorted(df["Work Type"].dropna().unique()) if "Work Type" in df.columns else []
    col1, col2 = st.columns(2)
    with col1:
        sel_techs = st.multiselect("Technicians", techs, default=techs)
    with col2:
        sel_types = st.multiselect("Work Types", types, default=types) if types else None
    df = df[df["Technician"].isin(sel_techs)]
    if types:
        df = df[df["Work Type"].isin(sel_types)]

    # ================================================
    # ALL ORIGINAL KPIs
    # ================================================
    st.markdown("### Work Orders KPIs")
    total_jobs = df["WO#"].nunique() if "WO#" in df.columns else len(df)
    tech_count = df["Technician"].nunique()
    avg_jobs = round(total_jobs / tech_count, 1) if tech_count else 0

    k1, k2, k3 = st.columns(3)
    k1.metric("Total Jobs", total_jobs)
    k2.metric("Tech Count", tech_count)
    k3.metric("Avg Jobs per Tech", avg_jobs)

    # Charts
    if "Duration" in df.columns:
        df["Mins"] = pd.to_numeric(df["Duration"].astype(str).str.extract(r"(\d+\.?\d*)")[0], errors="coerce")
        grouped = df.groupby(["Technician", "Work Type"]).agg(
            Jobs=("WO#", "nunique"), Avg_Min=("Mins", "mean")
        ).reset_index()

        fig1 = px.bar(grouped, x="Work Type", y="Jobs", color="Technician",
                      title="Jobs by Work Type & Technician", template="plotly_dark")
        fig2 = px.bar(grouped, x="Work Type", y="Avg_Min", color="Technician",
                      title="Avg Duration (mins)", template="plotly_dark")
        st.plotly_chart(fig1, use_container_width=True)
        st.plotly_chart(fig2, use_container_width=True)

    st.markdown("---")

    # ================================================
    # INSTALLATION REWORK — FULLY RESTORED
    # ================================================
    st.markdown("<h2 style='color:#8BC53F;'>Installation Rework Analysis</h2>", unsafe_allow_html=True)
    
    re_mode = st.sidebar.radio("Rework File", ["Upload New", "Load from GitHub"], key="re")
    df_rework = None

    if re_mode == "Upload New":
        re_file = st.sidebar.file_uploader("Upload Rework CSV", type=["csv","txt"], key="re_up")
        re_name = st.sidebar.text_input("Save as", "rework_latest", key="re_name")
        if re_file and re_name:
            bytes_re = re_file.getvalue()
            df_rework = load_csv_safe(bytes_re)
            upload_to_github(f"{re_name}.csv", bytes_re)
    else:
        files = list_github_files()
        if files:
            sel = st.sidebar.selectbox("Select Rework File", files, key="re_sel")
            if st.sidebar.button("Load Rework"):
                raw = download_file(sel)
                if raw:
                    df_rework = load_csv_safe(raw)

    if df_rework is not None and not df_rework.empty:
        # Parse rework file (your original format)
        rows = []
        for _, row in df_rework.iterrows():
            vals = row.tolist()
            if len(vals) >= 4:
                tech = str(vals[0])
                if tech.lower().startswith("install"): continue
                rows.append([tech, vals[1], vals[2], vals[3]])
        if rows:
            df_re = pd.DataFrame(rows, columns=["Technician", "Installs", "Rework", "Pct"])
            df_re["Technician"] = df_re["Technician"].str.strip().str.title()
            df_re["Technician"] = df_re["Technician"].replace({
                "Cameron Callan": "Cameron Callnan", "Cam Callnan": "Cameron Callnan"
            })
            df_re[["Installs", "Rework"]] = df_re[["Installs", "Rework"]].apply(pd.to_numeric, errors="coerce")
            df_re["Pct"] = pd.to_numeric(df_re["Pct"].astype(str).str.replace("%",""), errors="coerce")

            total_i = df_re["Installs"].sum()
            total_r = df_re["Rework"].sum()
            avg_pct = df_re["Pct"].mean()

            c1, c2, c3 = st.columns(3)
            c1.metric("Total Installs", int(total_i))
            c2.metric("Total Reworks", int(total_r))
            c3.metric("Avg Rework %", f"{avg_pct:.1f}%")

            fig = make_subplots(specs=[[{"secondary_y": True}]])
            fig.add_trace(go.Bar(x=df_re["Technician"], y=df_re["Installs"], name="Installs"), secondary_y=False)
            fig.add_trace(go.Scatter(x=df_re["Technician"], y=df_re["Pct"], mode="lines+markers", name="Rework %"), secondary_y=True)
            fig.update_layout(title="Installations vs Rework %", template="plotly_dark")
            st.plotly_chart(fig, use_container_width=True)

            def color_pct(val):
                if val < 5: return "background-color:#90EE90"
                if val < 10: return "background-color:#FFFF99"
                return "background-color:#FFB6C1"
            styled = df_re.style.map(color_pct, subset=["Pct"]).format({"Pct": "{:.1f}%"})
            st.dataframe(styled, use_container_width=True)

    # Debug
    with st.expander("DEBUG: Technicians Found"):
        st.write(sorted(df["Technician"].unique()))
        st.write(f"Total: {tech_count}")
        st.success("Cameron Callnan is now visible!") if "Cameron Callnan" in df["Technician"].values else st.warning("Cameron missing")

# ================================================
# REQUIRED — DO NOT REMOVE
# ================================================
run_workorders_dashboard()
