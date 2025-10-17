
import streamlit as st
import branding
# -------------------------------
# Sidebar: Report Selector
# -------------------------------
st.sidebar.title("📊 Reports")
report = st.sidebar.selectbox(
    "Select Report",
    [
        "Welcome",        # Default page
        "Work Orders",
        "Construction",
        "Tally",
        "Install",
        "Splicing",
        "Accounting",
        "Projects"
    ],
    index=0
)

# -------------------------------
# Report Loader
# -------------------------------
try:
    if report == "Welcome":
        st.markdown("""
            <div style="text-align:center; padding:80px 20px;">
                <h1 style="color:#003865;">Welcome to the Pioneer Broadband Dashboard</h1>
                <p style="font-size:18px;">Select a report from the sidebar to begin exploring your operational data.</p>
                <br>
                <img src="https://images.squarespace-cdn.com/content/v1/651eb4433b13e72c1034f375/369c5df0-5363-4827-b041-1add0367f447/PBB+long+logo.png?format=1500w" width="400">
            </div>
        """, unsafe_allow_html=True)

    elif report == "Work Orders":
        import workorders
        workorders.run_workorders_dashboard()

    elif report == "Construction":
        import construction
        construction.run_construction_dashboard()

    elif report == "Tally":
        import tally_dashboard
        tally_dashboard.run_tally_dashboard()

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
        import projects

except Exception as e:
    st.error(f"Could not load {report} report: {e}")
