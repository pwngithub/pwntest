import streamlit as st
import pandas as pd
import plotly.express as px
import os
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import requests
import base64

# =================================================
# GITHUB HELPERS (unchanged)
# =================================================
# ... [all your github helper functions stay exactly the same] ...
# (keeping them here for completeness but not re-typing to save space – use your existing ones)

# =================================================
# MAIN DASHBOARD
# =================================================

def run_workorders_dashboard():
    st.set_page_config(page_title="PBB Work Orders Dashboard", layout="wide", initial_sidebar_state="expanded")

    # CSS & Header (unchanged)
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
        custom_filename = st.sidebar.text_input("Enter filename to save (no extension):", key="wo_filename")
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
            st.error("No files in GitHub/workorders/"); st.stop()
        selected_file = st.sidebar.selectbox("Select Work Orders File", github_files, key="wo_select_github")
        if selected_file:
            local_path = download_github_workorder_file(selected_file)
            if local_path:
                df = pd.read_csv(local_path)

    if df is None:
        st.info("Upload or select a work orders file to continue.")
        st.stop()

    # =================================================
    # CRITICAL: TECHNICIAN NAME STANDARDIZATION (APPLY TO BOTH DATASETS)
    # =================================================
    def standardize_tech_name(series):
        return (series
                .astype(str)
                .str.strip()
                .str.replace(r"\s+", " ", regex=True)
                .str.title()
                .str.replace(r"\.$", "", regex=True)
                .str.replace(r"\s*\(.*\)$", "", regex=True)
                .replace({"Cameron Callan": "Cameron Callnan", "Cam Callnan": "Cameron Callnan"})
                )

    if "Techinician" in df.columns:
        df.rename(columns={"Techinician": "Technician"}, inplace=True)
    if "Technician" in df.columns:
        df["Technician"] = standardize_tech_name(df["Technician"])

    # =================================================
    # DATE HANDLING
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

    if df_filtered.empty:
        st.warning("No data in selected date range."); st.stop()

    # Tech & Work Type filters
    if "Technician" in df_filtered.columns and "Work Type" in df_filtered.columns:
        techs = sorted(df_filtered["Technician"].dropna().unique())
        wtypes = sorted(df_filtered["Work Type"].dropna().unique())
        col1, col2 = st.columns(2)
        with col1:
            selected_techs = st.multiselect("Technician(s)", techs, default=techs)
        with col2:
            selected_wtypes = st.multiselect("Work Type(s)", wtypes, default=wtypes)
        df_filtered = df_filtered[df_filtered["Technician"].isin(selected_techs) & df_filtered["Work Type"].isin(selected_wtypes)]

    required_cols = ['WO#', 'Duration', 'Technician', 'Work Type']
    if any(c not in df_filtered.columns for c in required_cols):
        st.error(f"Missing columns: {[c for c in required_cols if c not in df_filtered.columns]}"); st.stop()

    # =================================================
    # KPIs – NOW INCLUDES CAMERON
    # =================================================
    st.markdown("### Work Orders KPIs")
    kpi_data = df_filtered.dropna(subset=['WO#', 'Technician'])
    total_jobs = kpi_data["WO#"].nunique()
    tech_count = kpi_data["Technician"].nunique()        # ← This will now be 8
    avg_jobs = total_jobs / tech_count if tech_count else 0

    c1, c2, c3 = st.columns(3)
    c1.metric("Total Jobs", total_jobs)
    c2.metric("Tech Count", tech_count)                  # ← Cameron is now counted
    c3.metric("Avg Jobs per Tech", f"{avg_jobs:.1f}")

    # =================================================
    # CHARTS – CAMERON WILL NOW APPEAR
    # =================================================
    df_avg = df_filtered.copy()
    df_avg["Duration_Mins"] = pd.to_numeric(df_avg["Duration"].astype(str).str.extract(r"(\d+\.?\d*)")[0], errors="coerce")
    df_avg = df_avg.dropna(subset=["Duration_Mins"])

    if not df_avg.empty:
        grouped = (df_avg.groupby(["Technician", "Work Type"])
                   .agg(Total_Jobs=("WO#", "nunique"), Avg_Duration=("Duration_Mins", "mean"))
                   .reset_index())

        fig1 = px.bar(grouped, x="Work Type", y="Total_Jobs", color="Technician",
                      title="Jobs by Work Type & Technician", template="plotly_dark")
        fig2 = px.bar(grouped, x="Work Type", y="Avg_Duration", color="Technician",
                      title="Avg Duration by Work Type & Technician (mins)", template="plotly_dark")
        st.plotly_chart(fig1, use_container_width=True)
        st.plotly_chart(fig2, use_container_width=True)

    st.markdown("---")

    # =================================================
    # INSTALLATION REWORK – NOW MATCHES WORK ORDERS NAMES
    # =================================================
    st.markdown("<h2 style='color:#8BC53F;'>Installation Rework Analysis</h2>", unsafe_allow_html=True)

    re_mode = st.sidebar.radio("Installation Rework File", ["Upload New File", "Load Existing File"], key="re_mode")
    df_rework = None

    if re_mode == "Upload New File":
        file = st.sidebar.file_uploader("Upload Installation Assessment File", type=["csv","txt"], key="re_up")
        name = st.sidebar.text_input("Save as (no extension):", key="re_name")
        if file and name:
            bytes_data = file.getvalue()
            path = os.path.join(saved_folder, name.strip() + ".csv")
            with open(path, "wb") as f: f.write(bytes_data)
            upload_workorders_file_to_github(name.strip() + ".csv", bytes_data)
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
                vals = row.tolist()
                if len(vals) > 1 and str(vals[1]).startswith("Install"):
                    base = [vals[i] for i in [0,2,3,4] if i < len(vals)]
                else:
                    base = [vals[i] for i in [0,1,2,3] if i < len(vals)]
                while len(base) < 4: base.append(None)
                rows.append(base)

            df_re = pd.DataFrame(rows, columns=["Technician", "Total_Installations", "Rework", "Rework_Percentage"])

            # THIS IS THE KEY FIX – standardize names exactly the same way
            df_re["Technician"] = standardize_tech_name(df_re["Technician"])

            df_re["Total_Installations"] = pd.to_numeric(df_re["Total_Installations"], errors="coerce")
            df_re["Rework"] = pd.to_numeric(df_re["Rework"], errors="coerce")
            df_re["Rework_Percentage"] = pd.to_numeric(df_re["Rework_Percentage"].astype(str).str.replace(r"[^\d.]", "", regex=True), errors="coerce")
            df_re.dropna(subset=["Technician", "Total_Installations"], inplace=True)
            df_re = df_re.sort_values("Total_Installations", ascending=False)

            # Rework KPIs & Charts (Cameron now appears here too)
            total_i = df_re["Total_Installations"].sum()
            total_r = df_re["Rework"].sum()
            avg_p = df_re["Rework_Percentage"].mean()

            c1, c2, c3 = st.columns(3)
            c1.metric("Total Installations", int(total_i))
            c2.metric("Total Reworks", int(total_r))
            c3.metric("Avg Rework %", f"{avg_p:.1f}%")

            def color(val):
                if pd.isna(val): return ""
                return "background-color:#3CB371;color:white" if val < 5 else "background-color:#FFD700;color:black" if val < 10 else "background-color:#FF6347;color:white"

            styled = df_re.style.map(color, subset=["Rework_Percentage"]).format({"Rework_Percentage": "{:.1f}%", "Total_Installations": "{:.0f}", "Rework": "{:.0f}"})
            st.dataframe(styled, use_container_width=True)

            fig = make_subplots(specs=[[{"secondary_y": True}]])
            fig.add_trace(go.Bar(x=df_re["Technician"], y=df_re["Total_Installations"], name="Installs", marker_color="#00BFFF"), secondary_y=False)
            fig.add_trace(go.Scatter(x=df_re["Technician"], y=df_re["Rework_Percentage"], name="Rework %", mode="lines+markers", line=dict(color="#FF6347", width=3)), secondary_y=True)
            fig.add_hline(y=avg_p, line_dash="dash", line_color="cyan", annotation_text=f"Avg {avg_p:.1f}%", secondary_y=True)
            fig.update_layout(title="Technician Installations vs Rework %", template="plotly_dark")
            st.plotly_chart(fig, use_container_width=True)

            st.download_button("Download Rework Summary", df_re.to_csv(index=False).encode(), "rework_summary.csv", "text/csv")

        except Exception as e:
            st.error(f"Rework parsing error: {e}")

    # Optional debug (remove once confirmed working)
    with st.expander("Debug – Current Technician Names", expanded=False):
        st.write("Work Orders Techs:", sorted(df["Technician"].unique()))
        if 'df_re' in locals():
            st.write("Rework Techs:", sorted(df_re["Technician"].unique()))

if __name__ == "__main__":
    run_workorders_dashboard()
