import streamlit as st
import branding
# -------------------------------
# Sidebar: Report Selector
# -------------------------------
st.sidebar.title("📊 Reports")

# Always define report before try/except
report = st.sidebar.selectbox(
    "Select Report",
    [
        "Welcome",        # Default page
        "Work Orders",
        "Construction",
        "Tally",
        "Accounting",
        "Projects",
        "Network"
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

    elif report == "Preps":
    try:
        df = fetch_jotform_data(form_id="232136783361054", api_key="32c62a1b6c1a350caed2f989c1be4e48")
        st.sidebar.success(f"Loaded Preps data: {df.shape[0]} rows")
        run_preps_dashboard()
    except Exception as e:
        st.sidebar.error(f"Failed to load data for Preps: {e}")
        st.error("Unable to load Preps dashboard.")


    elif report == "Construction":
        import construction
        construction.run_construction_dashboard()

    elif report == "Tally":
        import dashboard
        dashboard.run_dashboard()

    elif report == "Accounting":
        import importlib
        import accounting as accounting_module
        importlib.reload(accounting_module)

    elif report == "Projects":
        import importlib
        import projects as projects_module
        importlib.reload(projects_module)

    elif report == "Network":
        import importlib
        import network as network_module
        importlib.reload(network_module)

except Exception as e:
    st.error(f"Could not load {report} report: {e}")

