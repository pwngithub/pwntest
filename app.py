
import streamlit as st
from dashboard import run_dashboard
from construction import run_construction
from workorders import run_workorders_dashboard
from prep import run_preps_dashboard
from tally_dashboard import run_tally_dashboard

st.set_page_config(page_title="Pioneer Dashboards", layout="wide")

st.sidebar.title("📊 Report Selector")
report = st.sidebar.selectbox("Select Report", ["Dashboard", "Construction", "Preps", "Tally"], index=0)

if report == "Dashboard":
    run_dashboard()
elif report == "Construction":
    run_construction()
elif report == "Preps":
    run_preps_dashboard()
elif report == "Tally":
    run_tally_dashboard()
