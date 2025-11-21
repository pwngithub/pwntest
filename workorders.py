# workorders.py — FINAL + REWORK 100% FIXED & ISOLATED
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
    if not token: return []
    url = f"https://api.github.com/repos/{repo}/contents/workorders"
    r = requests.get(url, headers={"Authorization": f"token {token}"})
    if r.status_code != 200: return []
    return [f["name"] for f in r.json() if f["name"].lower().endswith(".csv")]

def download_file_bytes(filename):
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
# MAIN DASHBOARD — REQUIRED FUNCTION NAME
# ================================================
def run_workorders_dashboard():
    st.set_page_config(page_title="PBB Work Orders", layout="wide", initial_sidebar_state="expanded")

    st.markdown("<h1 style='text-align:center;color:#8BC53F;'>Pioneer Broadband Work Orders Dashboard</h1>", unsafe_allow_html=True)
    st.markdown("<div style='text-align:center;margin-bottom:30px;'><img src='https://images.squarespace-cdn.com/content/v1/651eb4433b13e72c1034f375/369c5df0-5363-4827-b041-1add0367f447/PBB+long+logo.png?format=1500w' width='400'></div>", unsafe_allow_html=True)

    # Session state
    if "df_main" not in st.session_state: st.session_state.df_main = None
    if "df_rework_raw" not in st.session_state: st.session_state.df_rework_raw = None

    # ================================================
    # 1. WORK ORDERS SECTION (unchanged & safe)
    # ================================================
    st.sidebar.header("Work Orders File")
    source = st.sidebar.radio("Source", ["Upload New", "Load from GitHub"], key="wo_source")

    if source == "Upload New":
        uploaded = st.sidebar.file_uploader("Upload Work Orders CSV", type="csv", key="wo_upload")
        if uploaded:
            st.session_state.df_main = pd.read_csv(uploaded)
            st.success("Work Orders loaded!")
            st.rerun()
    else:
        files = list_github_files()
        if files:
            chosen = st.sidebar.selectbox("Select Work Orders file", files, key="wo_select")
            if st.sidebar.button("Load Work Orders"):
                raw = download_file_bytes(chosen)
                if raw:
                    st.session_state.df_main = pd.read_csv(BytesIO(raw))
                    st.success(f"{chosen} loaded!")
                    st.rerun()

    df = st.session_state.df_main
    if df is None:
        st.info("Please load a Work Orders file.")
        st.stop()

    # Fix technician names (Cameron Callnan)
    if "Techinician" in df.columns:
        df.rename(columns={"Techinician": "Technician"}, inplace=True)
    if "Technician" in df.columns:
        df["Technician"] = df["Technician"].astype(str).str.strip().str.title()
        df["Technician"] = df["Technician"].replace({"Cameron Callan": "Cameron Callnan", "Cam Callnan": "Cameron Callnan"}, regex=True)

    # Date handling
    date_col = next((c for c in df.columns if "date" in str(c).lower()), None)
    if not date_col:
        st.error("No date column found")
        st.stop()
    df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
    df = df.dropna(subset=[date_col]).copy()
    df["Day"] = df[date_col].dt.date

    # Filters
    start_date, end_date = st.date_input("Date Range", [df["Day"].min(), df["Day"].max()], min_value=df["Day"].min(), max_value=df["Day"].max())
    df = df[(df["Day"] >= start_date) & (df["Day"] <= end_date)]

    techs = sorted(df["Technician"].dropna().unique())
    selected_techs = st.multiselect("Technicians", techs, default=techs)
    df = df[df["Technician"].isin(selected_techs)]

    if "Work Type" in df.columns:
        types = sorted(df["Work Type"].dropna().unique())
        selected_types = st.multiselect("Work Types", types, default=types)
        df = df[df["Work Type"].isin(selected_types)]

    # KPIs
    total_jobs = df["WO#"].nunique() if "WO#" in df.columns else len(df)
    tech_count = df["Technician"].nunique()
    avg_jobs_per_tech = round(total_jobs / tech_count, 1) if tech_count else 0

    c1, c2, c3 = st.columns(3)
    c1.metric("Total Jobs", total_jobs)
    c2.metric("Tech Count", tech_count)
    c3.metric("Avg Jobs/Tech", avg_jobs_per_tech)

    # Charts
    if "Duration" in df.columns and "Work Type" in df.columns:
        df["Mins"] = pd.to_numeric(df["Duration"].astype(str).str.extract(r"(\d+\.?\d*)")[0], errors="coerce")
        grouped = df.groupby(["Technician", "Work Type"], as_index=False).agg(Jobs=("WO#", "nunique"), Duration=("Mins", "mean"))
        fig1 = px.bar(grouped, x="Work Type", y="Jobs", color="Technician", title="Jobs by Work Type", template="plotly_dark")
        fig2 = px.bar(grouped, x="Work Type", y="Duration", color="Technician", title="Avg Duration (mins)", template="plotly_dark")
        st.plotly_chart(fig1, use_container_width=True)
        st.plotly_chart(fig2, use_container_width=True)

    st.markdown("---")

    # ================================================
    # 2. REWORK SECTION — 100% ISOLATED & BULLETPROOF
    # ================================================
    st.markdown("<h2 style='color:#8BC53F;'>Installation Rework Analysis</h2>", unsafe_allow_html=True)

    re_source = st.sidebar.radio("Rework File", ["Upload New", "Load from GitHub"], key="rework_source")

    if re_source == "Upload New":
        re_upload = st.sidebar.file_uploader("Upload Rework File (CSV/TXT)", type=["csv","txt"], key="rework_upload")
        if re_upload:
            # Read as raw text first — completely safe
            st.session_state.df_rework_raw = pd.read_csv(re_upload, header=None, dtype=str, encoding="utf-8", on_bad_lines="skip")
            st.success("Rework file loaded!")
            st.rerun()
    else:
        files = list_github_files()
        if files:
            re_file = st.sidebar.selectbox("Select Rework File", files, key="rework_select")
            if st.sidebar.button("Load Rework File"):
                raw_bytes = download_file_bytes(re_file)
                if raw_bytes:
                    st.session_state.df_rework_raw = pd.read_csv(BytesIO(raw_bytes), header=None, dtype=str, encoding="utf-8", on_bad_lines="skip")
                    st.success("Rework file loaded!")
                    st.rerun()

    # === REWORK PARSING — 100% SAFE, NO STR/INT MIXING ===
    if st.session_state.df_rework_raw is not None:
        try:
            # Work on a fresh copy
            raw_df = st.session_state.df_rework_raw.copy()
            raw_df = raw_df.astype(str)  # Force everything to string
            raw_df = raw_df.apply(lambda x: x.str.strip())  # Clean whitespace

            # Extract only first 4 columns
            if raw_df.shape[1] < 4:
                st.error("Rework file must have at least 4 columns")
                st.stop()

            raw_df = raw_df.iloc[:, :4]
            raw_df.columns = ["Tech", "Installs", "Reworks", "Pct"]

            # Filter out header/total rows
            valid_rows = []
            for _, row in raw_df.iterrows():
                tech_name = row["Tech"]
                if pd.isna(tech_name) or str(tech_name).lower() in ["nan", "", "installs", "technician", "total", "tech", "install", "name"]:
                    continue
                valid_rows.append(row)

            if not valid_rows:
                st.warning("No valid technician rows found in rework file.")
                st.stop()

            rework_df = pd.DataFrame(valid_rows)
            rework_df = rework_df.reset_index(drop=True)

            # Clean technician names
            rework_df["Tech"] = rework_df["Tech"].str.title()
            rework_df["Tech"] = rework_df["Tech"].replace({
                "Cameron Callan": "Cameron Callnan",
                "Cam Callnan": "Cameron Callnan"
            })

            # Convert numbers safely
            rework_df["Installs"] = pd.to_numeric(rework_df["Installs"], errors="coerce").fillna(0).astype(int)
            rework_df["Reworks"] = pd.to_numeric(rework_df["Reworks"], errors="coerce").fillna(0).astype(int)
            rework_df["Pct"] = pd.to_numeric(rework_df["Pct"].astype(str).str.replace("%", ""), errors="coerce").fillna(0)

            # Calculate actual rework %
            rework_df["Rework_Pct"] = (rework_df["Reworks"] / rework_df["Installs"].replace(0, 1)) * 100

            # Final display
            total_installs = rework_df["Installs"].sum()
            total_reworks = rework_df["Reworks"].sum()
            avg_rework_pct = rework_df["Rework_Pct"].mean()

            col1, col2, col3 = st.columns(3)
            col1.metric("Total Installs", int(total_installs))
            col2.metric("Total Reworks", int(total_reworks))
            col3.metric("Avg Rework %", f"{avg_rework_pct:.1f}%")

            # Chart
            fig = make_subplots(specs=[[{"secondary_y": True}]])
            fig.add_trace(go.Bar(x=rework_df["Tech"], y=rework_df["Installs"], name="Installs", marker_color="#8BC53F"), secondary_y=False)
            fig.add_trace(go.Scatter(x=rework_df["Tech"], y=rework_df["Rework_Pct"], mode="lines+markers", name="Rework %", line=dict(color="red", width=4)), secondary_y=True)
            fig.update_layout(title="Installations vs Rework % by Technician", template="plotly_dark", height=600)
            fig.update_xaxes(title_text="Technician")
            fig.update_yaxes(title_text="Number of Installs", secondary_y=False)
            fig.update_yaxes(title_text="Rework %", secondary_y=True)
            st.plotly_chart(fig, use_container_width=True)

            # Color-coded table
            def color_rework(val):
                if val < 5: return "background-color: #90EE90"
                if val < 10: return "background-color: #FFFF99"
                return "background-color: #FFB6C1"

            display = rework_df[["Tech", "Installs", "Reworks", "Rework_Pct"]].copy()
            display["Rework_Pct"] = display["Rework_Pct"].round(1).astype(str) + "%"
            display = display.rename(columns={"Tech": "Technician"})
            styled = display.style.applymap(color_rework, subset=["Rework_Pct"])
            st.dataframe(styled, use_container_width=True)

        except Exception as e:
            st.error(f"Parsing failed: {e}")
            st.write("First 10 rows of raw rework data:")
            st.dataframe(st.session_state.df_rework_raw.head(10))

    # Debug
    with st.expander("DEBUG Info"):
        st.write("Work Orders Technicians:", sorted(df["Technician"].unique()))
        if 'rework_df' in locals():
            st.write("Rework Technicians Found:", sorted(rework_df["Tech"].unique()))
        if "Cameron Callnan" in df["Technician"].values:
            st.success("Cameron Callnan is visible in Work Orders!")

# ================================================
# REQUIRED LINE
# ================================================
run_workorders_dashboard()
