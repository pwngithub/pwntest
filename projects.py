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
# REFACTORED: Using constants for column names prevents typos and makes code easier to update.
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
    """Loads data from a Google Sheet URL and converts it to a DataFrame."""
    try:
        csv_url = sheet_url.replace("/edit?usp=sharing", "/export?format=csv")
        return pd.read_csv(csv_url, header=None)
    except Exception as e:
        st.error(f"Error loading data from Google Sheet: {e}")
        return None

def process_data(raw_df):
    """Processes the raw DataFrame to find headers, clean data, and calculate KPIs."""
    if raw_df is None:
        return None, None

    # Dynamically find the header row containing "Type"
    try:
        header_row_index = raw_df[raw_df[0] == COL_TYPE].index[0]
        header = raw_df.iloc[header_row_index].str.strip()
        df = raw_df.iloc[header_row_index + 1 :].copy()
        df.columns = header
        df = df.loc[:, ~df.columns.duplicated()] # Remove duplicate columns
    except (IndexError, KeyError):
        st.error("Header row with 'Type' column not found. Please check the sheet format.")
        return None, None
    
    # Check for required columns
    required_cols = [COL_TYPE, COL_DESIGN, COL_AS_BUILT]
    if not all(col in df.columns for col in required_cols):
        st.warning(f"Missing one or more required columns: {', '.join(required_cols)}")
        return df, None

    # Clean and process data
    df = df.dropna(subset=[COL_TYPE])
    df[COL_TYPE] = df[COL_TYPE].astype(str).str.replace(":", "", regex=False).str.strip().str.title()
    df = df[~df[COL_TYPE].str.contains("Last Edited", case=False, na=False)]

    for col in [COL_DESIGN, COL_AS_BUILT]:
        df[col] = pd.to_numeric(df[col].astype(str).str.replace(",", ""), errors="coerce").fillna(0)

    # Aggregate data
    kpi_df = df.groupby(COL_TYPE).agg({COL_DESIGN: "sum", COL_AS_BUILT: "sum"}).reset_index()
    kpi_df[COL_COMPLETION] = (kpi_df[COL_AS_BUILT] / kpi_df[COL_DESIGN].replace(0, pd.NA) * 100).clip(0, 100).fillna(0)
    kpi_df[COL_LEFT_TO_BUILD] = kpi_df[COL_DESIGN] - kpi_df[COL_AS_BUILT]
    
    return df, kpi_df

# --- UI Display Functions ---
# REFACTORED: Broke the main function into smaller, manageable UI components.

def display_sidebar(kpi_df):
    """Renders the sidebar with controls."""
    st.sidebar.header("Controls")
    if st.sidebar.button("🔄 Refresh Data"):
        st.cache_data.clear()
        st.rerun()

    all_types = sorted(kpi_df[COL_TYPE].unique())
    selected_types = st.sidebar.multiselect(
        "Filter Project Type", options=all_types, default=all_types
    )
    
    # NEW: Added a download button for the processed data.
    if not kpi_df.empty:
        output = BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            kpi_df.to_excel(writer, index=False, sheet_name='Summary')
        st.sidebar.download_button(
            label="📥 Download Data as Excel",
            data=output.getvalue(),
            file_name="project_kpi_summary.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        
    return kpi_df[kpi_df[COL_TYPE].isin(selected_types)]

def display_kpis(kpi_df):
    """Displays the main KPI metrics at the top of the page."""
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

def get_progress_color(percentage):
    """NEW: Helper function to return a color based on completion percentage."""
    if percentage >= 90:
        return "green"
    elif percentage >= 50:
        return "orange"
    else:
        return "red"

def display_tabs(kpi_df):
    """Renders the two main content tabs: Overview Chart and Detailed Breakdown."""
    tab1, tab2 = st.tabs(["📊 KPI Overview", "📄 Detailed Breakdown"])
    
    with tab1:
        st.subheader("Completion % by Type")
        if not kpi_df.empty:
            chart = (
                alt.Chart(kpi_df)
                .mark_bar(color="#4A90E2")
                .encode(
                    x=alt.X(f"{COL_COMPLETION}:Q", scale=alt.Scale(domain=[0, 100]), title="Completion %"),
                    y=alt.Y(f"{COL_TYPE}:N", sort="-x", title="Project Type"),
                    tooltip=[COL_TYPE, COL_COMPLETION, COL_AS_BUILT, COL_DESIGN],
                )
            )
            st.altair_chart(chart, use_container_width=True)
        else:
            st.info("No data to display for the selected filters.")

    with tab2:
        st.subheader("Detailed Breakdown")
        if not kpi_df.empty:
            sorted_kpi = kpi_df.sort_values(by=COL_COMPLETION, ascending=False)
            top_performer = sorted_kpi.iloc[0][COL_TYPE]
            
            for _, row in sorted_kpi.iterrows():
                st.markdown("---")
                # NEW: Added color to titles for quick visual assessment.
                color = get_progress_color(row[COL_COMPLETION])
                title = f"**{row[COL_TYPE]}**"
                if row[COL_TYPE] == top_performer:
                    title = f"🏆 {title}"

                st.markdown(f"<h4 style='color:{color};'>{title}</h4>", unsafe_allow_html=True)
                
                st.progress(int(row[COL_COMPLETION]), text=f"{row[COL_COMPLETION]:.2f}%")
                
                c1, c2, c3 = st.columns(3)
                c1.metric("Completion %", f"{row[COL_COMPLETION]:.2f}%")
                c2.metric("As Built", f"{row[COL_AS_BUILT]:,.2f}")
                c3.metric("Design Target", f"{row[COL_DESIGN]:,.2f}")
        else:
            st.info("No detailed data to display for the selected filters.")

# --- Main App ---
def main():
    """Main function to run the Streamlit app."""
    display_header()
    
    raw_df = load_data(GOOGLE_SHEET_URL)
    
    if raw_df is None:
        st.warning("Could not load data. The dashboard cannot be displayed.")
        return

    # Display last updated time if possible
    try:
        st.caption(f"Last Updated: {raw_df.iloc[6,0]}")
    except IndexError:
        pass # Silently fail if the cell doesn't exist

    clean_df, kpi_df = process_data(raw_df)

    if kpi_df is None or kpi_df.empty:
        st.warning("No valid data could be processed. Please check the Google Sheet format.")
        return

    filtered_kpi = display_sidebar(kpi_df)
    
    if filtered_kpi.empty:
        st.info("No data available for the selected filters.")
    else:
        display_kpis(filtered_kpi)
        display_tabs(filtered_kpi)

    # Raw Data Expander
    with st.expander("🔍 View Raw Cleaned Data Table"):
        if clean_df is not None:
            # Show only columns that are not completely empty or unnamed
            valid_cols = [c for c in clean_df.columns if not str(c).startswith("Unnamed") and clean_df[c].notna().any()]
            st.dataframe(clean_df[valid_cols].fillna(""), use_container_width=True)
        else:
            st.write("No raw data to display.")

if __name__ == "__main__":
    main()
