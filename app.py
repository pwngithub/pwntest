import streamlit as st
from talley import run_talley
from construction import run_construction_dashboard as run_construction
from workorders import run_workorders_dashboard
from prep import run_preps_dashboard
from utils import fetch_jotform_data
from jotform_client import fetch_jotform_data as fetch_jotform_data_client

st.set_page_config(page_title="Pioneer Dashboards", layout="wide")

st.sidebar.title("📊 Report Selector")
report = st.sidebar.selectbox(
    "Select Report",
    ["Welcome", "Talley", "Construction", "Preps", "Work Orders"],
    index=0
)

st.sidebar.markdown("---")
st.sidebar.markdown("### Debug Info")

if report == "Welcome":
    st.title("Welcome to Pioneer Dashboard")
    st.write("Please select a report from the sidebar.")

elif report == "Talley":
    run_talley()

elif report == "Construction":
    run_construction()

elif report == "Preps":
    try:
        df = fetch_jotform_data_client(form_id="210823797836164")
        st.sidebar.success(f"Loaded Preps data: {df.shape[0]} rows")
        run_preps_dashboard(df)
    except Exception as e:
        st.sidebar.error(f"Failed to load data for Preps: {e}")
        st.error("Unable to load Preps dashboard.")

elif report == "Work Orders":
    run_workorders_dashboard()
