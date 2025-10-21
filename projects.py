import streamlit as st
import pandas as pd
import altair as alt
from io import BytesIO

# --- Page Configuration (Best practice: call this first) ---
st.set_page_config(
    page_title="Project Performance Dashboard",
    page_icon="🚀",
    layout="wide"
)

# --- Constants ---
COL_TYPE = "Type"
COL_DESIGN = "Design"
COL_AS_BUILT = "As Built"
COL_COMPLETION = "Completion %"
COL_LEFT_TO_BUILD = "Left to be Built"
GOOGLE_SHEET_URL = "https://docs.google.com/spreadsheets/d/109p39EGYEikgbZT4kSW71_sXJNMM-4Tjjd5q-l9Tx_0/edit?usp=sharing"

# --- One-time header using session_state ---
def display_header():
    """Displays the header image and title only on the first run."""
    if "header_drawn" not in st.session_state:
        st.image(
            "https://images.squarespace-cdn.com/content/v1/651eb4433b13e72c1034f375/"
            "369c5df0-5363-4827-b041-1add0367f447/PBB+long+logo.png?format=1500w",
            use_container_width=True,
        )
        st.title("🚀 Project Performance Dashboard")
        st.session_state["header_drawn"] = True

# --- Data Loading and Processing ---
@st.cache_data(ttl=300)
def load_data(sheet_url):
    """Loads data from a Google Sheet URL. Returns None on failure."""
    try:
        csv_url = sheet_url.replace("/edit?usp=sharing", "/export?format=csv")
        return pd.read_csv(csv_url, header=None)
    except Exception as e:
        st.error(f"Error loading data from Google Sheet: {e}")
        return None

def process_data(raw_df):
    """
    Processes the raw DataFrame. Returns (clean_df, kpi_df).
    Returns (None, None) on critical processing failure.
    """
    if raw_df is None or raw_df.empty:
        return None, None

    try:
        # 1. Find the header row by searching for the cell that contains 'Type'
        header_row_filter = raw_df.apply(lambda r: r.astype(str).str.strip().eq('Type').any(), axis=1)
        if not header_row_filter.any():
            st.error("Processing Error: Could not find a header row containing the word 'Type'.")
            return raw_df, None # Return raw data for debugging, but no kpi_df

        header_row_index = header_row_filter.idxmax()
        
        # 2. Set the header and create the main DataFrame
        header = raw_df.iloc[header_row_index].str.strip().fillna('Unnamed')
        df = raw_df.iloc[header_row_index + 1 :].copy()
        df.columns = header
        df = df.loc[:, ~df.columns.duplicated()]

        # 3. Check for required columns
        required_cols = [COL_TYPE, COL_DESIGN, COL_AS_BUILT]
        if not all(col in df.columns for col in required_cols):
            st.error(f"Processing Error: Missing one or more required columns. Found: {list(df.columns)}. Required: {required_cols}")
            return df, None

        # 4. Clean and process data
        df = df.dropna(subset=[COL_TYPE])
        df[COL_TYPE] = df[COL_TYPE].astype(str).str.replace(":", "", regex=False).str.strip().str.title()
        df = df[~df[COL_TYPE].str.contains("Last Edited", case=False, na=False)]

        for col in [COL_DESIGN, COL_AS_BUILT]:
            df[col] = pd.to_numeric(df[col].astype(str).str.replace(",", ""), errors='coerce').fillna(0)

        # 5. Aggregate data for KPIs
        kpi_df = df.groupby(COL_TYPE).agg({COL_DESIGN: "sum", COL_AS_BUILT: "sum"}).reset_index()
        kpi_df = kpi_df[kpi_df[COL_DESIGN] > 0] # Avoid division by zero
        
        if kpi_df.empty:
             st.warning("No data rows with a 'Design' value greater than 0 were found after processing.")
             return df, kpi_df

        kpi_df[COL_COMPLETION] = (kpi_df[COL_AS_BUILT] / kpi_df[COL_DESIGN] * 100).clip(0, 100)
        kpi_df[COL_LEFT_TO_BUILD] = kpi_df[COL_DESIGN] - kpi_df[COL_AS_BUILT]
        
        return df, kpi_df

    except Exception as e:
        st.error(f"A critical error occurred during data processing: {e}")
        return raw_df, None


# --- UI Display Functions ---
def display_sidebar(kpi_df):
    st.sidebar.header("Controls")
    if st.sidebar.button("🔄 Refresh Data"):
        st.cache_data.clear()
        st.rerun()

    if kpi_df is not None and not kpi_df.empty:
        all_types = sorted(kpi_df[COL_TYPE].unique())
        selected_types = st.sidebar.multiselect("Filter Project Type", options=all_types, default=all_types)
        
        output = BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            kpi_df.to_excel(writer, index=False, sheet_name='Summary')
        
        st.sidebar.download_button("📥 Download Data as Excel", output.getvalue(), "project_kpi_summary.xlsx")
        return kpi_df[kpi_df[COL_TYPE].isin(selected_types)]
    else:
        st.sidebar.info("No data available to filter.")
        return pd.DataFrame()

def display_dashboard_content(kpi_df):
    st.header("📊 Overall Project Health")
    total_design = kpi_df[COL_DESIGN].sum()
    total_built = kpi_df[COL_AS_BUILT].sum()
    total_left = kpi_df[COL_LEFT_TO_BUILD].sum()
    overall_completion = (total_built / total_design * 100) if total_design else 0

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Design", f"{total_design:,.0f}")
    c2.metric("Total As Built", f"{total_built:,.0f}")
    c3.metric("Left to be Built", f"{total_left:,.0f}")
    c4.metric("Overall Completion", f"{overall_completion:.2f}%")
    st.divider()

    tab1, tab2 = st.tabs(["📊 KPI Overview", "📄 Detailed Breakdown"])
    with tab1:
        chart = alt.Chart(kpi_df).mark_bar(color="#4A90E2").encode(
            x=alt.X(f"{COL_COMPLETION}:Q", scale=alt.Scale(domain=[0, 100]), title="Completion %"),
            y=alt.Y(f"{COL_TYPE}:N", sort="-x", title="Project Type"),
            tooltip=[COL_TYPE, COL_COMPLETION, COL_AS_BUILT, COL_DESIGN],
        )
        st.altair_chart(chart, use_container_width=True)
    with tab2:
        st.subheader("Detailed Breakdown")
        for _, row in kpi_df.sort_values(by=COL_COMPLETION, ascending=False).iterrows():
            st.markdown("---")
            st.markdown(f"**{row[COL_TYPE]}**")
            st.progress(int(row[COL_COMPLETION]), text=f"{row[COL_COMPLETION]:.2f}%")
            c1, c2, c3 = st.columns(3)
            c1.metric("Completion %", f"{row[COL_COMPLETION]:.2f}%")
            c2.metric("As Built", f"{row[COL_AS_BUILT]:,.2f}")
            c3.metric("Design Target", f"{row[COL_DESIGN]:,.2f}")

# --- Main App ---
def main():
    display_header()
    raw_df = load_data(GOOGLE_SHEET_URL)
    
    # Process data and handle potential errors
    clean_df, kpi_df = process_data(raw_df)
    
    # Display sidebar regardless of data state
    filtered_kpi = display_sidebar(kpi_df)

    # Main content area logic
    if not filtered_kpi.empty:
        try:
            st.caption(f"Last Updated: {raw_df.iloc[6,0]}")
        except: pass
        display_dashboard_content(filtered_kpi)
    else:
        st.info("No data to display. This could be due to a processing error or filter selection.")
        # If processing failed, show the raw data to help the user debug their sheet
        if clean_df is not None:
            with st.expander("🔍 View Raw Loaded Data for Debugging"):
                st.dataframe(clean_df)
                
if __name__ == "__main__":
    main()
