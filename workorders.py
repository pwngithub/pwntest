# filename: workorders.py
import streamlit as st
import pandas as pd
import plotly.express as px
import os
import requests
import base64
from datetime import datetime

# =================================================
# GITHUB HELPERS
# =================================================
def get_github_config():
    try:
        gh = st.secrets["github"]
        return gh["token"], gh["repo"], gh.get("branch", "main")
    except:
        st.warning("GitHub secrets not configured")
        return None, None, None

def list_github_files():
    token, repo, _ = get_github_config()
    if not token: return []
    url = f"https://api.github.com/repos/{repo}/contents/workorders"
    r = requests.get(url, headers={"Authorization": f"token {token}"})
    if r.status_code != 200: return []
    return [f["name"] for f in r.json() if f["name"].lower().endswith((".csv", ".txt"))]

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

# =================================================
# SUPER SAFE CSV LOADER
# =================================================
def load_csv_forever(bytes_data):
    if not bytes_data: return pd.DataFrame()
    text = bytes_data.decode("utf-8", errors="ignore")
    from io import StringIO
    for sep in [",", "\t", ";", "|"]:
        for header in [0, None]:
            for skip in range(0, 6):
                try:
                    df = pd.read_csv(StringIO(text), sep=sep, header=header, skiprows=skip,
                                     on_bad_lines="skip", engine="python")
                    if df.shape[0] > 1 and df.shape[1] > 1:
                        return df
                except:
                    continue
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    if not lines: return pd.DataFrame()
    data = [l.split(",") for l in lines]
    return pd.DataFrame(data[1:], columns=data[0] if len(data) > 1 else None)

# =================================================
# MAIN FUNCTION – THIS IS REQUIRED
# =================================================
def main():
    st.set_page_config(page_title="PBB Work Orders", layout="wide", initial_sidebar_state="expanded")
    st.markdown("<h1 style='text-align:center;color:#8BC53F;'>Pioneer Broadband Work Orders</h1>", unsafe_allow_html=True)
    st.image("https://images.squarespace-cdn.com/content/v1/651eb4433b13e72c1034f375/369c5df0-5363-4827-b041-1add0367f447/PBB+long+logo.png?format=1500w", width=400, use_container_width=True)
    st.markdown("---")

    st.sidebar.header("Load Work Orders File")
    mode = st.sidebar.radio("Source", ["Upload New CSV", "Load from GitHub"])

    df = None

    if mode == "Upload New CSV":
        uploaded = st.sidebar.file_uploader("Choose file", type=["csv", "txt"])
        if uploaded:
            df = load_csv_forever(uploaded.getvalue())
    else:
        files = list_github_files()
        if not files:
            st.error("No files in GitHub/workorders/ folder")
            st.stop()
        selected = st.sidebar.selectbox("Select file", files)
        if st.sidebar.button("Load File"):
            with st.spinner("Downloading..."):
                raw = download_file(selected)
                if raw:
                    df = load_csv_forever(raw)
                else:
                    st.error("Download failed")

    if df is None or df.empty:
        st.info("Please upload or load a file to continue.")
        st.stop()

    # Find technician column
    tech_col_idx = 0
    for i in range(df.shape[1]):
        sample = " ".join(df.iloc[:5, i].astype(str).str.lower())
        if any(k in sample for k in ["cameron", "callnan", "tech", "technician"]):
            tech_col_idx = i
            break

    df["Technician"] = df.iloc[:, tech_col_idx].astype(str)
    df["Technician"] = (
        df["Technician"]
        .str.strip()
        .str.title()
        .str.replace(r"\s+", " ", regex=True)
        .replace({"Cameron Callan": "Cameron Callnan", "Cam Callnan": "Cameron Callnan"})
    )

    # Find date column
    date_col_idx = 1
    for i in range(df.shape[1]):
        sample = " ".join(df.iloc[:5, i].astype(str))
        if any(x in sample.lower() for x in ["date", "2024", "2025"]):
            date_col_idx = i
            break

    df["Date"] = pd.to_datetime(df.iloc[:, date_col_idx], errors="coerce")
    df = df.dropna(subset=["Date"]).copy()
    if df.empty:
        st.error("No valid dates found.")
        st.stop()

    # Date range filter
    min_date = df["Date"].min().date()
    max_date = df["Date"].max().date()
    col1, col2 = st.columns(2)
    with col1:
        start = st.date_input("Start", min_date, min_value=min_date, max_value=max_date)
    with col2:
        end = st.date_input("End", max_date, min_value=min_date, max_value=max_date)

    df = df[(df["Date"].dt.date >= start) & (df["Date"].dt.date <= end)]

    # Tech filter
    techs = sorted(df["Technician"].dropna().unique())
    selected = st.multiselect("Technicians", techs, default=techs)
    df = df[df["Technician"].isin(selected)]

    # KPIs
    total = len(df)
    tech_count = df["Technician"].nunique()

    c1, c2, c3 = st.columns(3)
    c1.metric("Total Jobs", total)
    c2.metric("Technicians", tech_count)
    c3.metric("Avg per Tech", round(total/tech_count, 1) if tech_count else 0)

    # Chart
    st.markdown("### Jobs per Technician")
    chart = df["Technician"].value_counts().reset_index()
    chart.columns = ["Technician", "Jobs"]

    fig = px.bar(chart, x="Technician", y="Jobs", text="Jobs",
                 title="Total Jobs per Technician", template="plotly_dark", color="Technician")
    fig.update_traces(textposition="outside")
    st.plotly_chart(fig, use_container_width=True)

    # Debug
    with st.expander("DEBUG: Technicians Found", expanded=False):
        st.write(sorted(df["Technician"].unique()))
        st.write(f"Total: {tech_count}")
        if "Cameron Callnan" in df["Technician"].values:
            st.success("Cameron Callnan is visible!")
        else:
            st.warning("Cameron Callnan missing")

    st.success("Dashboard loaded successfully!")

# =================================================
# THIS IS THE CRITICAL LINE – MUST BE AT THE END
# =================================================
if __name__ == "__main__":
    main()
