# workorders.py — FINAL + NEW "Overall Avg Time per Work Type" GRAPH ADDED
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import requests
import base64
from io import BytesIO

# ================================================
# GITHUB HELPERS (unchanged)
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
    headers = {"Authorization": f"token {token}"}
    r = requests.get(url, headers=headers)
    if r.status_code != 200: return []
    return [f["name"] for f in r.json() if f["name"].lower().endswith((".csv", ".txt"))]

def download_file_bytes(filename):
    token, repo, _ = get_github_config()
    if not token: return None
    url = f"https://api.github.com/repos/{repo}/contents/workorders/{filename}"
    headers = {"Authorization": f"token {token}"}
    r = requests.get(url, headers=headers)
    if r.status_code != 200: return None
    data = r.json()
    if "content" in data and data["content"]:
        return base64.b64decode(data["content"])
    if "download_url" in data:
        return requests.get(data["download_url"]).content
    return None

# ================================================
# MAIN APP — NOW WITH NEW GRAPH!
# ================================================
def run_workorders_dashboard():
    st.set_page_config(page_title="PBB Work Orders", layout="wide", initial_sidebar_state="expanded")

    st.markdown("<h1 style='text-align:center;color:#8BC53F;'>Pioneer Broadband Work Orders Dashboard</h1>", unsafe_allow_html=True)
    st.markdown("<div style='text-align:center;margin-bottom:30px;'><img src='https://images.squarespace-cdn.com/content/v1/651eb4433b13e72c1034f375/369c5df0-5363-4827-b041-1add0367f447/PBB+long+logo.png?format=1500w' width='400'></div>", unsafe_allow_html=True)

    if "df_main" not in st.session_state: st.session_state.df_main = None
    if "df_rework" not in st.session_state: st.session_state.df_rework = None

    # ================================================
    # WORK ORDERS LOADING
    # ================================================
    st.sidebar.header("Work Orders File")
    wo_source = st.sidebar.radio("Source", ["Upload New", "Load from GitHub"], key="wo_source_radio")

    if wo_source == "Upload New":
        uploaded = st.sidebar.file_uploader("Upload Work Orders CSV", type="csv", key="wo_upload")
        if uploaded:
            st.session_state.df_main = pd.read_csv(uploaded)
            st.success("Work Orders loaded!")
            st.rerun()
    else:
        files = list_github_files()
        if not files:
            st.sidebar.error("No files found")
        else:
            sel = st.sidebar.selectbox("Select file", files, key="wo_select")
            if st.sidebar.button("Load Work Orders", key="load_wo"):
                raw = download_file_bytes(sel)
                if raw:
                    st.session_state.df_main = pd.read_csv(BytesIO(raw))
                    st.success(f"{sel} loaded!")
                    st.rerun()

    if st.session_state.df_main is None:
        st.info("Please load a Work Orders file.")
        st.stop()

    df = st.session_state.df_main.copy()

    # Fix names
    if "Techinician" in df.columns:
        df.rename(columns={"Techinician": "Technician"}, inplace=True)
    if "Technician" in df.columns:
        df["Technician"] = df["Technician"].astype(str).str.strip().str.strip().str.title()
        df["Technician"] = df["Technician"].replace({"Cameron Callan": "Cameron Callnan", "Cam Callnan": "Cameron Callnan"}, regex=True)

    # Date
    date_col = next((c for c in df.columns if "date" in str(c).lower()), None)
    if not date_col:
        st.error("No date column found")
        st.stop()
    df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
    df = df.dropna(subset=[date_col]).copy()
    df["Day"] = df[date_col].dt.date

    # Filters
    start_date, end_date = st.date_input("Date Range", [df["Day"].min(), df["Day"].max()], key="date_range")
    df = df[(df["Day"] >= start_date) & (df["Day"] <= end_date)]

    techs = sorted(df["Technician"].dropna().unique())
    selected_techs = st.multiselect("Technicians", techs, default=techs, key="tech_filter")
    df = df[df["Technician"].isin(selected_techs)]

    if "Work Type" in df.columns:
        types = sorted(df["Work Type"].dropna().unique())
        selected_types = st.multiselect("Work Types", types, default=types, key="type_filter")
        df = df[df["Work Type"].isin(selected_types)]

    # KPIs
    st.markdown("### Work Orders KPIs")
    total_jobs = df["WO#"].nunique() if "WO#" in df.columns else len(df)
    tech_count = df["Technician"].nunique()
    avg_jobs = round(total_jobs / tech_count, 1) if tech_count > 0 else 0

    c1, c2, c3 = st.columns(3)
    c1.metric("Total Jobs Completed", total_jobs)
    c2.metric("Active Technicians", tech_count)
    c3.metric("Avg Jobs per Tech", avg_jobs)

    # ================================================
    # EXISTING AVERAGE VISUALS (per tech + work type)
    # ================================================
    st.markdown("### Technician Performance by Work Type")

    if "Duration" in df.columns and "Work Type" in df.columns:
        df["Mins"] = pd.to_numeric(df["Duration"].astype(str).str.extract(r"(\d+\.?\d*)")[0], errors="coerce")

        summary = df.groupby(["Technician", "Work Type"], as_index=False).agg(
            Jobs=("WO#", "nunique"),
            Avg_Duration=("Mins", "mean")
        ).round(1)

        col1, col2 = st.columns(2)
        with col1:
            fig1 = px.bar(summary, x="Work Type", y="Jobs", color="Technician",
                          title="Jobs Completed by Work Type", template="plotly_dark")
            st.plotly_chart(fig1, use_container_width=True)
        with col2:
            fig2 = px.bar(summary, x="Work Type", y="Avg_Duration", color="Technician",
                          title="Avg Duration per Job (minutes)", template="plotly_dark")
            st.plotly_chart(fig2, use_container_width=True)

    st.markdown("---")

    # ================================================
    # NEW GRAPH: OVERALL AVERAGE TIME PER WORK TYPE (ALL TECHS COMBINED)
    # ================================================
    st.markdown("### Overall Average Time per Work Type (All Technicians)")

    if "Duration" in df.columns and "Work Type" in df.columns and not df["Mins"].isna().all():
        overall_avg = df.groupby("Work Type", as_index=False)["Mins"].mean().round(1)
        overall_avg = overall_avg.sort_values("Mins", ascending=True)  # Nicer horizontal view

        fig_overall = go.Figure()
        fig_overall.add_trace(go.Bar(
            y=overall_avg["Work Type"],
            x=overall_avg["Mins"],
            orientation='h',
            marker_color="#8BC53F",
            text=overall_avg["Mins"].astype(str) + " min",
            textposition='outside',
            hovertemplate="<b>%{y}</b><br>Avg Time: %{x} minutes<extra></extra>"
        ))

        fig_overall.update_layout(
            title="Average Time to Complete Each Work Type",
            xaxis_title="Average Duration (minutes)",
            yaxis_title="Work Type",
            template="plotly_dark",
            height=400 + len(overall_avg) * 30,
            margin=dict(l=150)
        )
        st.plotly_chart(fig_overall, use_container_width=True)
    else:
        st.info("No duration data available for average time calculation.")

    st.markdown("---")

    # ================================================
    # REWORK — STILL PERFECT
    # ================================================
    st.markdown("<h2 style='color:#8BC53F;'>Installation Rework Analysis</h2>", unsafe_allow_html=True)

    re_mode = st.sidebar.radio("Rework File", ["Upload New File", "Load from GitHub"], key="re_source_radio")

    if re_mode == "Upload New File":
        re_up = st.sidebar.file_uploader("Upload Rework File", type=["csv","txt"], key="re_upload")
        if re_up:
            st.session_state.df_rework = pd.read_csv(re_up, header=None, dtype=str, on_bad_lines="skip")
            st.success("Rework uploaded!")
            st.rerun()
    else:
        files = list_github_files()
        if files:
            sel = st.sidebar.selectbox("Select Rework File", files, key="re_select")
            if st.sidebar.button("Load Rework File", key="load_re"):
                raw = download_file_bytes(sel)
                if raw:
                    st.session_state.df_rework = pd.read_csv(BytesIO(raw), header=None, dtype=str, on_bad_lines="skip")
                    st.success("Rework loaded!")
                    st.rerun()

    if st.session_state.df_rework is not None:
        try:
            df_rework = st.session_state.df_rework
            parsed = []
            for _, row in df_rework.iterrows():
                v = row.tolist()
                if len(v) > 1 and str(v[1]).strip().lower().startswith("install"):
                    base = [v[i] for i in [0,2,3,4] if i < len(v)]
                else:
                    base = [v[i] for i in [0,1,2,3] if i < len(v)]
                while len(base) < 4:
                    base.append(None)
                parsed.append(base)

            dfc = pd.DataFrame(parsed, columns=["Technician", "Total_Installations", "Rework", "Rework_Percentage"])
            dfc["Technician"] = dfc["Technician"].astype(str).str.replace('"','').str.strip()
            dfc["Total_Installations"] = pd.to_numeric(dfc["Total_Installations"], errors="coerce")
            dfc["Rework"] = pd.to_numeric(dfc["Rework"], errors="coerce")
            dfc["Rework_Percentage"] = pd.to_numeric(dfc["Rework_Percentage"].astype(str).str.replace("%","").str.replace('"',''), errors="coerce")
            dfc.dropna(subset=["Technician", "Total_Installations"], inplace=True)
            dfc.sort_values("Total_Installations", ascending=False, inplace=True)
            dfc["Technician"] = dfc["Technician"].replace({"Cameron Callan": "Cameron Callnan", "Cam Callnan": "Cameron Callnan"}, regex=True)

            total_i = dfc["Total_Installations"].sum()
            total_r = dfc["Rework"].sum()
            avg_p = dfc["Rework_Percentage"].mean()

            c1, c2, c3 = st.columns(3)
            c1.metric("Total Installations", int(total_i))
            c2.metric("Total Reworks", int(total_r))
            c3.metric("Avg Rework %", f"{avg_p:.1f}%")

            fig = make_subplots(specs=[[{"secondary_y": True}]])
            fig.add_trace(go.Bar(x=dfc["Technician"], y=dfc["Total_Installations"], name="Installs", marker_color="#00BFFF"), secondary_y=False)
            fig.add_trace(go.Scatter(x=dfc["Technician"], y=dfc["Rework_Percentage"], name="Rework %", mode="lines+markers", line=dict(color="#FF6347", width=3)), secondary_y=True)
            fig.add_hline(y=avg_p, line_dash="dash", line_color="cyan", annotation_text=f"Avg {avg_p:.1f}%", secondary_y=True)
            fig.update_layout(title="Installations vs Rework %", template="plotly_dark")
            st.plotly_chart(fig, use_container_width=True)

            def color(val):
                if pd.isna(val): return ""
                return "background-color:#3CB371;color:white;" if val < 5 else "background-color:#FFD700;color:black;" if val < 10 else "background-color:#FF6347;color:white;"

            styled = dfc.style.map(color, subset=["Rework_Percentage"]).format({"Rework_Percentage": "{:.1f}%"})
            st.dataframe(styled, use_container_width=True)

        except Exception as e:
            st.error(f"Rework error: {e}")

# ================================================
# RUN
# ================================================
run_workorders_dashboard()
