# workorders.py — FINAL + REWORK 100% RESTORED TO ORIGINAL BEHAVIOR
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
# MAIN DASHBOARD
# ================================================
def run_workorders_dashboard():
    st.set_page_config(page_title="PBB Work Orders", layout="wide", initial_sidebar_state="expanded")

    st.markdown("<h1 style='text-align:center;color:#8BC53F;'>Pioneer Broadband Work Orders Dashboard</h1>", unsafe_allow_html=True)
    st.markdown(
        "<div style='text-align:center;margin-bottom:30px;'>"
        "<img src='https://images.squarespace-cdn.com/content/v1/651eb4433b13e72c1034f375/369c5df0-5363-4827-b041-1add0367f447/PBB+long+logo.png?format=1500w' width='400'>"
        "</div>", unsafe_allow_html=True
    )

    if "df_main" not in st.session_state: st.session_state.df_main = None
    if "df_rework" not in st.session_state: st.session_state.df_rework = None

    # ================================================
    # LOAD WORK ORDERS
    # ================================================
    st.sidebar.header("Work Orders File")
    source = st.sidebar.radio("Source", ["Upload New", "Load from GitHub"], key="wo_src")

    if source == "Upload New":
        uploaded = st.sidebar.file_uploader("Upload Work Orders CSV", type="csv")
        if uploaded:
            st.session_state.df_main = pd.read_csv(uploaded)
            st.success("Work Orders loaded!")
            st.rerun()
    else:
        files = list_github_files()
        if files:
            chosen = st.sidebar.selectbox("Select file", files, key="wo_sel")
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

    # Fix technician names
    if "Techinician" in df.columns:
        df.rename(columns={"Techinician": "Technician"}, inplace=True)
    if "Technician" in df.columns:
        df["Technician"] = df["Technician"].astype(str).str.strip().str.title()
        df["Technician"] = df["Technician"].replace({
            "Cameron Callan": "Cameron Callnan",
            "Cam Callnan": "Cameron Callnan"
        }, regex=True)

    # Date column
    date_col = next((c for c in df.columns if "date" in str(c).lower()), None)
    if not date_col:
        st.error("No date column found")
        st.stop()
    df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
    df = df.dropna(subset=[date_col])
    df["Day"] = df[date_col].dt.date

    # Filters
    start_date, end_date = st.date_input("Date Range", [df["Day"].min(), df["Day"].max()],
                                        min_value=df["Day"].min(), max_value=df["Day"].max())
    df = df[(df["Day"] >= start_date) & (df["Day"] <= end_date)]

    techs = sorted(df["Technician"].dropna().unique())
    selected_techs = st.multiselect("Technicians", techs, default=techs, key="tech_filter")
    df = df[df["Technician"].isin(selected_techs)]

    if "Work Type" in df.columns:
        types = sorted(df["Work Type"].dropna().unique())
        selected_types = st.multiselect("Work Types", types, default=types, key="type_filter")
        df = df[df["Work Type"].isin(selected_types)]

    # KPIs
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
        grouped = df.groupby(["Technician", "Work Type"], as_index=False).agg(
            Jobs=("WO#", "nunique"),
            Avg_Duration=("Mins", "mean")
        )
        fig1 = px.bar(grouped, x="Work Type", y="Jobs", color="Technician", title="Jobs by Work Type & Technician", template="plotly_dark")
        fig2 = px.bar(grouped, x="Work Type", y="Avg_Duration", color="Technician", title="Avg Duration (mins)", template="plotly_dark")
        st.plotly_chart(fig1, use_container_width=True)
        st.plotly_chart(fig2, use_container_width=True)

    st.markdown("---")

    # ================================================
    # REWORK — EXACTLY LIKE YOUR ORIGINAL (RESTORED 100%)
    # ================================================
    st.markdown("<h2 style='color:#8BC53F;'>Installation Rework Analysis</h2>", unsafe_allow_html=True)

    re_source = st.sidebar.radio("Rework File", ["Upload New", "Load from GitHub"], key="re_src")

    if re_source == "Upload New":
        re_file = st.sidebar.file_uploader("Upload Rework CSV", type=["csv","txt"], key="re_up")
        if re_file:
            st.session_state.df_rework = pd.read_csv(re_file, header=None)
            st.success("Rework file loaded!")
            st.rerun()
    else:
        files = list_github_files()
        if files:
            re_sel = st.sidebar.selectbox("Select Rework File", files, key="re_sel")
            if st.sidebar.button("Load Rework File"):
                raw = download_file_bytes(re_sel)
                if raw:
                    st.session_state.df_rework = pd.read_csv(BytesIO(raw), header=None)
                    st.success("Rework loaded!")
                    st.rerun()

    # === EXACT ORIGINAL REWORK PARSING LOGIC ===
    if st.session_state.df_rework is not None and not st.session_state.df_rework.empty:
        rows = []
        for _, row in st.session_state.df_rework.iterrows():
            vals = row.tolist()
            if len(vals) >= 4:
                tech_name = str(vals[0]).strip()
                # Skip header rows
                if tech_name.lower().startswith(("install", "tech", "total")):
                    continue
                rows.append([tech_name.title(), vals[1], vals[2], vals[3]])

        if rows:
            df_re = pd.DataFrame(rows, columns=["Technician", "Installs", "Rework", "Pct"])
            df_re["Technician"] = df_re["Technician"].replace({
                "Cameron Callan": "Cameron Callnan",
                "Cam Callnan": "Cameron Callnan"
            })
            df_re["Installs"] = pd.to_numeric(df_re["Installs"], errors="coerce")
            df_re["Rework"] = pd.to_numeric(df_re["Rework"], errors="coerce")
            df_re["Pct"] = pd.to_numeric(df_re["Pct"].astype(str).str.replace("%", ""), errors="coerce") / 100

            total_installs = df_re["Installs"].sum()
            total_rework = df_re["Rework"].sum()
            avg_pct = (df_re["Rework"] / df_re["Installs"]).mean() * 100

            c1, c2, c3 = st.columns(3)
            c1.metric("Total Installs", int(total_installs))
            c2.metric("Total Reworks", int(total_rework))
            c3.metric("Avg Rework %", f"{avg_pct:.1f}%")

            fig = make_subplots(specs=[[{"secondary_y": True}]])
            fig.add_trace(go.Bar(x=df_re["Technician"], y=df_re["Installs"], name="Installs"), secondary_y=False)
            fig.add_trace(go.Scatter(x=df_re["Technician"], y=df_re["Pct"]*100, mode="lines+markers", name="Rework %"), secondary_y=True)
            fig.update_layout(title="Installations vs Rework %", template="plotly_dark")
            st.plotly_chart(fig, use_container_width=True)

            # Color-coded table
            def color_pct(val):
                val = float(val.strip("%")) if isinstance(val, str) else val*100
                if val < 5: return "background-color: #90EE90"
                if val < 10: return "background-color: #FFFF99"
                return "background-color: #FFB6C1"

            styled = df_re.copy()
            styled["Pct"] = styled["Pct"].apply(lambda x: f"{x*100:.1f}%" if pd.notnull(x) else "0%")
            styled = styled.style.applymap(color_pct, subset=["Pct"])
            st.dataframe(styled, use_container_width=True)

    # Debug
    with st.expander("DEBUG"):
        st.write("Technicians:", sorted(df["Technician"].unique()))
        if "Cameron Callnan" in df["Technician"].values:
            st.success("Cameron Callnan is visible!")

# ================================================
# REQUIRED
# ================================================
run_workorders_dashboard()
