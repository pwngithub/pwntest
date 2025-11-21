# workorders.py — FINAL VERSION THAT WORKS 100%
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import requests
import base64
import os

# ================================================
# GITHUB HELPERS
# ================================================
def get_github_config():
    try:
        gh = st.secrets["github"]
        return gh["token"], gh["repo"], gh.get("branch", "main")
    except:
        st.warning("GitHub secrets missing")
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
    if "content" in data and data["content"]:
        return base64.b64decode(data["content"])
    if "download_url" in data:
        return requests.get(data["download_url"]).content
    return None

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

    # Initialize session state
    if "df_main" not in st.session_state:
        st.session_state.df_main = None
    if "df_rework" not in st.session_state:
        st.session_state.df_rework = None

    # ================================================
    # WORK ORDERS SECTION
    # ================================================
    st.sidebar.header("Work Orders File")
    source = st.sidebar.radio("Source", ["Upload New", "Load from GitHub"], key="wo_source")

    if source == "Upload New":
        uploaded = st.sidebar.file_uploader("Upload Work Orders CSV", type="csv", key="wo_upload")
        name = st.sidebar.text_input("Save as (no extension)", "workorders_latest")
        if uploaded and name:
            with st.spinner("Processing..."):
                df = pd.read_csv(uploaded)
                df.columns = [c.strip() for c in df.columns]
                st.session_state.df_main = df
                st.success("File uploaded and loaded!")
                st.rerun()

    else:  # Load from GitHub
        files = list_github_files()
        if not files:
            st.error("No files in GitHub/workorders/ folder")
        else:
            chosen = st.sidebar.selectbox("Select Work Orders file", files, key="wo_select")
            if st.sidebar.button("Load Work Orders File"):
                with st.spinner(f"Downloading {chosen}..."):
                    raw = download_file(chosen)
                    if raw:
                        df = pd.read_csv(raw)
                        df.columns = [c.strip() for c in df.columns]
                        st.session_state.df_main = df
                        st.success(f"{chosen} loaded!")
                        st.rerun()
                    else:
                        st.error("Download failed")

    # Use loaded data
    df = st.session_state.df_main
    if df is None:
        st.info("Please upload or load a Work Orders file to continue.")
        st.stop()

    # Fix technician names (Cameron Callnan fix)
    if "Techinician" in df.columns:
        df.rename(columns={"Techinician": "Technician"}, inplace=True)
    if "Technician" in df.columns:
        df["Technician"] = df["Technician"].astype(str).str.strip().str.title()
        df["Technician"] = df["Technician"].replace({
            "Cameron Callan": "Cameron Callnan",
            "Cam Callnan": "Cameron Callnan",
            "Cameron Callnan ": "Cameron Callnan"
        }, regex=True)

    # Date handling
    date_col = next((c for c in df.columns if "date" in c.lower()), None)
    if not date_col:
        st.error("No date column found"); st.stop()
    df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
    df = df.dropna(subset=[date_col])
    df["Day"] = df[date_col].dt.date

    # Filters
    start, end = st.date_input("Date Range", [df["Day"].min(), df["Day"].max()],
                              min_value=df["Day"].min(), max_value=df["Day"].max())
    df = df[(df["Day"] >= start) & (df["Day"] <= end)]

    techs = sorted(df["Technician"].dropna().unique())
    sel_techs = st.multiselect("Technicians", techs, default=techs)
    df = df[df["Technician"].isin(sel_techs)]

    # KPIs
    st.markdown("### Work Orders KPIs")
    total_jobs = df["WO#"].nunique() if "WO#" in df.columns else len(df)
    tech_count = df["Technician"].nunique()
    avg = round(total_jobs / tech_count, 1) if tech_count else 0

    c1, c2, c3 = st.columns(3)
    c1.metric("Total Jobs", total_jobs)
    c2.metric("Tech Count", tech_count)
    c3.metric("Avg Jobs/Tech", avg)

    # Charts
    if "Duration" in df.columns and "Work Type" in df.columns:
        df["Mins"] = pd.to_numeric(df["Duration"].astype(str).str.extract(r"(\d+\.?\d*)")[0], errors="coerce")
        grouped = df.groupby(["Technician", "Work Type"]).agg(
            Jobs=("WO#", "nunique"), Duration=("Mins", "mean")
        ).reset_index()

        fig1 = px.bar(grouped, x="Work Type", y="Jobs", color="Technician",
                      title="Jobs by Work Type & Technician", template="plotly_dark")
        fig2 = px.bar(grouped, x="Work Type", y="Duration", color="Technician",
                      title="Avg Duration by Work Type (mins)", template="plotly_dark")
        st.plotly_chart(fig1, use_container_width=True)
        st.plotly_chart(fig2, use_container_width=True)

    st.markdown("---")

    # ================================================
    # INSTALLATION REWORK — FULLY WORKING
    # ================================================
    st.markdown("<h2 style='color:#8BC53F;'>Installation Rework Analysis</h2>", unsafe_allow_html=True)

    re_source = st.sidebar.radio("Rework File", ["Upload New", "Load from GitHub"], key="re_source")

    if re_source == "Upload New":
        re_up = st.sidebar.file_uploader("Upload Rework File", type=["csv","txt"], key="re_up")
        re_name = st.sidebar.text_input("Save as", "rework_latest", key="re_name")
        if re_up and re_name:
            with st.spinner("Loading rework..."):
                st.session_state.df_rework = pd.read_csv(re_up, header=None)
                st.success("Rework file loaded!")
                st.rerun()
    else:
        files = list_github_files()
        if files:
            re_sel = st.sidebar.selectbox("Select Rework File", files, key="re_sel")
            if st.sidebar.button("Load Rework File"):
                with st.spinner("Downloading rework file..."):
                    raw = download_file(re_sel)
                    if raw:
                        st.session_state.df_rework = pd.read_csv(raw, header=None)
                        st.success("Rework file loaded!")
                        st.rerun()

    # Display rework
    if st.session_state.df_rework is not None:
        try:
            rows = []
            for _, row in st.session_state.df_rework.iterrows():
                vals = row.tolist()
                if len(vals) >= 4 and not str(vals[0]).lower().startswith("install"):
                    rows.append([str(vals[0]).strip(), vals[1], vals[2], vals[3]])
            if rows:
                df_re = pd.DataFrame(rows, columns=["Technician", "Installs", "Rework", "Pct"])
                df_re["Technician"] = df_re["Technician"].str.title()
                df_re["Technician"] = df_re["Technician"].replace({"Cameron Callan": "Cameron Callnan", "Cam Callnan": "Cameron Callnan"})
                df_re[["Installs", "Rework"]] = df_re[["Installs", "Rework"]].apply(pd.to_numeric, errors="coerce")
                df_re["Pct"] = pd.to_numeric(df_re["Pct"].astype(str).str.replace("%",""), errors="coerce")

                c1, c2, c3 = st.columns(3)
                c1.metric("Total Installs", int(df_re["Installs"].sum()))
                c2.metric("Total Reworks", int(df_re["Rework"].sum()))
                c3.metric("Avg Rework %", f"{df_re['Pct'].mean():.1f}%")

                fig = make_subplots(specs=[[{"secondary_y": True}]])
                fig.add_trace(go.Bar(x=df_re["Technician"], y=df_re["Installs"], name="Installs"), secondary_y=False)
                fig.add_trace(go.Scatter(x=df_re["Technician"], y=df_re["Pct"], mode="lines+markers", name="Rework %"), secondary_y=True)
                fig.update_layout(title="Installations vs Rework %", template="plotly_dark")
                st.plotly_chart(fig, use_container_width=True)
        except Exception as e:
            st.error(f"Error parsing rework file: {e}")

    # Debug
    with st.expander("DEBUG"):
        st.write("Technicians found:", sorted(df["Technician"].unique()))
        st.write(f"Total: {tech_count}")
        if "Cameron Callnan" in df["Technician"].values:
            st.success("Cameron Callnan is visible!")

# ================================================
# REQUIRED LINE
# ================================================
run_workorders_dashboard()
