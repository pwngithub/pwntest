import streamlit as st
from dashboard import run_dashboard
from tally_dashboard import run_tally_dashboard
from construction import run_construction_dashboard
from workorders import run_workorders_dashboard
from accounting import run_accounting_dashboard
from projects import run_projects_dashboard
from network import run_network_dashboard
from jotform_client import fetch_jotform_data
from prep import run_preps_dashboard

# -------------------------------
# APP CONFIGURATION
# -------------------------------
st.set_page_config(page_title="Pioneer Broadband Dashboard", page_icon="📊", layout="wide")

st.sidebar.title("📊 Reports")
report = st.sidebar.selectbox(
    "Select Report",
    [
        "Dashboard",
        "Tally",
        "Construction",
        "Work Orders",
        "Preps",
        "Accounting",
        "Projects",
        "Network",
    ],
)

# -------------------------------
# REPORT ROUTER
# -------------------------------
try:
    if report == "Dashboard":
        run_dashboard()

    elif report == "Tally":
        run_tally_dashboard()

    elif report == "Construction":
        run_construction_dashboard()

    elif report == "Work Orders":
        run_workorders_dashboard()

    elif report == "Preps":
        try:
            df = fetch_jotform_data(
                form_id="232136783361054",
                api_key="32c62a1b6c1a350caed2f989c1be4e48"
            )
            st.sidebar.success(f"✅ Loaded Preps data: {df.shape[0]} rows")
            run_preps_dashboard()
        except Exception as e:
            st.sidebar.error(f"⚠️ Failed to load data for Preps: {e}")
            st.error("Unable to load Preps dashboard.")

    elif report == "Accounting":
        run_accounting_dashboard()

    elif report == "Projects":
        run_projects_dashboard()

    elif report == "Network":
        run_network_dashboard()

except Exception as e:
    st.error(f"Could not load {report} report: {e}")
