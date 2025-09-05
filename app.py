
import streamlit as st
from dashboard import run_dashboard
from construction import run_construction_dashboard as run_construction
from workorders import run_workorders_dashboard
from prep import run_preps_dashboard
from tally_dashboard import run as run_tally_dashboard
from utils import fetch_jotform_data

st.set_page_config(page_title="Pioneer Dashboards", layout="wide")

st.sidebar.title("📊 Report Selector")
report = st.sidebar.selectbox("Select Report", ["Welcome", "Construction", "Preps", "Tally"], index=0)

st.sidebar.markdown("---")
st.sidebar.markdown("### Debug Info")

if report == "Welcome":
    st.title("Welcome to Pioneer Dashboard")
    st.write("Please select a report from the sidebar.")

elif report == "Construction":
    run_construction()

elif report == "Preps":
    try:
        df = fetch_jotform_data(form_id="232136783361054", api_key="32c62a1b6c1a350caed2f989c1be4e48")
        st.sidebar.success(f"Loaded Preps data: {df.shape[0]} rows")
        run_preps_dashboard()
    except Exception as e:
        st.sidebar.error(f"Failed to load data for Preps: {e}")
        st.error("Unable to load Preps dashboard.")

elif report == "Tally":
    try:
        df = fetch_jotform_data(form_id="231867872328063", api_key="32c62a1b6c1a350caed2f989c1be4e48")
        st.sidebar.success(f"Loaded Tally data: {df.shape[0]} rows")
        run_tally_dashboard(df)
    except Exception as e:
        st.sidebar.error(f"Failed to load data for Tally: {e}")
        st.error("Unable to load Tally dashboard.")
