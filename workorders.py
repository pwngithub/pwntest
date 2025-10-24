import streamlit as st
import pandas as pd
import plotly.express as px
import os
import plotly.graph_objects as go
from plotly.subplots import make_subplots

def run_workorders_dashboard():
    st.set_page_config(
        page_title="PBB Work Orders Dashboard",
        layout="wide",
        initial_sidebar_state="expanded"
    )

    # --- Custom CSS ---
    st.markdown("""
    <style>
    .stApp {background-color: #0E1117;}
    div[data-testid="metric-container"] {
        background-color: #262730;
        border: 1px solid #3c3c3c;
        padding: 15px;
        border-radius: 10px;
        box-shadow: 0 4px 8px rgba(0,0,0,0.4);
        transition: transform 0.2s;
        color: #FAFAFA;
    }
    div[data-testid="metric-container"]:hover {
        transform: scale(1.05);
        border-color: #8BC53F;
    }
    div[data-testid="metric-container"] > label {color: #A0A0A0;}
    .logo-container {text-align:center;margin-bottom:20px;}
    .main-title {color:#FFFFFF;text-align:center;font-weight:bold;}
    </style>
    """, unsafe_allow_html=True)

    # --- Logo + Title ---
    st.markdown("""
    <div class='logo-container'>
        <img src='https://images.squarespace-cdn.com/content/v1/651eb4433b13e72c1034f375/
        369c5df0-5363-4827-b041-1add0367f447/PBB+long+logo.png?format=1500w' width='400'>
    </div>
    """, unsafe_allow_html=True)
    st.markdown("<h1 class='main-title'>🛠 Pioneer Broadband Work Orders Dashboard</h1>", unsafe_allow_html=True)
    st.markdown("<hr>", unsafe_allow_html=True)

    # =================================================
    # SECTION 1: WORK ORDERS FILE MANAGEMENT
    # =================================================
    st.sidebar.header("📁 Work Orders File")
    saved_folder = "saved_uploads"
    os.makedirs(saved_folder, exist_ok=True)

    mode = st.sidebar.radio("Select Mode", ["Upload New Work Orders File", "Load Existing Work Orders File"], key="wo_mode")
    df = None

    if mode == "Upload New Work Orders File":
        uploaded_file = st.sidebar.file_uploader("Upload Work Orders CSV", type=["csv"])
        custom_filename = st.sidebar.text_input("Enter filename to save (no extension):", key="wo_filename")

        if uploaded_file and custom_filename:
            save_path = os.path.join(saved_folder, custom_filename + ".csv")
            with open(save_path, "wb") as f:
                f.write(uploaded_file.getbuffer())
            st.sidebar.success(f"File saved as: {custom_filename}.csv")
            df = pd.read_csv(save_path)
        elif uploaded_file:
            st.sidebar.warning("Please enter a file name to save.")
    else:
        saved_files = [f for f in os.listdir(saved_folder) if f.endswith(".csv")]
        if not saved_files:
            st.warning("No saved files found. Please upload one first.")
            st.stop()
        selected_file = st.sidebar.selectbox("Select a saved file", saved_files, key="wo_select")
        if selected_file:
            df = pd.read_csv(os.path.join(saved_folder, selected_file))
        if st.sidebar.button("🗑 Delete Selected Work Orders File"):
            os.remove(os.path.join(saved_folder, selected_file))
            st.sidebar.success(f"Deleted {selected_file}")
            st.rerun() # Use st.rerun() for modern Streamlit

    if df is None:
        st.info("Please upload or load a Work Orders file to begin.")
        st.stop()

    # --- Data Cleaning and Preparation ---
    date_cols = [col for col in df.columns if str(col).lower() in ["date when", "date", "work date", "completed", "completion date"]]
    if not date_cols:
        st.error("No date column found. Please include a 'Date When', 'Date', or 'Completed' column in your CSV.")
        st.stop()

    date_col = date_cols[0]
    df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
    df = df.dropna(subset=[date_col])
    df["Day"] = df[date_col].dt.date

    if "Techinician" in df.columns and "Technician" not in df.columns:
        df.rename(columns={"Techinician": "Technician"}, inplace=True)

    min_day, max_day = df["Day"].min(), df["Day"].max()

    # --- Filters ---
    st.subheader("F I L T E R S")
    start_date, end_date = st.date_input("📅 Date Range", [min_day, max_day], min_value=min_day, max_value=max_day)
    df_filtered = df[(df["Day"] >= start_date) & (df["Day"] <= end_date)]

    if not df_filtered.empty:
        techs = sorted(df_filtered["Technician"].unique())
        work_types = sorted(df_filtered["Work Type"].unique())
        col1, col2 = st.columns(2)
        with col1:
            selected_techs = st.multiselect("👨‍🔧 Select Technician(s)", techs, default=techs)
        with col2:
            selected_work_types = st.multiselect("📋 Select Work Type(s)", work_types, default=work_types)
        df_filtered = df_filtered[df_filtered["Technician"].isin(selected_techs) & df_filtered["Work Type"].isin(selected_work_types)]

    if df_filtered.empty:
        st.warning("No data available for the selected filters.")
        st.stop()

    # =====================================================
    # SECTION 2: KPIs (DIAGNOSTIC TEST)
    # =====================================================
    st.markdown("### 📌 Work Orders KPIs")
    st.success("--- KPI SECTION IS RUNNING ---") # <-- THIS IS THE TEST MESSAGE

    # The original KPI code is temporarily disabled for our test.
    # We will restore it after this test is successful.

    # =====================================================
    # SECTION 3: CHARTS
    # =====================================================
    try:
        grouped_overall = (
            df_filtered.groupby(["Technician", "Work Type"])
            .agg(Total_Jobs=("WO#", "nunique"),
                 Average_Duration=("Duration", lambda x: pd.to_numeric(x.str.extract(r"(\d+\.?\d*)")[0], errors="coerce").mean()))
            .reset_index()
        )

        st.subheader("📊 Work Orders Charts")
        fig1 = px.bar(grouped_overall, x="Work Type", y="Total_Jobs",
                      color="Technician", title="Jobs by Work Type & Technician", template="plotly_dark")
        st.plotly_chart(fig1, use_container_width=True)

        fig2 = px.bar(grouped_overall, x="Work Type", y="Average_Duration",
                      color="Technician", title="Avg Duration by Work Type & Technician", template="plotly_dark")
        st.plotly_chart(fig2, use_container_width=True)
    except Exception as e:
        st.error(f"An error occurred while creating charts: {e}")

    st.markdown("---")

    # =====================================================
    # SECTION 4: INSTALLATION REWORK ANALYSIS
    # =====================================================
    st.markdown("<h2 style='color:#8BC53F;'>🔁 Installation Rework Analysis</h2>", unsafe_allow_html=True)
    re_mode = st.sidebar.radio("Select Mode for Installation Rework File", ["Upload New File", "Load Existing File"], key="re_mode")
    df_rework = None

    if re_mode == "Upload New File":
        re_file = st.sidebar.file_uploader("Upload Installation Assessment File (CSV or TXT)", type=["csv", "txt"])
        re_filename = st.sidebar.text_input("Enter name to save (no extension):", key="re_filename")

        if re_file and re_filename:
            save_path = os.path.join(saved_folder, re_filename + ".csv")
            with open(save_path, "wb") as f:
                f.write(re_file.getbuffer())
            st.sidebar.success(f"File saved as: {re_filename}.csv")
            df_rework = pd.read_csv(save_path, header=None)
        elif re_file:
            st.sidebar.warning("Please enter a file name to save.")
    else:
        saved_files = [f for f in os.listdir(saved_folder) if f.endswith(".csv")]
        if saved_files:
            selected_re_file = st.sidebar.selectbox("Select saved file", saved_files, key="re_select")
            if selected_re_file:
                df_rework = pd.read_csv(os.path.join(saved_folder, selected_re_file), header=None)
        else:
            st.sidebar.warning("No saved files found for Installation Rework.")

    if df_rework is not None and not df_rework.empty:
        try:
            # (Rework parsing code is unchanged)
            parsed_rows = []
            for _, row in df_rework.iterrows():
                values = row.tolist()
                if len(values) > 1 and str(values[1]).startswith("Install"):
                    base_subset = [values[i] for i in [0, 2, 3, 4] if i < len(values)]
                else:
                    base_subset = [values[i] for i in [0, 1, 2, 3] if i < len(values)]
                while len(base_subset) < 4:
                    base_subset.append(None)
                parsed_rows.append(base_subset)

            df_combined = pd.DataFrame(parsed_rows, columns=["Technician", "Total_Installations", "Rework", "Rework_Percentage"])
            df_combined["Technician"] = df_combined["Technician"].astype(str).str.replace('"', '').str.strip()
            df_combined["Total_Installations"] = pd.to_numeric(df_combined["Total_Installations"], errors="coerce")
            df_combined["Rework"] = pd.to_numeric(df_combined["Rework"], errors="coerce")
            df_combined["Rework_Percentage"] = (df_combined["Rework_Percentage"].astype(str).str.replace("%", "").str.replace('"', "").str.strip())
            df_combined["Rework_Percentage"] = pd.to_numeric(df_combined["Rework_Percentage"], errors="coerce")
            df_combined.dropna(subset=["Technician", "Total_Installations"], inplace=True)
            df_combined = df_combined.sort_values("Total_Installations", ascending=False)

            st.markdown("### 📌 Installation Rework KPIs")
            total_jobs_rw = df_combined["Total_Installations"].sum()
            total_repeats = df_combined["Rework"].sum()
            avg_repeat_pct = df_combined["Rework_Percentage"].mean()

            c1, c2, c3 = st.columns(3)
            c1.metric("🏗️ Total Installations", int(total_jobs_rw))
            c2.metric("🔁 Total Reworks", int(total_repeats))
            c3.metric("📈 Avg Rework %", f"{avg_repeat_pct:.1f}%")

            st.markdown("### 🧾 Installation Rework Summary Table (Visualized)")
            def color_rework(val):
                if pd.isna(val): return ''
                elif val < 5: return 'background-color: #3CB371; color: white;'
                elif val < 10: return 'background-color: #FFD700; color: black;'
                else: return 'background-color: #FF6347; color: white;'

            # --- FIX for DeprecationWarning ---
            # Changed .applymap to .map
            styled_table = (df_combined.style.map(color_rework, subset=['Rework_Percentage']).format({'Rework_Percentage': '{:.1f}%', 'Total_Installations': '{:.0f}', 'Rework': '{:.0f}'}))
            
            # --- FIX for DeprecationWarning ---
            # Removed use_container_width from st.dataframe
            st.dataframe(styled_table)

            st.markdown("### 📊 Installations (Bars) vs Rework % (Line)")
            fig_combo = make_subplots(specs=[[{"secondary_y": True}]])
            fig_combo.add_trace(go.Bar(x=df_combined["Technician"], y=df_combined["Total_Installations"], name="Total Installations", marker_color="#00BFFF"), secondary_y=False)
            fig_combo.add_trace(go.Scatter(x=df_combined["Technician"], y=df_combined["Rework_Percentage"], name="Rework %", mode="lines+markers", line=dict(color="#FF6347", width=3)), secondary_y=True)
            fig_combo.add_hline(y=avg_repeat_pct, line_dash="dash", line_color="cyan", annotation_text=f"Avg Rework % ({avg_repeat_pct:.1f}%)", annotation_font_color="cyan", secondary_y=True)
            fig_combo.update_layout(title_text="Technician Total Installations vs Rework %", template="plotly_dark", xaxis_title="Technician", yaxis_title="Total Installations", legend=dict(x=0.01, y=0.99, bgcolor="rgba(0,0,0,0)"), bargap=0.25)
            fig_combo.update_yaxes(title_text="Total Installations", secondary_y=False)
            fig_combo.update_yaxes(title_text="Rework %", secondary_y=True)
            st.plotly_chart(fig_combo, use_container_width=True)

            csv_rework = df_combined.to_csv(index=False).encode("utf-8")
            st.download_button("⬇️ Download Installation Rework Summary CSV", data=csv_rework, file_name="installation_rework_summary.csv", mime="text/csv")

        except Exception as e:
            st.error(f"Error parsing installation rework file: {e}")

if __name__ == "__main__":
    run_workorders_dashboard()
