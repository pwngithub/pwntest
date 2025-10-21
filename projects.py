import streamlit as st
import pandas as pd
import altair as alt

# -----------------------------------------
# PAGE CONFIGURATION
# -----------------------------------------
st.set_page_config(page_title="Project Dashboard", page_icon="🚀", layout="wide")

# -----------------------------------------
# APP HEADER (outside rerun area)
# -----------------------------------------
header_placeholder = st.empty()
with header_placeholder.container():
    st.image(
        "https://images.squarespace-cdn.com/content/v1/651eb4433b13e72c1034f375/"
        "369c5df0-5363-4827-b041-1add0367f447/PBB+long+logo.png?format=1500w",
        use_container_width=True,
    )
    st.title("🚀 Project Performance Dashboard")

# -----------------------------------------
# DATA FUNCTIONS
# -----------------------------------------
@st.cache_data(ttl=300)
def load_data(sheet_url):
    try:
        csv_url = sheet_url.replace("/edit?usp=sharing", "/export?format=csv")
        return pd.read_csv(csv_url, header=None)
    except Exception as e:
        st.error(f"Failed to load data. Error: {e}")
        return None


def process_data(df):
    df = df.copy()
    df.columns = df.columns.str.strip()
    req = ["Type", "Design", "As Built"]
    if not all(c in df.columns for c in req):
        st.warning("Missing required columns.")
        return None

    df = df.dropna(subset=["Type"])
    df["Type"] = (
        df["Type"].astype(str).str.replace(":", "", regex=False).str.strip().str.title()
    )
    df = df[~df["Type"].str.contains("Last Edited", case=False, na=False)]

    for c in ["Design", "As Built"]:
        df[c] = pd.to_numeric(df[c].astype(str).str.replace(",", ""), errors="coerce").fillna(0)

    out = df.groupby("Type").agg({"Design": "sum", "As Built": "sum"}).reset_index()
    out["Completion %"] = (out["As Built"] / out["Design"].replace(0, pd.NA)) * 100
    out["Completion %"] = out["Completion %"].clip(0, 100).fillna(0)
    out["Left to be Built"] = out["Design"] - out["As Built"]
    return out


# -----------------------------------------
# MAIN DASHBOARD
# -----------------------------------------
def show_dashboard():
    GOOGLE_SHEET_URL = (
        "https://docs.google.com/spreadsheets/d/109p39EGYEikgbZT4kSW71_sXJNMM-4Tjjd5q-l9Tx_0/edit?usp=sharing"
    )

    raw = load_data(GOOGLE_SHEET_URL)
    if raw is None:
        st.warning("Could not load data.")
        return

    try:
        st.markdown(f"**Sheet Last Updated:** {raw.iloc[6,0]}  ")
    except Exception:
        st.caption("No update timestamp found.")

    try:
        header_idx = raw[raw[0] == "Type"].index[0]
        header = raw.iloc[header_idx].fillna("Unnamed")
        df = raw.copy()
        df.columns = header
        df = df.iloc[header_idx + 1:].reset_index(drop=True)
        df = df.loc[:, ~df.columns.duplicated()]
    except Exception:
        st.error("Could not find header row.")
        return

    kpi = process_data(df)
    if kpi is None or kpi.empty:
        st.warning("No valid data found.")
        return

    # --------------- SIDEBAR ---------------
    st.sidebar.header("Controls")
    if st.sidebar.button("🔄 Refresh Data"):
        load_data.clear()
        st.rerun()

    all_types = sorted(kpi["Type"].unique())
    selected = st.sidebar.multiselect(
        "Filter Project Type", options=all_types, default=all_types
    )
    kpi = kpi[kpi["Type"].isin(selected)]

    # -----------------------------------------
    # SINGLE CONTAINER PREVENTS VISUAL DUPLICATION
    # -----------------------------------------
    with st.container():
        st.header("📊 Overall Project Health")
        total_d = kpi["Design"].sum()
        total_b = kpi["As Built"].sum()
        total_l = kpi["Left to be Built"].sum()
        overall = (total_b / total_d * 100) if total_d else 0
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Total Design", f"{total_d:,.0f}")
        c2.metric("Total As Built", f"{total_b:,.0f}")
        c3.metric("Left to be Built", f"{total_l:,.0f}")
        c4.metric("Overall Completion", f"{overall:.2f}%")
        st.divider()

        # Tabs for data views
        tab1, tab2 = st.tabs(["📊 KPI Overview", "📄 Detailed Breakdown"])

        with tab1:
            st.subheader("Completion Percentage by Type")
            if not kpi.empty:
                chart = (
                    alt.Chart(kpi)
                    .mark_bar(color="#4A90E2")
                    .encode(
                        x=alt.X("Completion %:Q", scale=alt.Scale(domain=[0, 100])),
                        y=alt.Y("Type:N", sort="-x"),
                        tooltip=["Type", "Completion %", "As Built", "Design"],
                    )
                )
                text = chart.mark_text(align="left", baseline="middle", dx=3).encode(
                    text=alt.Text("Completion %:Q", format=".2f")
                )
                st.altair_chart(chart + text, use_container_width=True)
            else:
                st.info("No data to display.")

        with tab2:
            st.subheader("Detailed Breakdown by Project Type")
            if not kpi.empty:
                kpi = kpi.sort_values(by="Completion %", ascending=False)
                top = kpi.iloc[0]["Type"]
                for _, r in kpi.iterrows():
                    st.markdown("---")
                    st.markdown(
                        f"🏆 **{r['Type']}** (Top Performer)"
                        if r["Type"] == top
                        else f"**{r['Type']}**"
                    )
                    st.progress(int(r["Completion %"]), text=f"{r['Completion %']:.2f}%")
                    cc1, cc2, cc3 = st.columns(3)
                    cc1.metric("Completion %", f"{r['Completion %']:.2f}%")
                    cc2.metric("As Built", f"{r['As Built']:,.2f}")
                    cc3.metric("Design Target", f"{r['Design']:,.2f}")
            else:
                st.info("No data available.")

        # Expander for raw data table
        with st.expander("🔍 View Raw Data Table"):
            cols = [c for c in df.columns if not str(c).startswith("Unnamed")]
            st.dataframe(df[cols].fillna(""), use_container_width=True)


# -----------------------------------------
# RUN APP
# -----------------------------------------
show_dashboard()
