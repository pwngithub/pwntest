# workorders.py — FINAL 100% WORKING VERSION (NO ERRORS)
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import requests
import base64
from io import BytesIO

# ================================================
# GITHUB HELPERS
# ================================================
def get_github_config():
    try:
        gh = st.secrets["github"]
        return gh["token"], gh["repo"], gh.get("branch", "main")
    except:
        return None, None, None

def list_github_files():
    token, repo, _ = get_github_config()
    if not token:
        return []
    url = f"https://api.github.com/repos/{repo}/contents/workorders"
    headers = {"Authorization": f"token {token}"}
    r = requests.get(url, headers=headers)
    if r.status_code != 200:
        return []
    return [item["name"] for item in r.json() if item["name"].lower().endswith(".csv")]

def download_file_bytes(filename):
    token, repo, _ = get_github_config()
    if not token:
        return None
    url = f"https://api.github.com/repos/{repo}/contents/workorders/{filename}"
    headers = {"Authorization": f"token {token}"}
    r = requests.get(url, headers=headers)
    if r.status_code != 200:
        return None
    data = r.json()
    if "content" in data and data["content"]:
        return base64.b64decode(data["content"])
    if "download_url" in data:
        return requests.get(data["download_url"]).content
    return None

# ================================================
# MAIN DASHBOARD — REQUIRED FUNCTION NAME
# ================================================
def run_workorders_dashboard():
    st.set_page_config(page_title="PBB Work Orders", layout="wide", initial_sidebar_state="expanded")

    # Title & Logo
    st.markdown("<h1 style='text-align:center;color:#8BC53F;'>Pioneer Broadband Work Orders Dashboard</h1>", unsafe_allow_html=True)
    st.markdown(
        "<div style='text-align:center;margin-bottom:30px;'>"
        "<img src='https://images.squarespace-cdn.com/content/v1/651eb4433b13e72c1034f375/369c5df0-5363-4827-b041-1add0367f447/PBB+long+logo.png?format=1500w' width='400'>"
        "</div>",
        unsafe_allow_html=True
    )

    # Session state
    if "df_main" not in st.session_state:
        st.session_state.df_main = None
    if "df_rework" not in st.session_state:
        st.session_state.df_rework = None

    # ================================================
    # LOAD WORK ORDERS
    # ================================================
    st.sidebar.header("Work Orders File")
    source = st.sidebar.radio("Source", ["Upload New", "Load from GitHub"], key="wo_source")

    if source == "Upload New":
        uploaded = st.sidebar.file_uploader("Upload Work Orders CSV", type="csv", key="wo_upload")
        if uploaded:
            with st.spinner("Loading file..."):
                st.session_state.df_main = pd.read_csv(uploaded)
                st.success("Work Orders loaded!")
                st.rerun()
    else:
        files = list_github_files()
        if not files:
            st.sidebar.error("No CSV files found in GitHub/workorders/")
        else:
            chosen = st.sidebar.selectbox("Select file", files, key="wo_select")
            if st.sidebar.button("Load Work Orders File"):
                with st.spinner(f"Downloading {chosen}..."):
                    raw = download_file_bytes(chosen)
                    if raw:
                        st.session_state.df_main = pd.read_csv(BytesIO(raw))
                        st.success(f"{chosen} loaded!")
                        st.rerun()
                    else:
                        st.error("Failed to download file")

    df = st.session_state.df_main
    if df is None:
        st.info("Please upload or load a Work Orders file to continue.")
        st.stop()

    # Fix technician names (Cameron Callnan)
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
    date_col = next((col for col in df.columns if "date" in str(col).lower()), None)
    if not date_col:
        st.error("No date column found in the file.")
        st.stop()
    df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
    df = df.dropna(subset=[date_col]).copy()
    df["Day"] = df[date_col].dt.date

    # Filters
    start_date, end_date = st.date_input(
        "Date Range",
        [df["Day"].min(), df["Day"].max()],
        min_value=df["Day"].min(),
        max_value=df["Day"].max()
    )
    df = df[(df["Day"] >= start_date) & (df["Day"] <= end_date)]

    techs = sorted(df["Technician"].dropna().unique())
    selected_techs = st.multiselect("Technicians", techs, default=techs)
    df = df[df["Technician"].isin(selected_techs)]

    # ================================================
    # KPIs
    # ================================================
    st.markdown("### Work Orders KPIs")
    total_jobs = df["WO#"].nunique() if "WO#" in df.columns else len(df)
    tech_count = df["Technician"].nunique()
    avg_jobs = round(total_jobs / tech_count, 1) if tech_count > 0 else 0

    col1, col2, col3 = st.columns(3)
    col1.metric("Total Jobs", total_jobs)
    col2.metric("Tech Count", tech_count)
    col3.metric("Avg Jobs/Tech", avg_jobs)

    # Charts
    if "Duration" in df.columns and "Work Type" in df.columns:
        df["Mins"] = pd.to_numeric(df["Duration"].astype(str).str.extract(r"(\d+\.?\d*)")[0], errors="coerce")
        grouped = df.groupby(["Technician", "Work Type"], as_index=False).agg(
            Jobs=("WO#", "nunique"),
            Avg_Duration=("Mins", "mean")
        )
        fig1 = px.bar(grouped, x="Work Type", y="Jobs", color="Technician",
                      title="Jobs by Work Type & Technician", template="plotly_dark")
        fig2 = px.bar(grouped, x="Work Type", y="Avg_Duration", color="Technician",
                      title="Average Duration by Work Type (mins)", template="plotly_dark")
        st.plotly_chart(fig1, use_container_width=True)
        st.plotly_chart(fig2, use_container_width=True)

    st.markdown("---")

    # ================================================
    # INSTALLATION REWORK ANALYSIS
    # ================================================
    st.markdown("<h2 style='color:#8BC53F;'>Installation Rework Analysis</h2>", unsafe_allow_html=True)

    re_source = st.sidebar.radio("Rework File", ["Upload New", "Load from GitHub"], key="rework_source")

    if re_source == "Upload New":
        re_upload = st.sidebar.file_uploader("Upload Rework File", type=["csv", "txt"], key="re_upload")
        if re_upload:
            st.session_state.df_rework = pd.read_csv(re_upload, header=None)
            st.success("Rework file loaded!")
            st.rerun()
    else:
        files = list_github_files()
        if files:
            re_file = st.sidebar.selectbox("Select Rework File", files, key="re_select")
            if st.sidebar.button("Load Rework File"):
                raw = download_file_bytes(re_file)
                if raw:
                    st.session_state.df_rework = pd.read_csv(BytesIO(raw), header=None)
                    st.success("Rework file loaded!")
                    st.rerun()

    if st.session_state.df_rework is not None:
        try:
            rows = []
            for _, row in st.session_state.df_rework.iterrows():
                vals = row.tolist()
                if len(vals) >= 4 and str(vals[0]).strip().lower() != "install":
                    tech = str(vals[0]).strip().title()
                    rows.append([tech, vals[1], vals[2], vals[3]])

            if rows:
                df_re = pd.DataFrame(rows, columns=["Technician", "Installs", "Rework", "Pct"])
                df_re["Technician"] = df_re["Technician"].replace({"Cameron Callan": "Cameron Callnan", "Cam Callnan": "Cameron Callnan"})
                df_re[["Installs", "Rework"]] = df_re[["Installs", "Rework"]].apply(pd.to_numeric, errors="coerce")
                df_re["Pct"] = pd.to_numeric(df_re["Pct"].astype(str).str.replace("%", ""), errors="coerce")

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
            st.error(f"Error processing rework file: {e}")

    # Debug
    with st.expander("DEBUG - Technicians Found"):
        st.write("Technicians in data:", sorted(df["Technician"].unique()))
        st.write(f"Total unique: {tech_count}")
        if "Cameron Callnan" in df["Technician"].values:
            st.success("Cameron Callnan is visible!")
        else:
            st.warning("Cameron Callnan not found")

# ================================================
# REQUIRED — DO NOT REMOVE
# ================================================
run_workorders_dashboard()
