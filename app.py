import streamlit as st
import importlib
import traceback
import pandas as pd
import sys, os, importlib.util
import branding

# ----------------------------
# PAGE CONFIG
# ----------------------------
st.set_page_config(page_title="Pioneer Broadband Dashboard", layout="wide")

# ----------------------------
# SIDEBAR NAVIGATION
# ----------------------------
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

# ----------------------------
# MAIN APP LOGIC
# ----------------------------
try:
    branding.init_theme_state()
    branding.apply_theme()
    branding.render_header()

    if report == "Home":
        st.markdown(
            """
            <div style='text-align:center; margin-top:40px;'>
                <h1>Welcome to the Pioneer Broadband Dashboard</h1>
                <p style='font-size:18px;'>Select a report from the sidebar.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )

    elif report == "Tally":
        with st.spinner("Loading Pioneer Broadband Dashboard..."):
            try:
                import dashboard as dashboard
                dashboard.run_dashboard()
            except Exception as e:
                st.error("⚠️ Could not load Tally report:")
                st.exception(e)

    elif report == "Construction":
        with st.spinner("Loading Pioneer Broadband Dashboard..."):
            try:
                import construction as construction
                construction.run_construction_dashboard()
            except Exception as e:
                st.error("⚠️ Could not load Construction report:")
                st.exception(e)

    elif report == "Installs":
        with st.spinner("Loading Pioneer Broadband Dashboard..."):
            try:
                import install as install
                install.run_installs_dashboard()
            except Exception as e:
                st.error("⚠️ Could not load Installs report:")
                st.exception(e)

    elif report == "Splicing":
        with st.spinner("Loading Pioneer Broadband Dashboard..."):
            try:
                import splicing as splicing
                splicing.run_splicing_dashboard()
            except Exception as e:
                st.error("⚠️ Could not load Splicing report:")
                st.exception(e)

    elif report == "Preps":
        with st.spinner("Loading Pioneer Broadband Dashboard..."):
            try:
                import prep as prep
                prep.run_preps_dashboard()
            except Exception as e:
                st.error("⚠️ Could not load Preps report:")
                st.exception(e)

    elif report == "Work Orders":
        with st.spinner("Loading Pioneer Broadband Dashboard..."):
            try:
                import workorders as workorders
                workorders.run_workorders_dashboard()
            except Exception as e:
                st.error("⚠️ Could not load Work Orders report:")
                st.exception(e)

    elif report == "Accounting":
        with st.spinner("Loading Pioneer Broadband Dashboard..."):
            try:
                spec = importlib.util.spec_from_file_location("accounting", os.path.join(os.getcwd(), "accounting.py"))
                accounting = importlib.util.module_from_spec(spec)
                sys.modules["accounting"] = accounting
                spec.loader.exec_module(accounting)
            except Exception as e:
                st.error("⚠️ Could not load Accounting report:")
                st.exception(e)

    branding.render_footer()

except Exception as global_error:
    st.error("❌ A fatal error occurred while loading the app.")
    st.code(traceback.format_exc())
