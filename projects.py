import streamlit as st
import pandas as pd
import altair as alt

st.set_page_config(page_title="Project Dashboard", page_icon="🚀", layout="wide")

# --- One-time header using session_state ---
if "header_drawn" not in st.session_state:
    st.image(
        "https://images.squarespace-cdn.com/content/v1/651eb4433b13e72c1034f375/"
        "369c5df0-5363-4827-b041-1add0367f447/PBB+long+logo.png?format=1500w",
        use_container_width=True,
    )
    st.title("🚀 Project Performance Dashboard")
    st.session_state["header_drawn"] = True

# --- Prevent scroll jump on rerun ---
st.markdown(
    """
    <style>
    html { scroll-behavior: smooth; }
    </style>
    """,
    unsafe_allow_html=True,
)

@st.cache_data(ttl=300)
def load_data(sheet_url):
    csv_url = sheet_url.replace("/edit?usp=sharing", "/export?format=csv")
    return pd.read_csv(csv_url, header=None)

def process_data(df):
    df = df.copy()
    df.columns = df.columns.str.strip()
    req = ["Type", "Design", "As Built"]
    if not all(c in df.columns for c in req):
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

# --- Single container for all dynamic content ---
main_container = st.empty()

def render_dashboard():
    GOOGLE_SHEET_URL = (
        "https://docs.google.com/spreadsheets/d/109p39EGYEikgbZT4kSW71_sXJNMM-4Tjjd5q-l9Tx_0/edit?usp=sharing"
    )
    try:
        raw = load_data(GOOGLE_SHEET_URL)
    except Exception as e:
        st.error(f"Error loading sheet: {e}")
        return

    try:
        st.caption(f"Last Updated: {raw.iloc[6,0]}")
    except Exception:
        pass

    # locate header
    try:
        header_idx = raw[raw[0] == "Type"].index[0]
        header = raw.iloc[header_idx].fillna("Unnamed")
        df = raw.copy()
        df.columns = header
        df = df.iloc[header_idx + 1:].reset_index(drop=True)
        df = df.loc[:, ~df.columns.duplicated()]
    except Exception:
        st.error("Header row not found.")
        return

    kpi = process_data(df)
    if kpi is None or kpi.empty:
        st.warning("No valid data found.")
        return

    # Sidebar controls
    st.sidebar.header("Controls")
    if st.sidebar.button("🔄 Refresh Data"):
        load_data.clear()
        st.rerun()
    all_types = sorted(kpi["Type"].unique())
    selected = st.sidebar.multiselect(
        "Filter Project Type", options=all_types, default=all_types
    )
    kpi = kpi[kpi["Type"].isin(selected)]

    # KPIs
    st.header("📊 Overall Project Health")
    total_d, total_b = kpi["Design"].sum(), kpi["As Built"].sum()
    total_l = kpi["Left to be Built"].sum()
    overall = (total_b / total_d * 100) if total_d else 0
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Design", f"{total_d:,.0f}")
    c2.metric("Total As Built", f"{total_b:,.0f}")
    c3.metric("Left to be Built", f"{total_l:,.0f}")
    c4.metric("Overall Completion", f"{overall:.2f}%")
    st.divider()

    # Tabs
    tab1, tab2 = st.tabs(["📊 KPI Overview", "📄 Detailed Breakdown"])
    with tab1:
        st.subheader("Completion % by Type")
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
            st.altair_chart(chart, use_container_width=True)
        else:
            st.info("No data to display.")

    with tab2:
        st.subheader("Detailed Breakdown")
        if not kpi.empty:
            kpi = kpi.sort_values(by="Completion %", ascending=False)
            top = kpi.iloc[0]["Type"]
            for _, r in kpi.iterrows():
                st.markdown("---")
                st.markdown(
                    f"🏆 **{r['Type']}**" if r["Type"] == top else f"**{r['Type']}**"
                )
                st.progress(int(r["Completion %"]), text=f"{r['Completion %']:.2f}%")
                c1, c2, c3 = st.columns(3)
                c1.metric("Completion %", f"{r['Completion %']:.2f}%")
                c2.metric("As Built", f"{r['As Built']:,.2f}")
                c3.metric("Design Target", f"{r['Design']:,.2f}")
        else:
            st.info("No detailed data.")

    # Raw Data
    with st.expander("🔍 View Raw Data Table"):
        cols = [c for c in df.columns if not str(c).startswith("Unnamed")]
        st.dataframe(df[cols].fillna(""), use_container_width=True)

# --- Draw inside the single placeholder ---
with main_container.container():
    render_dashboard()
