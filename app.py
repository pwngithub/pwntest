
import streamlit as st
from dashboard import run_dashboard
from construction import run_construction
from workorders import run_workorders_dashboard
from tally_dashboard import run as run_tally
from utils import fetch_jotform_data

st.set_page_config(page_title="PWNTEST Dashboard", layout="wide")
report = st.sidebar.selectbox("Select Report", ["Dashboard", "Construction", "Work Orders", "Tally", "Preps"])

if report == "Dashboard":
    run_dashboard()
elif report == "Construction":
    run_construction()
elif report == "Work Orders":
    run_workorders_dashboard()
elif report == "Tally":
    try:
        form_id = "251684170301146"
        df = fetch_jotform_data(form_id)
        if df is not None:
            run_tally(df)
        else:
            st.error("Failed to load data for Tally.")
    except Exception as e:
        st.exception(e)
elif report == "Preps":
    try:
        form_id = "251721096441149"
        df = fetch_jotform_data(form_id)
        if df is not None:
            import prep
            prep.run(df)
        else:
            st.error("Failed to load data for Preps.")
    except Exception as e:
        st.exception(e)
