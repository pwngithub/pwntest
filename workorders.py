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
# GITHUB HELPERS (Stable)
# =================================================

def get_github_config_workorders():
    try:
        gh = st.secrets["github"]
        token = gh["token"]
        repo = gh["repo"]
        branch = gh.get("branch", "main")
        folder = "workorders/"
        return token, repo, branch, folder
    except:
        st.error("❌ GitHub secrets missing under [github].")
        return None, None, None, None


def list_github_workorders():
    token, repo, branch, folder = get_github_config_workorders()
    if not token:
        return []

    url = f"https://api.github.com/repos/{repo}/contents/{folder}"
    headers = {"Authorization": f"token {token}"}
    r = requests.get(url, headers=headers)

    if r.status_code != 200:
        return []

    return [f["name"] for f in r.json()
            if f["type"] == "file" and f["name"].endswith(".csv")]


def download_github_workorder_file(filename):
    token, repo, branch, folder = get_github_config_workorders()
    if not token:
        return None

    api_url = f"https://api.github.com/repos/{repo}/contents/{folder}{filename}"
    headers = {"Authorization": f"token {token}"}
    r = requests.get(api_url, headers=headers)

    if r.status_code != 200:
        return None

    data = r.json()

    if data.get("download_url"):
        file_bytes = requests.get(data["download_url"]).content
    else:
        file_bytes = base64.b64decode(data["content"])

    os.makedirs("saved_uploads", exist_ok=True)
    local = os.path.join("saved_uploads", filename)

    with open(local, "wb") as f:
        f.write(file_bytes)

    return local


def upload_workorders_file_to_github(filename, file_bytes):
    token, repo, branch, folder = get_github_config_workorders()
    if not token:
        return

    remote = f"{folder}{filename}"
    url = f"https://api.github.com/repos/{repo}/contents/{remote}"
    headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github+json"}

    sha = None
    existing = requests.get(url, headers=headers)
    if existing.status_code == 200:
        sha = existing.json().get("sha")

    payload = {
        "message": f"Update {filename}",
        "content": base64.b64encode(file_bytes).decode(),
        "branch": branch
    }
    if sha:
        payload["sha"] = sha

    r = requests.put(url, headers=headers, json=payload)
    if r.status_code not in (200, 201):
        st.error(f"❌ GitHub upload failed: {r.status_code} {r.text}")
    else:
        st.sidebar.success(f"📤 Uploaded to GitHub → {filename}")


# =================================================
# TIMESTAMP PARSER
# =================================================

def safe_timestamp(x):
    if pd.isna(x):
        return None
    try:
        return pd.to_datetime(x)
    except:
        try:
            return datetime.strptime(x, "%m/%d/%Y %H:%M")
        except:
            try:
                return datetime.strptime(x, "%m/%d/%Y %H:%M:%S %p")
            except:
                return None


# =================================================
# MAIN DASHBOARD
# =================================================

def run_workorders_dashboard():
    st.set_page_config(page_title="PBB Work Orders Dashboard", layout="wide")

    st.image(
        "https://images.squarespace-cdn.com/content/v1/651eb4433b13e72c1034f375/"
        "369c5df0-5363-4827-b041-1add0367f447/PBB+long+logo.png?format=1500w",
        width=330
    )
    st.markdown("<h1 style='text-align:center;color:white;'>🛠 Pioneer Broadband Work Orders Dashboard</h1>",
                unsafe_allow_html=True)
    st.markdown("---")

    os.makedirs("saved_uploads", exist_ok=True)

    # =================================================
    # FILE LOAD
    # =================================================

    st.sidebar.header("📁 Work Orders File")
    mode = st.sidebar.radio("Choose Mode", ["Upload New", "Load Existing"], key="wo_mode")

    df = None

    if mode == "Upload New":
        up = st.sidebar.file_uploader("Upload CSV", type=["csv"], key="wo_upload")
        name = st.sidebar.text_input("Filename", key="wo_filename")

        if up and name:
            fname = name + ".csv"
            b = up.getvalue()

            local = f"saved_uploads/{fname}"
            with open(local, "wb") as f:
                f.write(b)

            upload_workorders_file_to_github(fname, b)
            df = pd.read_csv(local)

    else:
        files = list_github_workorders()
        if not files:
            st.error("❌ No Work Orders files in GitHub/workorders/")
            st.stop()

        sel = st.sidebar.selectbox("Select File", files, key="wo_select")
        df = pd.read_csv(download_github_workorder_file(sel))

    if df is None:
        st.info("Upload or load a file to continue.")
        st.stop()

    # =================================================
    # CLEAN DATA
    # =================================================

    if "Techinician" in df.columns:
        df.rename(columns={"Techinician": "Technician"}, inplace=True)

    # Find date col
    date_candidates = ["Date When", "Current Date", "Work Date", "Completed", "Date"]
    date_col = None
    for c in df.columns:
        if c.strip().lower() in [x.lower() for x in date_candidates]:
            date_col = c
            break

    if not date_col:
        st.error("❌ No usable timestamp column found.")
        st.stop()

    df[date_col] = df[date_col].apply(safe_timestamp)
    df.dropna(subset=[date_col], inplace=True)
    df["Day"] = df[date_col].dt.date

    # =================================================
    # FILTERS
    # =================================================

    st.subheader("F I L T E R S")

    min_day, max_day = df["Day"].min(), df["Day"].max()
    start_date, end_date = st.date_input("📅 Date Range", [min_day, max_day],
                                         min_value=min_day, max_value=max_day)

    df_f = df[(df["Day"] >= start_date) & (df["Day"] <= end_date)]

    if df_f.empty:
        st.warning("No Work Orders found.")
        st.stop()

    if "Technician" in df_f.columns:
        all_techs = sorted(df_f["Technician"].dropna().unique())
        selected = st.multiselect("👨‍🔧 Technician(s)", all_techs, default=all_techs)
        df_f = df_f[df_f["Technician"].isin(selected)]

    if df_f.empty:
        st.warning("No Work Orders remain after filters.")
        st.stop()

    # =================================================
    # TRAVEL TIME (FIRST Enroute → FIRST Arrived)
    # =================================================

    def compute_travel(df):
        out = []
        grouped = df.sort_values(date_col).groupby(["WO#", "Technician"])

        for (wo, tech), g in grouped:
            enroute = g[g["Tech Status"] == "Enroute"][date_col]
            arrived = g[g["Tech Status"] == "Arrived"][date_col]

            if len(enroute) > 0 and len(arrived) > 0:
                start = enroute.min()
                end = arrived.min()
                mins = (end - start).total_seconds() / 60
                if mins > 0:
                    out.append({"WO#": wo, "Technician": tech, "Travel_Minutes": mins})
        return pd.DataFrame(out)

    df_travel = compute_travel(df_f)

    # =================================================
    # CORRECTED MILEAGE CALCULATION
    # OPTION A — **FIRST Arrived Distance per WO**
    # =================================================

    def parse_miles(x):
        if pd.isna(x): return None
        x = str(x).lower()
        for w in ["miles", "mile", "mi"]:
            x = x.replace(w, "")
        try:
            return float(x.strip())
        except:
            return None

    mileage_rows = []

    grouped = df_f.groupby(["WO#", "Technician"])
    for (wo, tech), g in grouped:
        arrived_rows = g[g["Tech Status"] == "Arrived"]
        if arrived_rows.empty:
            continue

        # First Arrived row
        first_arrived = arrived_rows.sort_values(date_col).iloc[0]

        miles_val = parse_miles(first_arrived.get("Distance", None))

        if miles_val is not None and miles_val > 0:
            mileage_rows.append({"WO#": wo, "Technician": tech, "Miles": miles_val})

    df_miles = pd.DataFrame(mileage_rows)

    # Sum mileage per tech
    tech_miles = df_miles.groupby("Technician")["Miles"].sum().reset_index()

    # Count jobs per tech
    tech_jobs = df_f.groupby("Technician")["WO#"].nunique().reset_index(name="Total_Jobs")

    df_jobs_miles = tech_jobs.merge(tech_miles, on="Technician", how="left")
    df_jobs_miles["Jobs_Per_Mile"] = df_jobs_miles["Total_Jobs"] / df_jobs_miles["Miles"]
    df_jobs_miles["Miles_Per_Job"] = df_jobs_miles["Miles"] / df_jobs_miles["Total_Jobs"]

    overall_jobs = df_f["WO#"].nunique()
    overall_miles = df_miles["Miles"].sum()

    overall_jpm = overall_jobs / overall_miles if overall_miles else 0
    overall_mpj = overall_miles / overall_jobs if overall_jobs else 0

    # =================================================
    # ORIGINAL KPIs
    # =================================================

    st.markdown("### 📌 Work Orders KPIs")

    df_kpi = df_f.dropna(subset=["Duration"])
    total_jobs = df_kpi["WO#"].nunique()
    tech_count = df_kpi["Technician"].nunique()
    avg_jobs = total_jobs / tech_count if tech_count else 0

    k1, k2, k3 = st.columns(3)
    k1.metric("🔧 Total Jobs", total_jobs)
    k2.metric("👨‍🔧 Tech Count", tech_count)
    k3.metric("📈 Avg Jobs per Tech", f"{avg_jobs:.1f}")

    # =================================================
    # NEW TRAVEL TIME KPIs
    # =================================================

    if not df_travel.empty:
        avg_tt = df_travel["Travel_Minutes"].mean()
        fast = df_travel["Travel_Minutes"].min()
        slow = df_travel["Travel_Minutes"].max()

        t1, t2, t3 = st.columns(3)
        t1.metric("⏱ Avg Travel Time", f"{avg_tt:.1f} mins")
        t2.metric("⚡ Fastest Travel", f"{fast:.1f} mins")
        t3.metric("🐢 Longest Travel", f"{slow:.1f} mins")

    # =================================================
    # NEW JOBS PER MILE KPIs
    # =================================================

    j1, j2 = st.columns(2)
    j1.metric("🚗 Overall Jobs Per Mile", f"{overall_jpm:.3f}")
    j2.metric("🛣 Miles Per Job (Overall)", f"{overall_mpj:.2f}")

    st.markdown("---")

    # =================================================
    # ORIGINAL AVERAGE DURATION CHARTS
    # =================================================

    st.markdown("### 📊 Overall Average Duration by Work Type")

    df_avg = df_f.dropna(subset=["Duration"])
    df_avg["Duration_Mins"] = pd.to_numeric(
        df_avg["Duration"].astype(str).str.extract(r"(\d+\.?\d*)")[0],
        errors="coerce"
    )

    gw = df_avg.groupby(["Work Type", "Technician"])["Duration_Mins"].mean().reset_index()
    w_avg = gw.groupby("Work Type")["Duration_Mins"].mean().reset_index()

    fig = px.bar(
        w_avg,
        x="Work Type",
        y="Duration_Mins",
        title="Average Duration by Work Type",
        template="plotly_dark",
        color="Duration_Mins"
    )
    fig.update_traces(marker_color="#8BC53F")
    st.plotly_chart(fig, use_container_width=True)

    # =================================================
    # ORIGINAL TECHNICIAN CHARTS
    # =================================================

    st.markdown("### 📊 Work Orders Charts by Technician")

    grouped_charts = (
        df_avg.groupby(["Technician", "Work Type"])
        .agg(
            Total_Jobs=("WO#", "nunique"),
            Avg_Duration=("Duration_Mins", "mean")
        )
        .reset_index()
    )

    fig1 = px.bar(
        grouped_charts,
        x="Work Type",
        y="Total_Jobs",
        color="Technician",
        title="Jobs by Work Type & Technician",
        template="plotly_dark"
    )
    st.plotly_chart(fig1, use_container_width=True)

    fig2 = px.bar(
        grouped_charts,
        x="Work Type",
        y="Avg_Duration",
        color="Technician",
        title="Avg Duration by Work Type & Technician (mins)",
        template="plotly_dark"
    )
    st.plotly_chart(fig2, use_container_width=True)

    # =================================================
    # NEW TRAVEL TIME CHART
    # =================================================

    if not df_travel.empty:
        st.markdown("### 📊 Average Travel Time per Technician")

        tt = df_travel.groupby("Technician")["Travel_Minutes"].mean().reset_index()

        fig_tt = px.bar(
            tt,
            x="Technician",
            y="Travel_Minutes",
            title="Avg Travel Time per Technician",
            template="plotly_dark",
            color="Travel_Minutes"
        )
        st.plotly_chart(fig_tt, use_container_width=True)

    # =================================================
    # NEW JOBS PER MILE CHART
    # =================================================

    st.markdown("### 📊 Jobs Per Mile by Technician")

    fig_jpm = px.bar(
        df_jobs_miles,
        x="Technician",
        y="Jobs_Per_Mile",
        title="Jobs Per Mile per Technician",
        template="plotly_dark",
        color="Jobs_Per_Mile"
    )
    st.plotly_chart(fig_jpm, use_container_width=True)

    st.markdown("---")

    # =================================================
    # INSTALLATION REWORK (unchanged)
    # =================================================

    st.markdown("<h2 style='color:#8BC53F;'>🔁 Installation Rework Analysis</h2>", unsafe_allow_html=True)

    re_mode = st.sidebar.radio("Rework Mode", ["Upload New", "Load Existing"], key="re_mode_file")

    df_rework = None

    if re_mode == "Upload New":
        up_r = st.sidebar.file_uploader("Upload Rework File", type=["csv", "txt"], key="re_up")
        name_r = st.sidebar.text_input("Rework Filename", key="re_name")

        if up_r and name_r:
            fn = name_r + ".csv"
            b = up_r.getvalue()

            local_r = f"saved_uploads/{fn}"
            with open(local_r, "wb") as f:
                f.write(b)

            upload_workorders_file_to_github(fn, b)

            df_rework = pd.read_csv(local_r, header=None)

    else:
        files_r = list_github_workorders()
        if files_r:
            sel_r = st.sidebar.selectbox("Select Rework File", files_r, key="re_sel")
            df_rework = pd.read_csv(download_github_workorder_file(sel_r), header=None)

    if df_rework is not None and not df_rework.empty:
        try:
            rows = []
            for _, row in df_rework.iterrows():
                v = row.tolist()
                if len(v) > 1 and str(v[1]).startswith("Install"):
                    vals = [v[i] for i in [0, 2, 3, 4] if i < len(v)]
                else:
                    vals = [v[i] for i in [0, 1, 2, 3] if i < len(v)]
                while len(vals) < 4:
                    vals.append(None)
                rows.append(vals)

            df_rw = pd.DataFrame(
                rows,
                columns=["Technician", "Total_Installations", "Rework", "Rework_Percentage"]
            )

            df_rw["Technician"] = df_rw["Technician"].astype(str).str.strip().str.replace('"', '')
            df_rw["Total_Installations"] = pd.to_numeric(df_rw["Total_Installations"], errors="coerce")
            df_rw["Rework"] = pd.to_numeric(df_rw["Rework"], errors="coerce")
            df_rw["Rework_Percentage"] = (
                df_rw["Rework_Percentage"].astype(str)
                .replace("%", "", regex=False)
                .str.strip()
            )
            df_rw["Rework_Percentage"] = pd.to_numeric(df_rw["Rework_Percentage"], errors="coerce")

            df_rw.dropna(subset=["Technician", "Total_Installations"], inplace=True)

            st.markdown("### 📌 Installation Rework KPIs")

            r1, r2, r3 = st.columns(3)
            r1.metric("🏗 Total Installs", int(df_rw["Total_Installations"].sum()))
            r2.metric("🔁 Total Reworks", int(df_rw["Rework"].sum()))
            r3.metric("📈 Avg Rework %", f"{df_rw['Rework_Percentage'].mean():.1f}%")

            def color_rw(v):
                if pd.isna(v): return ""
                if v < 5: return "background-color:#3CB371;color:white;"
                if v < 10: return "background-color:#FFD700;color:black;"
                return "background-color:#FF6347;color:white;"

            st.dataframe(
                df_rw.style
                .map(color_rw, subset=["Rework_Percentage"])
                .format({
                    "Total_Installations": "{:.0f}",
                    "Rework": "{:.0f}",
                    "Rework_Percentage": "{:.1f}%"
                })
            )

            st.markdown("### 📊 Installations vs Rework %")

            fig_rw = make_subplots(specs=[[{"secondary_y": True}]])
            fig_rw.add_trace(go.Bar(
                x=df_rw["Technician"],
                y=df_rw["Total_Installations"],
                name="Total Installs",
                marker_color="#00BFFF"
            ), secondary_y=False)

            fig_rw.add_trace(go.Scatter(
                x=df_rw["Technician"],
                y=df_rw["Rework_Percentage"],
                name="Rework %",
                mode="lines+markers",
                line=dict(color="#FF6347", width=3)
            ), secondary_y=True)

            fig_rw.update_layout(template="plotly_dark")
            st.plotly_chart(fig_rw, use_container_width=True)

        except Exception as e:
            st.error(f"❌ Error parsing rework file: {e}")


# RUN APP
if __name__ == "__main__":
    run_workorders_dashboard()
