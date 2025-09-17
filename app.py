
import streamlit as st
from dashboard import run_dashboard
from construction import run_construction_dashboard
from workorders import run_workorders_dashboard
from prep import run_prep_dashboard

st.set_page_config(page_title="Pioneer Dashboard", layout="wide")

st.title("📊 Pioneer Broadband Dashboard")

report_options = {
    "Tally": run_dashboard,
    "Construction": run_construction_dashboard,
    "Work Orders": run_workorders_dashboard,
    "Preps": run_prep_dashboard
}

report_choice = st.sidebar.selectbox("Select Report", ["Welcome"] + list(report_options.keys()))

if report_choice == "Welcome":
    st.markdown("## 👋 Welcome to the Pioneer Dashboard!")
    st.markdown("Use the sidebar to select a report.")
else:
    run_func = report_options[report_choice]
    run_func()
