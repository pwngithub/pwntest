# File must be named: workorders.py
import streamlit as st
import pandas as pd
import plotly.express as px
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
        st.warning("GitHub secrets not set")
        return None, None, None

def list_github_files():
    token, repo, _ = get_github_config()
    if not token: return []
    url = f"https://api.github.com/repos/{repo}/contents/workorders"
    r = requests.get(url, headers={"Authorization": f"token {token}"})
    if r.status_code != 200: return []
    return [f["name"] for f in r.json() if f["name"].lower().endswith(".csv")]

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
# SAFE CSV LOADER
# ================================================
def load_csv_safely(data_bytes):
    if not data_bytes: return pd.DataFrame()
    text = data_bytes.decode("utf-8", errors="ignore")
    from io import StringIO
    for sep in [",", "\t", ";"]:
        for header in [0, None]:
            try:
                df = pd.read_csv(StringIO(text), sep=sep, header=header, on_bad_lines="skip", engine="python")
                if df.shape[0] > 1 and df.shape[1] > 1:
                    return df
            except:
                continue
    return pd.read_csv(StringIO(text), on_bad_lines="skip", engine="python")

# ================================================
# REQUIRED FUNCTION NAME — THIS IS THE ONE
# ================================================
def run_workorders_dashboard():
    st.set_page_config(page_title="PBB Work Orders", layout="wide")
    st.markdown("<h1 style='text-align:center;color:#8BC53F;'>Pioneer Broadband Work Orders</h1>", unsafe_allow_html=True)
    st.image("https://images.squarespace-cdn.com/content/v1/651eb4433b13e72c1034f375/369c5df0-5363-4827-b041-1add0367f447/PBB+long+logo.png?format=1500w", width=400, use_container_width=True)
    st.markdown("---")

    st.sidebar.header("Load File")
    mode = st.sidebar.radio("Source", ["Upload CSV", "Load from GitHub"])

    df = None
    if mode == "Upload CSV":
        uploaded = st.sidebar.file_uploader("Upload work orders", type="csv")
        if uploaded:
            df = load_csv_safely(uploaded.getvalue())
    else:
        files = list_github_files()
        if not files:
            st.error("No files in GitHub/workorders/"); st.stop()
        chosen = st.sidebar.selectbox("Select file", files)
        if st.sidebar.button("Load"):
            raw = download_file(chosen)
            if raw:
                df = load_csv_safely(raw)
            else:
                st.error("Download failed")

    if df is None or df.empty:
        st.info("Please upload or load a file.")
        st.stop()

    # Find technician column
    tech_idx = 0
    for i in range(df.shape[1]):
        if df.iloc[:10, i].astype(str).str.contains("cameron|callnan|tech", case=False, na=False).any():
            tech_idx = i
            break

    df["Technician"] = df.iloc[:, tech_idx].astype(str)
    df["Technician"] = df["Technician"].str.strip().str.title().str.replace(r"\s+", " ", regex=True)
    df["Technician"] = df["Technician"].replace({"Cameron Callan": "Cameron Callnan", "Cam Callnan": "Cameron Callnan"})

    # Find date column
    date_idx = next((i for i in range(df.shape[1]) if "date" in str(df.columns[i]).lower()), 1)
    df["Date"] = pd.to_datetime(df.iloc[:, date_idx], errors="coerce")
    df = df.dropna(subset=["Date"])

    # Filters
    start = st.date_input("Start", df["Date"].dt.date.min())
    end = st.date_input("End", df["Date"].dt.date.max())
    df = df[(df["Date"].dt.date >= start) & (df["Date"].dt.date <= end)]

    techs = sorted(df["Technician"].unique())
    selected = st.multiselect("Technicians", techs, default=techs)
    df = df[df["Technician"].isin(selected)]

    # KPIs
    total = len(df)
    tech_count = df["Technician"].nunique()
    c1, c2 = st.columns(2)
    c1.metric("Total Jobs", total)
    c2.metric("Technicians", tech_count)

    # Chart
    chart = df["Technician"].value_counts().reset_index()
    chart.columns = ["Technician", "Jobs"]
    fig = px.bar(chart, x="Technician", y="Jobs", text="Jobs", title="Jobs per Technician", template="plotly_dark")
    fig.update_traces(textposition="outside")
    st.plotly_chart(fig, use_container_width=True)

    # Debug
    with st.expander("Technicians Found"):
        st.write(sorted(df["Technician"].unique()))
        if "Cameron Callnan" in df["Technician"].values:
            st.success("Cameron Callnan is here!")

    st.success("Dashboard loaded!")

# ================================================
# DO NOT CHANGE THIS LINE
# ================================================
run_workorders_dashboard()
