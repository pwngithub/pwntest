
import streamlit as st
import branding
# -------------------------------
# Sidebar: Report Selector
# -------------------------------
st.sidebar.title("📊 Reports")
report = st.sidebar.selectbox(
    "Select Report",
    [
        "Dashboard",
        "Work Orders",
        "Construction",
        "Tally",
        "Install",
        "Splicing",
        "Accounting",
        "Projects"  # ✅ Added new Projects report
    ]
)

# -------------------------------
# Report Loader
# -------------------------------
try:
    if report == "Dashboard":
        import dashboard
        dashboard.run_dashboard()

    elif report == "Work Orders":
        import workorders
        workorders.run_workorders_dashboard()

    elif report == "Construction":
        import construction
        construction.run_construction_dashboard()

    elif report == "Tally":
        import dashboard
        dashboard.run_dashboard()

    elif report == "Install":
        import install
        install.run_install_dashboard()

    elif report == "Splicing":
        import splicing
        splicing.run_splicing_dashboard()

    elif report == "Accounting":
        import accounting
        accounting.run_accounting_dashboard()

    elif report == "Projects":
        import projects  # ✅ New Projects dashboard (standalone)

except Exception as e:
    st.error(f"Could not load {report} report: {e}")
