import streamlit as st
import importlib
import traceback
import pandas as pd

st.set_page_config(page_title="Pioneer Dashboard", layout="wide")

st.sidebar.title("📊 Reports")
report = st.sidebar.selectbox(
    "Select a Report",
    [
        "Home",
        "Tally",
        "Construction",
        "Installs",
        "Splicing",
        "Preps",
        "Work Orders",
        "Accounting"
    ]
)

try:
    if report == "Home":
        st.markdown(
            "<div style='text-align:center;'><img src='https://images.squarespace-cdn.com/content/v1/651eb4433b13e72c1034f375/369c5df0-5363-4827-b041-1add0367f447/PBB+long+logo.png?format=1500w' width='500'></div>",
            unsafe_allow_html=True
        )
        st.title("Welcome to Pioneer Dashboard")
        st.write("Use the sidebar to open a report.")

    elif report == "Tally":
        try:
            import tally_dashboard as tally_dashboard
            df = pd.DataFrame()
            tally_dashboard.run(df)
        except Exception as e:
            st.error("⚠️ Could not load Tally report:")
            st.exception(e)

    elif report == "Construction":
        try:
            import construction as construction
            construction.run_construction_dashboard()
        except Exception as e:
            st.error("⚠️ Could not load Construction report:")
            st.exception(e)

    elif report == "Installs":
        try:
            import install as install
            install.run_installs_dashboard()
        except Exception as e:
            st.error("⚠️ Could not load Installs report:")
            st.exception(e)

    elif report == "Splicing":
        try:
            import splicing as splicing
            splicing.run_splicing_dashboard()
        except Exception as e:
            st.error("⚠️ Could not load Splicing report:")
            st.exception(e)

    elif report == "Preps":
        try:
            import prep as prep
            prep.run_preps_dashboard()
        except Exception as e:
            st.error("⚠️ Could not load Preps report:")
            st.exception(e)

    elif report == "Work Orders":
        try:
            import workorders as workorders
            workorders.run_workorders_dashboard()
        except Exception as e:
            st.error("⚠️ Could not load Work Orders report:")
            st.exception(e)

    elif report == "Accounting":
    try:
        import importlib.util, sys, os
        spec = importlib.util.spec_from_file_location("accounting", os.path.join(os.getcwd(), "accounting.py"))
        accounting = importlib.util.module_from_spec(spec)
        sys.modules["accounting"] = accounting
        spec.loader.exec_module(accounting)
    except Exception as e:
        st.error("⚠️ Could not load Accounting report:")
        st.exception(e)


except Exception as global_error:
    st.error("❌ A fatal error occurred while loading the app.")
    st.code(traceback.format_exc())
