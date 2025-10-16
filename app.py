import streamlit as st

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
        tally_dashboard.run()
    except Exception as e:
        st.error(f"Could not load Tally report: {e}")

elif report == "Construction":
    try:
        import construction as construction
        construction.run_construction_dashboard()
    except Exception as e:
        st.error(f"Could not load Construction report: {e}")

elif report == "Installs":
    try:
        import install as install
        install.run_installs_dashboard()
    except Exception as e:
        st.error(f"Could not load Installs report: {e}")

elif report == "Splicing":
    try:
        import splicing as splicing
        splicing.run_splicing_dashboard()
    except Exception as e:
        st.error(f"Could not load Splicing report: {e}")

elif report == "Preps":
    try:
        import prep as prep
        prep.run_preps_dashboard()
    except Exception as e:
        st.error(f"Could not load Preps report: {e}")

elif report == "Work Orders":
    try:
        import workorders as workorders
        workorders.run_workorders_dashboard()
    except Exception as e:
        st.error(f"Could not load Work Orders report: {e}")

elif report == "Accounting":
    try:
        import accounting
    except Exception as e:
        st.error(f"Could not load Accounting report: {e}")
